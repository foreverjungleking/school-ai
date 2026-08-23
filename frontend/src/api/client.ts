import type {
  Activity,
  GenerateDraftResult,
  Room,
  Schedule,
  ScheduleComparison,
  ScheduleVersion,
  StudentGroup,
  Teacher,
} from "../types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "API_UNAVAILABLE", "The School AI API is unavailable. Check that the backend is running.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiError(
      response.status,
      detail?.code ?? "API_ERROR",
      detail?.message ?? "The request could not be completed.",
      detail,
    );
  }
  return payload as T;
}

export const schoolDataApi = {
  teachers: () => request<Teacher[]>("/teachers"),
  rooms: () => request<Room[]>("/rooms"),
  groups: () => request<StudentGroup[]>("/student-groups"),
  activities: () => request<Activity[]>("/activities"),
};

export const schedulesApi = {
  create: (name: string) =>
    request<Schedule>("/schedules", { method: "POST", body: JSON.stringify({ name }) }),
  get: (scheduleId: number) => request<Schedule>(`/schedules/${scheduleId}`),
  versions: (scheduleId: number) => request<ScheduleVersion[]>(`/schedules/${scheduleId}/versions`),
  version: (scheduleId: number, versionId: number) =>
    request<ScheduleVersion>(`/schedules/${scheduleId}/versions/${versionId}`),
  published: async (scheduleId: number) => {
    try {
      return await request<ScheduleVersion>(`/schedules/${scheduleId}/published`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  generateDraft: (scheduleId: number) =>
    request<GenerateDraftResult>(`/schedules/${scheduleId}/drafts`, {
      method: "POST",
      body: JSON.stringify({ time_slots: buildDemoTimeSlots(), max_solve_seconds: 10 }),
    }),
  publish: (scheduleId: number, versionId: number) =>
    request<ScheduleVersion>(`/schedules/${scheduleId}/versions/${versionId}/publish`, { method: "POST" }),
  compare: (scheduleId: number, fromVersionId: number, toVersionId: number) =>
    request<ScheduleComparison>(
      `/schedules/${scheduleId}/compare?from_version_id=${fromVersionId}&to_version_id=${toVersionId}`,
    ),
};

function buildDemoTimeSlots() {
  const slots = [];
  let id = 1;
  for (let weekday = 0; weekday < 5; weekday += 1) {
    for (let hour = 8; hour < 16; hour += 1) {
      slots.push({
        id: id++,
        weekday,
        start_time: `${String(hour).padStart(2, "0")}:00:00`,
        end_time: `${String(hour + 1).padStart(2, "0")}:00:00`,
      });
    }
  }
  return slots;
}
