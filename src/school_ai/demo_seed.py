"""Idempotent synthetic data seed for the public School AI demo."""

from dataclasses import dataclass
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from school_ai.database.base import Base
from school_ai.database.models import (
    Activity,
    Room,
    RoomAvailability,
    StudentGroup,
    Teacher,
    TeacherAvailability,
)
from school_ai.database.session import create_database_engine, get_database_url


@dataclass(frozen=True)
class SeedResult:
    created: bool
    teachers: int
    rooms: int
    student_groups: int
    activities: int


def seed_demo_data(session: Session) -> SeedResult:
    """Populate an empty database with deterministic, entirely synthetic data."""

    counts = _counts(session)
    if any(counts):
        if all(counts):
            return SeedResult(False, *counts)
        raise RuntimeError("refusing to seed a partially populated school database")

    teachers = [Teacher(name=name) for name in (
        "Aisha Rahman", "Daniel Tan", "Mei Lin", "Priya Nair", "Marcus Lee"
    )]
    groups = [
        StudentGroup(name="Year 7 Aurora", size=26),
        StudentGroup(name="Year 7 Horizon", size=24),
        StudentGroup(name="Year 8 Summit", size=28),
        StudentGroup(name="Year 8 Grove", size=22),
    ]
    rooms = [
        Room(name="North 201", capacity=32, room_type="classroom"),
        Room(name="South 104", capacity=30, room_type="classroom"),
        Room(name="Discovery Lab", capacity=28, room_type="laboratory"),
        Room(name="Harmony Studio", capacity=26, room_type="music"),
        Room(name="Sports Hall", capacity=80, room_type="sports"),
    ]
    for teacher in teachers:
        teacher.availability.extend(
            TeacherAvailability(
                weekday=weekday,
                start_time=time(8),
                end_time=time(16),
                available=True,
            )
            for weekday in range(5)
        )
    for room in rooms:
        room.availability.extend(
            RoomAvailability(
                weekday=weekday,
                start_time=time(8),
                end_time=time(16),
                available=True,
            )
            for weekday in range(5)
        )

    activity_specs = (
        ("Mathematics", 0, 0, 3, "classroom"),
        ("English", 1, 0, 2, "classroom"),
        ("Science", 2, 1, 2, "laboratory"),
        ("Music", 3, 1, 1, "music"),
        ("Physical Education", 4, 2, 2, "sports"),
        ("History", 0, 2, 2, "classroom"),
        ("Computing", 2, 3, 2, "classroom"),
        ("Visual Arts", 3, 3, 2, "classroom"),
    )
    activities = [
        Activity(
            name=name,
            teacher=teachers[teacher_index],
            student_group=groups[group_index],
            sessions_per_week=sessions,
            duration_minutes=60,
            required_room_type=room_type,
        )
        for name, teacher_index, group_index, sessions, room_type in activity_specs
    ]
    session.add_all([*rooms, *activities])
    session.commit()
    return SeedResult(True, len(teachers), len(rooms), len(groups), len(activities))


def _counts(session: Session) -> tuple[int, int, int, int]:
    return (
        session.scalar(select(func.count(Teacher.id))) or 0,
        session.scalar(select(func.count(Room.id))) or 0,
        session.scalar(select(func.count(StudentGroup.id))) or 0,
        session.scalar(select(func.count(Activity.id))) or 0,
    )


def main() -> None:
    engine = create_database_engine(get_database_url())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = seed_demo_data(session)
    engine.dispose()
    action = "Created" if result.created else "Kept existing"
    print(
        f"{action} synthetic demo data: {result.teachers} teachers, "
        f"{result.rooms} rooms, {result.student_groups} groups, "
        f"{result.activities} activities."
    )


if __name__ == "__main__":
    main()
