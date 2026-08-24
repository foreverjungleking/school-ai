"""Application-service boundary for School AI capabilities."""

from school_ai.services.scheduling import SchedulingService, build_standard_time_slots
from school_ai.services.school_data import SchoolDataService

__all__ = ["SchoolDataService", "SchedulingService", "build_standard_time_slots"]
