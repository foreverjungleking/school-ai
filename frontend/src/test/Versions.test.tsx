import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { VersionComparison } from "../components/VersionComparison";
import { Versions } from "../components/Versions";
import { comparison, draftVersion, publishedVersion, schoolData } from "./fixtures";

test("renders draft and published version statuses", () => {
  render(<Versions schedule={{ id: 7, name: "Demo", latest_draft_version_id: 11, published_version_id: 10 }} versions={[publishedVersion, draftVersion]} comparison={null} publishingId={null} comparing={false} onSelect={vi.fn()} onPublish={vi.fn()} onCompare={vi.fn()} data={schoolData} />);

  expect(screen.getByText("DRAFT")).toBeInTheDocument();
  expect(screen.getByText("PUBLISHED")).toBeInTheDocument();
});

test("requires a deliberate publish button action", async () => {
  const user = userEvent.setup();
  const publish = vi.fn();
  render(<Versions schedule={{ id: 7, name: "Demo", latest_draft_version_id: 11, published_version_id: 10 }} versions={[draftVersion]} comparison={null} publishingId={null} comparing={false} onSelect={vi.fn()} onPublish={publish} onCompare={vi.fn()} data={schoolData} />);

  await user.click(screen.getByRole("button", { name: "Publish draft" }));

  expect(publish).toHaveBeenCalledWith(draftVersion);
});

test("renders backend-classified version changes", () => {
  render(<VersionComparison comparison={comparison} data={schoolData} />);

  expect(screen.getByText("Moved")).toBeInTheDocument();
  expect(screen.getByText((_, element) => element?.tagName === "SPAN" && element.textContent?.includes("09:00") === true)).toBeInTheDocument();
  expect(screen.getByText("1", { selector: ".comparison-summary strong" })).toBeInTheDocument();
});
