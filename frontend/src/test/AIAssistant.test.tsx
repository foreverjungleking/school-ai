import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { AIAssistant } from "../components/AIAssistant";

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

const baseResponse = {
  assistant_text: "Aisha Rahman is available.",
  tool_calls: [{ name: "list_teachers", arguments: {}, success: true, result: [], error: null }],
  metadata: { provider: "fake", tool_iterations: 1, draft_created: false },
};

function renderAssistant(onDraftCreated = vi.fn().mockResolvedValue(undefined)) {
  return {
    onDraftCreated,
    onReviewDraft: vi.fn(),
    ...render(<AIAssistant onDraftCreated={onDraftCreated} onReviewDraft={vi.fn()} />),
  };
}

test("renders the AI page and all example prompts", () => {
  renderAssistant();

  expect(screen.getByRole("heading", { name: "AI Assistant" })).toBeInTheDocument();
  expect(screen.getByText("Cannot publish schedules")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "What can you help me with?" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "List the teachers." })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show me the current published schedule." })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Generate a new draft." })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Compare the newest draft with the published schedule." })).toBeInTheDocument();
});

test("sends a user message and renders the assistant and tool activity", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn().mockReturnValue(jsonResponse(baseResponse));
  vi.stubGlobal("fetch", fetchMock);
  renderAssistant();

  await user.type(screen.getByLabelText("Message"), "List the teachers.");
  await user.click(screen.getByRole("button", { name: "Send" }));

  expect(await screen.findByText("Aisha Rahman is available.")).toBeInTheDocument();
  expect(screen.getByText("Used tools")).toBeInTheDocument();
  expect(screen.getByText("list_teachers")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8000/ai/chat",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ message: "List the teachers." }) }),
  );
});

test("shows a stable unavailable message without affecting scheduling", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(jsonResponse({
    detail: { code: "AI_PROVIDER_NOT_CONFIGURED", message: "AI_PROVIDER is not configured" },
  }, 503)));
  renderAssistant();

  await user.type(screen.getByLabelText("Message"), "Hello");
  await user.click(screen.getByRole("button", { name: "Send" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "AI Assistant is currently unavailable. Scheduling and timetable features continue to work normally.",
  );
});

test("refreshes schedule state and offers review after a draft is created", async () => {
  const user = userEvent.setup();
  const onDraftCreated = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(jsonResponse({
    assistant_text: "A new draft was created successfully.",
    tool_calls: [
      { name: "get_current_demo_schedule", arguments: {}, success: true, result: {}, error: null },
      { name: "create_schedule_draft", arguments: {}, success: true, result: {}, error: null },
    ],
    metadata: { provider: "fake", tool_iterations: 2, draft_created: true, schedule_id: 7, version_id: 11, solver_status: "OPTIMAL" },
  })));
  renderAssistant(onDraftCreated);

  await user.click(screen.getByRole("button", { name: "Generate a new draft." }));
  await user.click(screen.getByRole("button", { name: "Send" }));

  expect(await screen.findByText("A new draft was created successfully.")).toBeInTheDocument();
  expect(screen.getByText("create_schedule_draft")).toBeInTheDocument();
  expect(screen.getByText("Draft ready · OPTIMAL")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Review draft" })).toBeInTheDocument();
  await waitFor(() => expect(onDraftCreated).toHaveBeenCalledWith(7, 11));
});

test("disables submission while a request is pending", async () => {
  const user = userEvent.setup();
  let resolveRequest!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { resolveRequest = resolve; })));
  renderAssistant();

  await user.type(screen.getByLabelText("Message"), "List teachers");
  await user.click(screen.getByRole("button", { name: "Send" }));

  expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
  expect(screen.getByLabelText("Message")).toBeDisabled();
  resolveRequest(new Response(JSON.stringify(baseResponse), { status: 200, headers: { "Content-Type": "application/json" } }));
  expect(await screen.findByText("Aisha Rahman is available.")).toBeInTheDocument();
});
