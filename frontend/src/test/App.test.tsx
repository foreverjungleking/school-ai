import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { App } from "../App";
import { draftVersion, schoolData } from "./fixtures";

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

function mockInitialData() {
  vi.stubGlobal("fetch", vi.fn((input: string | URL | Request) => {
    const path = String(input);
    if (path.endsWith("/teachers")) return jsonResponse(schoolData.teachers);
    if (path.endsWith("/rooms")) return jsonResponse(schoolData.rooms);
    if (path.endsWith("/student-groups")) return jsonResponse(schoolData.groups);
    if (path.endsWith("/activities")) return jsonResponse(schoolData.activities);
    throw new Error(`Unexpected request: ${path}`);
  }));
}

test("renders the application shell and dashboard summary", async () => {
  mockInitialData();

  render(<App />);

  expect(screen.getByText("School AI")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "Make the school week fit." })).toBeInTheDocument();
  expect(screen.getByText("Available educators").previousSibling).toHaveTextContent("1");
});

test("shows a useful API connectivity error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

  render(<App />);

  expect(await screen.findByRole("alert")).toHaveTextContent("The School AI API is unavailable");
  expect(screen.getByText("API unavailable")).toBeInTheDocument();
});

test("generates a draft once and opens the timetable", async () => {
  const user = userEvent.setup();
  let created = false;
  vi.stubGlobal("fetch", vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/teachers")) return jsonResponse(schoolData.teachers);
    if (url.endsWith("/rooms")) return jsonResponse(schoolData.rooms);
    if (url.endsWith("/student-groups")) return jsonResponse(schoolData.groups);
    if (url.endsWith("/activities")) return jsonResponse(schoolData.activities);
    if (url.endsWith("/schedules") && init?.method === "POST") { created = true; return jsonResponse({ id: 7, name: "School AI Demo Timetable", latest_draft_version_id: null, published_version_id: null }, 201); }
    if (url.endsWith("/schedules/7/drafts")) return jsonResponse({ solver_status: "OPTIMAL", solve_duration_seconds: 0.12, version: draftVersion, solver_metadata: {}, message: "draft schedule version created" }, 201);
    if (url.endsWith("/schedules/7/versions")) return jsonResponse([draftVersion]);
    if (url.endsWith("/schedules/7/published")) return jsonResponse({ detail: { code: "SCHEDULE_VERSION_NOT_FOUND", message: "not found" } }, 404);
    if (url.endsWith("/schedules/7")) return jsonResponse({ id: 7, name: "School AI Demo Timetable", latest_draft_version_id: 11, published_version_id: null });
    throw new Error(`Unexpected request: ${url}`);
  }));
  render(<App />);
  const generateButton = await screen.findByRole("button", { name: "Generate new draft" });

  await user.click(generateButton);

  await waitFor(() => expect(created).toBe(true));
  expect(await screen.findByRole("heading", { name: "Version 2" })).toBeInTheDocument();
  expect(screen.getByText("Mathematics")).toBeInTheDocument();
  expect(screen.getByText(/Draft version 2 created by CP-SAT/)).toBeInTheDocument();
});
