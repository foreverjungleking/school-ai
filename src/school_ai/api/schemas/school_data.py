from datetime import time

from pydantic import BaseModel, ConfigDict


class ApiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AvailabilityResponse(ApiResponse):
    id: int
    weekday: int
    start_time: time
    end_time: time
    available: bool


class TeacherResponse(ApiResponse):
    id: int
    name: str
    availability: tuple[AvailabilityResponse, ...]


class RoomResponse(ApiResponse):
    id: int
    name: str
    capacity: int
    room_type: str
    availability: tuple[AvailabilityResponse, ...]


class StudentGroupResponse(ApiResponse):
    id: int
    name: str
    size: int


class ActivityResponse(ApiResponse):
    id: int
    name: str
    student_group_id: int
    teacher_id: int
    sessions_per_week: int
    duration_minutes: int
    required_room_type: str
