from datetime import time

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from school_ai.database.models import (
    Activity,
    Room,
    StudentGroup,
    Teacher,
    TeacherAvailability,
)


def test_all_domain_tables_are_created(session: Session) -> None:
    assert set(inspect(session.bind).get_table_names()) == {
        "activities",
        "rooms",
        "student_groups",
        "teacher_availability",
        "teachers",
    }


def test_models_persist_with_relationships(session: Session) -> None:
    teacher = Teacher(name="Ms Lim")
    group = StudentGroup(name="Class 7A", size=28)
    room = Room(name="Science Lab", capacity=32, room_type="laboratory")
    activity = Activity(
        name="Chemistry",
        student_group=group,
        teacher=teacher,
        sessions_per_week=3,
        duration_minutes=60,
        required_room_type="laboratory",
    )
    availability = TeacherAvailability(
        teacher=teacher,
        weekday=0,
        start_time=time(8, 0),
        end_time=time(16, 0),
        available=True,
    )
    session.add_all([room, activity, availability])
    session.commit()

    stored = session.scalar(select(Activity).where(Activity.name == "Chemistry"))
    assert stored is not None
    assert stored.teacher.name == "Ms Lim"
    assert stored.student_group.name == "Class 7A"
    assert stored.teacher.availability[0].start_time == time(8, 0)
    assert session.scalar(select(Room)).capacity == 32


def test_availability_defaults_to_available(session: Session) -> None:
    teacher = Teacher(name="Mr Tan")
    slot = TeacherAvailability(
        teacher=teacher,
        weekday=2,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    session.add(slot)
    session.commit()

    assert slot.available is True
