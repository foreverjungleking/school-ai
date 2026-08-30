export type Availability = {
  id: number;
  weekday: number;
  start_time: string;
  end_time: string;
  available: boolean;
};

export type Teacher = {
  id: number;
  name: string;
  availability: Availability[];
};

export type Room = {
  id: number;
  name: string;
  capacity: number;
  room_type: string;
  availability: Availability[];
};

export type StudentGroup = { id: number; name: string; size: number };

export type Activity = {
  id: number;
  name: string;
  student_group_id: number;
  teacher_id: number;
  sessions_per_week: number;
  duration_minutes: number;
  required_room_type: string;
};

export type Schedule = {
  id: number;
  name: string;
  latest_draft_version_id: number | null;
  published_version_id: number | null;
};

export type VersionStatus = "DRAFT" | "PUBLISHED" | "SUPERSEDED";
export type SolverStatus = "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN";

export type ScheduledLesson = {
  id: number;
  activity_id: number;
  session_index: number;
  teacher_id: number;
  student_group_id: number;
  room_id: number;
  time_slot_id: number;
  weekday: number;
  start_time: string;
  end_time: string;
  duration_minutes: number;
};

export type ScheduleVersion = {
  id: number;
  schedule_id: number;
  version_number: number;
  status: VersionStatus;
  created_at: string;
  published_at: string | null;
  solver_status: SolverStatus;
  solve_duration_seconds: number;
  solver_metadata: Record<string, unknown>;
  lessons: ScheduledLesson[];
};

export type GenerateDraftResult = {
  solver_status: SolverStatus;
  solve_duration_seconds: number;
  version: ScheduleVersion;
  solver_metadata: Record<string, unknown>;
  message: string;
};

export type LessonChange = { before: ScheduledLesson; after: ScheduledLesson };

export type ScheduleComparison = {
  from_version_id: number;
  to_version_id: number;
  unchanged: ScheduledLesson[];
  added: ScheduledLesson[];
  removed: ScheduledLesson[];
  changed: LessonChange[];
};

export type SchoolData = {
  teachers: Teacher[];
  rooms: Room[];
  groups: StudentGroup[];
  activities: Activity[];
};

export type AIToolCall = {
  name: string;
  arguments: Record<string, unknown>;
  success: boolean;
  result: unknown;
  error: string | null;
};

export type AIChatRequest = { message: string };

export type AIChatResponse = {
  assistant_text: string;
  tool_calls: AIToolCall[];
  metadata: {
    provider?: string;
    tool_iterations?: number;
    draft_created?: boolean;
    schedule_id?: number;
    version_id?: number;
    solver_status?: SolverStatus;
    [key: string]: unknown;
  };
};
