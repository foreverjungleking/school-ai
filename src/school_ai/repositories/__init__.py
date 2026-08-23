"""Persistence boundaries used by application services."""

from school_ai.repositories.schedules import ScheduleRepository
from school_ai.repositories.scheduling_data import (
    SchedulingData,
    SchedulingDataRepository,
)

__all__ = ["ScheduleRepository", "SchedulingData", "SchedulingDataRepository"]
