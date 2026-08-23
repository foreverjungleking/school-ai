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
    assert first.teachers == 5
    assert first.rooms == 5
    assert first.student_groups == 4
    assert first.activities == 8
    assert second.created is False
    assert session.scalar(select(func.count(Activity.id))) == 8
    assert session.scalar(select(func.count(TeacherAvailability.id))) == 25
    assert session.scalar(select(func.count(RoomAvailability.id))) == 25


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

    assert result.solver_status is SolveStatus.OPTIMAL
    assert result.version is not None
    assert len(result.version.lessons) == 16
