from datetime import time

import pytest
from pydantic import ValidationError

from school_ai.database.models import Teacher
from school_ai.schemas import (
    ActivityCreate,
    RoomCreate,
    TeacherAvailabilityCreate,
    TeacherRead,
)


def test_create_schemas_validate_domain_values() -> None:
    room = RoomCreate(name="Hall", capacity=100, room_type="assembly")
    activity = ActivityCreate(
        name="Drama",
        student_group_id=1,
        teacher_id=2,
        sessions_per_week=2,
        duration_minutes=90,
        required_room_type="assembly",
    )

    assert room.capacity == 100
    assert activity.sessions_per_week == 2


@pytest.mark.parametrize(
    "values",
    [
        {"weekday": 7, "start_time": time(8), "end_time": time(9)},
        {"weekday": 1, "start_time": time(10), "end_time": time(9)},
    ],
)
def test_availability_rejects_invalid_ranges(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TeacherAvailabilityCreate(teacher_id=1, **values)


def test_read_schema_serializes_orm_model() -> None:
    teacher = Teacher(id=5, name="Ms Wong")

    assert TeacherRead.model_validate(teacher).model_dump() == {
        "id": 5,
        "name": "Ms Wong",
    }


def test_positive_values_are_required() -> None:
    with pytest.raises(ValidationError):
        RoomCreate(name="Tiny room", capacity=0, room_type="classroom")
