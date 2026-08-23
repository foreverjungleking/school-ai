import type { ScheduleComparison, ScheduleVersion, SchoolData } from "../types";

export const schoolData: SchoolData = {
  teachers: [{ id: 1, name: "Aisha Rahman", availability: [] }],
  rooms: [{ id: 1, name: "North 201", capacity: 30, room_type: "classroom", availability: [] }],
  groups: [{ id: 1, name: "Year 7 Aurora", size: 24 }],
  activities: [{ id: 1, name: "Mathematics", student_group_id: 1, teacher_id: 1, sessions_per_week: 1, duration_minutes: 60, required_room_type: "classroom" }],
};

export const draftVersion: ScheduleVersion = {
  id: 11,
  schedule_id: 7,
  version_number: 2,
  status: "DRAFT",
  created_at: "2026-08-23T08:00:00Z",
  published_at: null,
  solver_status: "OPTIMAL",
  solve_duration_seconds: 0.12,
  solver_metadata: { candidate_count: 40 },
  lessons: [{ id: 21, activity_id: 1, session_index: 0, teacher_id: 1, student_group_id: 1, room_id: 1, time_slot_id: 1, weekday: 0, start_time: "08:00:00", end_time: "09:00:00", duration_minutes: 60 }],
};

export const publishedVersion: ScheduleVersion = {
  ...draftVersion,
  id: 10,
  version_number: 1,
  status: "PUBLISHED",
  published_at: "2026-08-23T09:00:00Z",
};

export const comparison: ScheduleComparison = {
  from_version_id: 10,
  to_version_id: 11,
  unchanged: [],
  added: [],
  removed: [],
  changed: [{
    before: publishedVersion.lessons[0],
    after: { ...draftVersion.lessons[0], time_slot_id: 2, start_time: "09:00:00", end_time: "10:00:00" },
  }],
};
