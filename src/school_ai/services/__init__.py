"""Application-service boundary for School AI capabilities."""

from school_ai.services.scheduling import SchedulingService
from school_ai.services.school_data import SchoolDataService

__all__ = ["SchoolDataService", "SchedulingService"]
