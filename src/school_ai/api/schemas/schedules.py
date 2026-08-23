from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from school_ai.database.models import ScheduleVersionStatus
from school_ai.solver import SolveStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CreateScheduleRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("schedule name must not be blank")
        return value


class ScheduleResponse(ApiModel):
    id: int
    name: str
    latest_draft_version_id: int | None = None
    published_version_id: int | None = None


class TimeSlotRequest(ApiModel):
    id: int = Field(gt=0)
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @field_validator("end_time")
    @classmethod
    def end_must_follow_start(cls, value: time, info) -> time:
        start_time = info.data.get("start_time")
        if start_time is not None and value <= start_time:
            raise ValueError("end_time must be after start_time")
        return value


class GenerateDraftRequest(ApiModel):
    time_slots: tuple[TimeSlotRequest, ...] = Field(min_length=1)
    max_solve_seconds: float = Field(default=10.0, gt=0, allow_inf_nan=False)


class ScheduledLessonResponse(ApiModel):
    id: int
    activity_id: int
    session_index: int
    teacher_id: int
    student_group_id: int
    room_id: int
    time_slot_id: int
    weekday: int
    start_time: time
    end_time: time
    duration_minutes: int


class ScheduleVersionResponse(ApiModel):
    id: int
    schedule_id: int
    version_number: int
    status: ScheduleVersionStatus
    created_at: datetime
    published_at: datetime | None
    solver_status: SolveStatus
    solve_duration_seconds: float
    solver_metadata: dict[str, Any]
    lessons: tuple[ScheduledLessonResponse, ...]


class GenerateDraftResponse(ApiModel):
    solver_status: SolveStatus
    solve_duration_seconds: float
    version: ScheduleVersionResponse
    solver_metadata: dict[str, Any]
    message: str


class LessonChangeResponse(ApiModel):
    before: ScheduledLessonResponse
    after: ScheduledLessonResponse


class ScheduleComparisonResponse(ApiModel):
    from_version_id: int
    to_version_id: int
    unchanged: tuple[ScheduledLessonResponse, ...]
    added: tuple[ScheduledLessonResponse, ...]
    removed: tuple[ScheduledLessonResponse, ...]
    changed: tuple[LessonChangeResponse, ...]
