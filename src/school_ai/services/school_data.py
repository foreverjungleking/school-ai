"""Read-only application service for school-domain data."""

from datetime import time

from pydantic import BaseModel, ConfigDict

from school_ai.repositories import SchoolDataRepository


class SchoolDataNotFoundError(LookupError):
    pass


class DataView(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)


class AvailabilityView(DataView):
    id: int
    weekday: int
    start_time: time
    end_time: time
    available: bool


class TeacherView(DataView):
    id: int
    name: str
    availability: tuple[AvailabilityView, ...]


class RoomView(DataView):
    id: int
    name: str
    capacity: int
    room_type: str
    availability: tuple[AvailabilityView, ...]


class StudentGroupView(DataView):
    id: int
    name: str
    size: int


class ActivityView(DataView):
    id: int
    name: str
    student_group_id: int
    teacher_id: int
    sessions_per_week: int
    duration_minutes: int
    required_room_type: str


class SchoolDataService:
    def __init__(self, repository: SchoolDataRepository) -> None:
        self._repository = repository

    def list_teachers(self) -> tuple[TeacherView, ...]:
        return tuple(TeacherView.model_validate(item) for item in self._repository.list_teachers())

    def get_teacher(self, teacher_id: int) -> TeacherView:
        item = self._repository.get_teacher(teacher_id)
        if item is None:
            raise SchoolDataNotFoundError(f"teacher {teacher_id} not found")
        return TeacherView.model_validate(item)

    def list_rooms(self) -> tuple[RoomView, ...]:
        return tuple(RoomView.model_validate(item) for item in self._repository.list_rooms())

    def get_room(self, room_id: int) -> RoomView:
        item = self._repository.get_room(room_id)
        if item is None:
            raise SchoolDataNotFoundError(f"room {room_id} not found")
        return RoomView.model_validate(item)

    def list_student_groups(self) -> tuple[StudentGroupView, ...]:
        return tuple(
            StudentGroupView.model_validate(item)
            for item in self._repository.list_student_groups()
        )

    def get_student_group(self, group_id: int) -> StudentGroupView:
        item = self._repository.get_student_group(group_id)
        if item is None:
            raise SchoolDataNotFoundError(f"student group {group_id} not found")
        return StudentGroupView.model_validate(item)

    def list_activities(self) -> tuple[ActivityView, ...]:
        return tuple(
            ActivityView.model_validate(item)
            for item in self._repository.list_activities()
        )

    def get_activity(self, activity_id: int) -> ActivityView:
        item = self._repository.get_activity(activity_id)
        if item is None:
            raise SchoolDataNotFoundError(f"activity {activity_id} not found")
        return ActivityView.model_validate(item)
