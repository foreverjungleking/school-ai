"""Validated inputs and structured outputs for the scheduling engine."""

from datetime import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SolverModel(BaseModel):
    """Immutable base model for solver boundary objects."""

    model_config = ConfigDict(frozen=True)


class AvailabilityWindow(SolverModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    available: bool = True

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilityWindow":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class TimeSlot(SolverModel):
    """A possible session start and the end of its scheduling period."""

    id: int = Field(gt=0)
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "TimeSlot":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class TeacherInput(SolverModel):
    id: int = Field(gt=0)
    availability: tuple[AvailabilityWindow, ...] = ()


class StudentGroupInput(SolverModel):
    id: int = Field(gt=0)
    size: int = Field(gt=0)


class RoomInput(SolverModel):
    id: int = Field(gt=0)
    capacity: int = Field(gt=0)
    room_type: str = Field(min_length=1)
    availability: tuple[AvailabilityWindow, ...] = ()


class ActivityInput(SolverModel):
    id: int = Field(gt=0)
    teacher_id: int = Field(gt=0)
    student_group_id: int = Field(gt=0)
    sessions_per_week: int = Field(gt=0)
    duration_minutes: int = Field(gt=0)
    required_room_type: str | None = Field(default=None, min_length=1)


class SchedulingProblem(SolverModel):
    teachers: tuple[TeacherInput, ...]
    student_groups: tuple[StudentGroupInput, ...]
    rooms: tuple[RoomInput, ...]
    activities: tuple[ActivityInput, ...]
    time_slots: tuple[TimeSlot, ...]
    max_solve_seconds: float = Field(default=10.0, gt=0)

    @model_validator(mode="after")
    def validate_references_and_identifiers(self) -> "SchedulingProblem":
        collections = {
            "teacher": self.teachers,
            "student group": self.student_groups,
            "room": self.rooms,
            "time slot": self.time_slots,
            "activity": self.activities,
        }
        for label, items in collections.items():
            identifiers = [item.id for item in items]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"duplicate {label} id")

        teacher_ids = {teacher.id for teacher in self.teachers}
        group_ids = {group.id for group in self.student_groups}
        for activity in self.activities:
            if activity.teacher_id not in teacher_ids:
                raise ValueError(f"unknown teacher_id {activity.teacher_id}")
            if activity.student_group_id not in group_ids:
                raise ValueError(
                    f"unknown student_group_id {activity.student_group_id}"
                )
        return self


class SolveStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class Assignment(SolverModel):
    activity_id: int
    session_index: int = Field(ge=0)
    teacher_id: int
    student_group_id: int
    room_id: int
    time_slot_id: int
    weekday: int
    start_time: time
    end_time: time


class SolverResult(SolverModel):
    status: SolveStatus
    assignments: tuple[Assignment, ...] = ()
    solve_duration_seconds: float = Field(ge=0)
    objective_value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
