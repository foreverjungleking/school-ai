"""Idempotent synthetic data seed for the public School AI demo."""

import argparse
from dataclasses import dataclass
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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


def seed_demo_data(session: Session, *, expand: bool = False) -> SeedResult:
    """Populate an empty database with deterministic, entirely synthetic data."""

    counts = _counts(session)
    if any(counts):
        if all(counts):
            if expand:
                return _expand_demo_data(session)
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
    session.flush()
    return _expand_demo_data(session)


# Fictional lower-secondary curriculum: 25 hour-long lessons per class/week.
_CURRICULUM = (
    ("Mathematics", "Aisha Rahman", 5, "classroom"),
    ("English", "Daniel Tan", 5, "classroom"),
    ("Science", "Mei Lin", 4, "laboratory"),
    ("History", "Sofia Lim", 3, "classroom"),
    ("Physical Education", "Marcus Lee", 2, "sports"),
    ("Music", "Priya Nair", 2, "music"),
    ("Computing", "Alex Wong", 2, "classroom"),
    ("Visual Arts", "Ravi Kumar", 2, "classroom"),
)


def _expand_demo_data(session: Session) -> SeedResult:
    """Explicitly expand the known demo in place, preserving all version rows."""
    teachers = {item.name: item for item in session.scalars(select(Teacher))}
    groups = {item.name: item for item in session.scalars(select(StudentGroup))}
    rooms = {item.name: item for item in session.scalars(select(Room))}
    if (
        set(groups) != {"Year 7 Aurora", "Year 7 Horizon", "Year 8 Summit", "Year 8 Grove"}
        or not {"Aisha Rahman", "Daniel Tan", "Mei Lin", "Priya Nair", "Marcus Lee"} <= teachers.keys()
        or not {"North 201", "South 104", "Discovery Lab", "Harmony Studio", "Sports Hall"} <= rooms.keys()
        or set(teachers) - {item[1] for item in _CURRICULUM}
        or set(rooms) - {"North 201", "South 104", "Discovery Lab", "Harmony Studio", "Sports Hall", "East 301", "West 102"}
    ):
        raise RuntimeError("expansion requires the known synthetic demo dataset")
    activities = list(session.scalars(select(Activity)))
    existing = {(item.student_group_id, item.name): item for item in activities}
    if len(existing) != len(activities) or any(
        item.name not in {spec[0] for spec in _CURRICULUM} for item in activities
    ):
        raise RuntimeError("expansion refuses unknown or duplicate demo activities")
    changed = False
    for _, name, _, _ in _CURRICULUM:
        if name not in teachers:
            teachers[name] = Teacher(name=name)
            session.add(teachers[name])
            changed = True
    for name in ("East 301", "West 102"):
        if name not in rooms:
            rooms[name] = Room(name=name, capacity=32, room_type="classroom")
            session.add(rooms[name])
            changed = True
    # All groups must fit the specialist spaces.
    if rooms["Harmony Studio"].capacity < 28:
        rooms["Harmony Studio"].capacity = 28
        changed = True
    for resource in [*teachers.values(), *rooms.values()]:
        window_type = TeacherAvailability if isinstance(resource, Teacher) else RoomAvailability
        # A 08:00–15:00 school day with a protected 12:00–13:00 lunch break.
        expected = {(day, time(start), time(end), True)
                    for day in range(5) for start, end in ((8, 12), (13, 15))}
        actual = {(w.weekday, w.start_time, w.end_time, w.available)
                  for w in resource.availability}
        if actual != expected:
            resource.availability[:] = [window_type(
                weekday=day, start_time=start, end_time=end, available=available
            ) for day, start, end, available in sorted(expected)]
            changed = True
    for group in groups.values():
        for subject, teacher, sessions, room_type in _CURRICULUM:
            activity = existing.get((group.id, subject))
            if activity is None:
                activity = Activity(name=subject, student_group=group)
                session.add(activity)
                changed = True
            if (activity.teacher != teachers[teacher]
                or activity.sessions_per_week != sessions
                or activity.duration_minutes != 60
                or activity.required_room_type != room_type):
                activity.teacher = teachers[teacher]
                activity.sessions_per_week = sessions
                activity.duration_minutes = 60
                activity.required_room_type = room_type
                changed = True
    session.commit()
    return SeedResult(changed, *_counts(session))


def _counts(session: Session) -> tuple[int, int, int, int]:
    return (
        session.scalar(select(func.count(Teacher.id))) or 0,
        session.scalar(select(func.count(Room.id))) or 0,
        session.scalar(select(func.count(StudentGroup.id))) or 0,
        session.scalar(select(func.count(Activity.id))) or 0,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expand", action="store_true", help="Expand the known synthetic demo curriculum and replace its availability; preserve stored timetable versions")
    args = parser.parse_args()
    engine = create_database_engine(get_database_url())
    with Session(engine) as session:
        result = seed_demo_data(session, expand=args.expand)
    engine.dispose()
    action = "Created" if result.created else "Kept existing"
    print(
        f"{action} synthetic demo data: {result.teachers} teachers, "
        f"{result.rooms} rooms, {result.student_groups} groups, "
        f"{result.activities} activities."
    )


if __name__ == "__main__":
    main()
