"""Public interface for the CP-SAT scheduling engine."""

from school_ai.solver.dto import (
    ActivityInput,
    Assignment,
    AvailabilityWindow,
    RoomInput,
    SchedulingProblem,
    SolveStatus,
    SolverResult,
    StudentGroupInput,
    TeacherInput,
    TimeSlot,
)
from school_ai.solver.engine import solve

__all__ = [
    "ActivityInput",
    "Assignment",
    "AvailabilityWindow",
    "RoomInput",
    "SchedulingProblem",
    "SolveStatus",
    "SolverResult",
    "StudentGroupInput",
    "TeacherInput",
    "TimeSlot",
    "solve",
]
