from collections import Counter
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from school_ai.database.models import Activity, RoomAvailability, TeacherAvailability
from school_ai.demo_seed import seed_demo_data
from school_ai.repositories import ScheduleRepository, SchedulingDataRepository
from school_ai.services import SchedulingService
from school_ai.solver import SolveStatus, TimeSlot


def test_demo_seed_is_synthetic_complete_and_idempotent(session: Session) -> None:
    first = seed_demo_data(session)
    second = seed_demo_data(session)

    assert first.created is True
    assert first.teachers == 8
    assert first.rooms == 7
    assert first.student_groups == 4
    assert first.activities == 32
    assert second.created is False
    assert session.scalar(select(func.count(Activity.id))) == 32
    assert session.scalar(select(func.count(TeacherAvailability.id))) == 80
    assert session.scalar(select(func.count(RoomAvailability.id))) == 70


def test_seeded_demo_data_generates_a_valid_schedule(session: Session) -> None:
    seed_demo_data(session)
    service = SchedulingService(
        ScheduleRepository(session), SchedulingDataRepository(session)
    )
    schedule = service.create_schedule("Synthetic demo timetable")
    slots = tuple(
        TimeSlot(
            id=weekday * 8 + hour - 7,
            weekday=weekday,
            start_time=time(hour),
            end_time=time(hour + 1),
        )
        for weekday in range(5)
        for hour in range(8, 16)
    )

    result = service.generate_schedule_draft(schedule.id, slots)

    assert result.solver_status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)
    assert result.version is not None
    assert len(result.version.lessons) == 100

    lessons = result.version.lessons
    assert Counter(item.student_group_id for item in lessons) == {1: 25, 2: 25, 3: 25, 4: 25}
    for group_id in {item.student_group_id for item in lessons}:
        loads = Counter(item.weekday for item in lessons if item.student_group_id == group_id)
        assert set(loads) == set(range(5))
        assert max(loads.values()) - min(loads.values()) <= 1
    assert all(item.end_time <= time(12) or item.start_time >= time(13) for item in lessons)
    assert all(item.end_time <= time(15) for item in lessons)
    assert max(Counter((item.activity_id, item.weekday) for item in lessons).values()) == 1
    assert result.solver_metadata["objective_value"] == 0
    for index, left in enumerate(lessons):
        for right in lessons[index + 1:]:
            if (left.weekday == right.weekday
                and left.start_time < right.end_time
                and right.start_time < left.end_time):
                assert left.teacher_id != right.teacher_id
                assert left.student_group_id != right.student_group_id
                assert left.room_id != right.room_id


def test_expansion_is_idempotent_and_preserves_versions(session: Session) -> None:
    seed_demo_data(session)
    service = SchedulingService(ScheduleRepository(session), SchedulingDataRepository(session))
    schedule = service.create_schedule("Preserved demo")
    result = service.generate_schedule_draft(schedule.id)
    assert result.version is not None
    before = service.get_schedule_version(result.version.id)
    assert seed_demo_data(session, expand=True).created is False
    assert service.get_schedule_version(result.version.id) == before


def test_legacy_demo_expands_without_changing_published_lessons(session: Session) -> None:
    from school_ai.database.models import Teacher, Room, StudentGroup, ScheduleVersionStatus

    teachers = [Teacher(name=name) for name in (
        "Aisha Rahman", "Daniel Tan", "Mei Lin", "Priya Nair", "Marcus Lee"
    )]
    groups = [StudentGroup(name=name, size=size) for name, size in (
        ("Year 7 Aurora", 26), ("Year 7 Horizon", 24),
        ("Year 8 Summit", 28), ("Year 8 Grove", 22),
    )]
    rooms = [Room(name=name, capacity=capacity, room_type=kind)
             for name, capacity, kind in (
                 ("North 201", 32, "classroom"), ("South 104", 30, "classroom"),
                 ("Discovery Lab", 28, "laboratory"), ("Harmony Studio", 26, "music"),
                 ("Sports Hall", 80, "sports"),
             )]
    activities = [Activity(name=name, teacher=teachers[teacher], student_group=groups[group],
                           sessions_per_week=count, duration_minutes=60, required_room_type=kind)
                  for name, teacher, group, count, kind in (
                      ("Mathematics", 0, 0, 3, "classroom"),
                      ("English", 1, 0, 2, "classroom"),
                      ("Science", 2, 1, 2, "laboratory"),
                      ("Music", 3, 1, 1, "music"),
                      ("Physical Education", 4, 2, 2, "sports"),
                      ("History", 0, 2, 2, "classroom"),
                      ("Computing", 2, 3, 2, "classroom"),
                      ("Visual Arts", 3, 3, 2, "classroom"),
                  )]
    session.add_all([*rooms, *activities])
    session.commit()
    service = SchedulingService(ScheduleRepository(session), SchedulingDataRepository(session))
    schedule = service.create_schedule("Legacy synthetic demo")
    draft = service.generate_schedule_draft(schedule.id)
    assert draft.version is not None
    published = service.publish_schedule_version(draft.version.id)
    assert len(published.lessons) == 16
    assert seed_demo_data(session).created is False
    result = seed_demo_data(session, expand=True)
    assert (result.teachers, result.rooms, result.activities) == (8, 7, 32)
    assert service.get_schedule_version(published.id) == published
    assert service.get_schedule_version(published.id).status is ScheduleVersionStatus.PUBLISHED
    expanded = service.generate_schedule_draft(schedule.id)
    assert expanded.version is not None
    assert len(expanded.version.lessons) == 100
    assert expanded.version.status is ScheduleVersionStatus.DRAFT
    assert seed_demo_data(session, expand=True).created is False


def test_expansion_refuses_non_demo_resources(session: Session) -> None:
    import pytest
    from school_ai.database.models import Teacher

    seed_demo_data(session)
    session.add(Teacher(name="Unrelated resource"))
    session.commit()
    with pytest.raises(RuntimeError, match="known synthetic demo"):
        seed_demo_data(session, expand=True)
    assert session.scalar(select(func.count(Activity.id))) == 32
