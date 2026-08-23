from datetime import time

import pytest
from pydantic import ValidationError

from school_ai.database.models import RoomAvailability, Teacher
from school_ai.schemas import (
    ActivityCreate,
    RoomAvailabilityCreate,
    RoomAvailabilityRead,
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


@pytest.mark.parametrize("weekday", [-1, 7])
def test_room_availability_rejects_invalid_weekday(weekday: int) -> None:
    with pytest.raises(ValidationError):
        RoomAvailabilityCreate(
            room_id=1,
            weekday=weekday,
            start_time=time(8),
            end_time=time(9),
        )


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [(time(10), time(9)), (time(9), time(9))],
)
def test_room_availability_requires_increasing_time_range(
    start_time: time, end_time: time
) -> None:
    with pytest.raises(ValidationError):
        RoomAvailabilityCreate(
            room_id=1,
            weekday=1,
            start_time=start_time,
            end_time=end_time,
        )


def test_room_availability_defaults_to_available() -> None:
    availability = RoomAvailabilityCreate(
        room_id=1,
        weekday=1,
        start_time=time(8),
        end_time=time(9),
    )

    assert availability.available is True


def test_room_availability_read_schema_serializes_orm_model() -> None:
    availability = RoomAvailability(
        id=3,
        room_id=2,
        weekday=1,
        start_time=time(8),
        end_time=time(9),
        available=True,
    )

    assert RoomAvailabilityRead.model_validate(availability).model_dump() == {
        "weekday": 1,
        "start_time": time(8),
        "end_time": time(9),
        "available": True,
        "room_id": 2,
        "id": 3,
    }


def test_read_schema_serializes_orm_model() -> None:
    teacher = Teacher(id=5, name="Ms Wong")

    assert TeacherRead.model_validate(teacher).model_dump() == {
        "id": 5,
        "name": "Ms Wong",
    }


def test_positive_values_are_required() -> None:
    with pytest.raises(ValidationError):
        RoomCreate(name="Tiny room", capacity=0, room_type="classroom")
