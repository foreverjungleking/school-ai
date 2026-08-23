"""Stable service-layer outputs independent of SQLAlchemy models."""

from datetime import datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict

from school_ai.database.models import ScheduleVersionStatus
from school_ai.solver import SolveStatus


class ServiceModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ScheduleSummary(ServiceModel):
    id: int
    name: str
    latest_draft_version_id: int | None = None
    published_version_id: int | None = None


class ScheduledLessonView(ServiceModel):
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


class ScheduleVersionView(ServiceModel):
    id: int
    schedule_id: int
    version_number: int
    status: ScheduleVersionStatus
    created_at: datetime
    published_at: datetime | None
    solver_status: SolveStatus
    solve_duration_seconds: float
    solver_metadata: dict[str, Any]
    lessons: tuple[ScheduledLessonView, ...]


class GenerateScheduleResult(ServiceModel):
    solver_status: SolveStatus
    solve_duration_seconds: float
    version: ScheduleVersionView | None = None
    solver_metadata: dict[str, Any]
    message: str


class LessonChange(ServiceModel):
    before: ScheduledLessonView
    after: ScheduledLessonView


class ScheduleVersionComparison(ServiceModel):
    from_version_id: int
    to_version_id: int
    unchanged: tuple[ScheduledLessonView, ...]
    added: tuple[ScheduledLessonView, ...]
    removed: tuple[ScheduledLessonView, ...]
    changed: tuple[LessonChange, ...]
