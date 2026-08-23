import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Timetable } from "../components/Timetable";
import { draftVersion, schoolData } from "./fixtures";

test("renders scheduled lessons in a weekly calendar with resource details", () => {
  render(<Timetable version={draftVersion} data={schoolData} />);

  expect(screen.getByLabelText("Weekly timetable")).toBeInTheDocument();
  expect(screen.getByText("Monday")).toBeInTheDocument();
  expect(screen.getByText("Mathematics")).toBeInTheDocument();
  expect(screen.getByText("Year 7 Aurora · North 201")).toBeInTheDocument();
  expect(screen.getByText("Aisha Rahman")).toBeInTheDocument();
});
