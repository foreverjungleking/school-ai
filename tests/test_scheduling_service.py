from collections.abc import Callable
from datetime import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from school_ai.database.models import (
    Activity,
    Room,
    ScheduleVersion,
    ScheduleVersionStatus,
    ScheduledLesson,
    StudentGroup,
    Teacher,
)
from school_ai.repositories import ScheduleRepository, SchedulingDataRepository
from school_ai.services.scheduling import (
    InvalidScheduleTransitionError,
    ScheduleNotFoundError,
    SchedulingDataIncompleteError,
    SchedulingService,
)
from school_ai.solver import (
    Assignment,
    SchedulingProblem,
    SolveStatus,
    SolverResult,
    TimeSlot,
)


@pytest.fixture
def school_data(session: Session) -> tuple[Teacher, StudentGroup, Room, Activity]:
    teacher = Teacher(name="Ms Lim")
    group = StudentGroup(name="Class 7A", size=24)
    room = Room(name="Room 101", capacity=30, room_type="classroom")
    activity = Activity(
        name="Mathematics",
        teacher=teacher,
        student_group=group,
        sessions_per_week=1,
        duration_minutes=60,
        required_room_type="classroom",
    )
    session.add_all([room, activity])
    session.commit()
    return teacher, group, room, activity


@pytest.fixture
def time_slots() -> tuple[TimeSlot, ...]:
    return (
        TimeSlot(id=1, weekday=0, start_time=time(8), end_time=time(9)),
        TimeSlot(id=2, weekday=0, start_time=time(9), end_time=time(10)),
    )


def _service(
    session: Session,
    solver: Callable[[SchedulingProblem], SolverResult] | None = None,
) -> SchedulingService:
    arguments = (
        ScheduleRepository(session),
        SchedulingDataRepository(session),
    )
    return (
        SchedulingService(*arguments, solver=solver)
        if solver
        else SchedulingService(*arguments)
    )


def _assignment(
    activity: Activity,
    room: Room,
    *,
    time_slot_id: int = 1,
    start_time: time = time(8),
    end_time: time = time(9),
) -> Assignment:
    return Assignment(
        activity_id=activity.id,
        session_index=0,
        teacher_id=activity.teacher_id,
        student_group_id=activity.student_group_id,
        room_id=room.id,
        time_slot_id=time_slot_id,
        weekday=0,
        start_time=start_time,
        end_time=end_time,
    )


def _successful_result(assignment: Assignment) -> SolverResult:
    return SolverResult(
        status=SolveStatus.OPTIMAL,
        assignments=(assignment,),
        solve_duration_seconds=0.1,
        metadata={"candidate_count": 2, "solver_status": "OPTIMAL"},
    )


def test_generation_reports_missing_master_data(
    session: Session, time_slots: tuple[TimeSlot, ...]
) -> None:
    service = _service(session)
    schedule = service.create_schedule("Empty timetable")

    with pytest.raises(SchedulingDataIncompleteError) as error:
        service.generate_schedule_draft(schedule.id, time_slots)

    assert error.value.missing == (
        "teachers",
        "rooms",
        "student groups",
        "activities",
    )


def test_solver_result_is_persisted_as_complete_draft(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    teacher, group, room, activity = school_data
    service = _service(session)
    schedule = service.create_schedule("2026 timetable")

    result = service.generate_schedule_draft(schedule.id, time_slots)

    assert result.solver_status is SolveStatus.OPTIMAL
    assert result.solve_duration_seconds >= 0
    assert result.version is not None
    assert result.version.status is ScheduleVersionStatus.DRAFT
    assert result.version.version_number == 1
    assert result.version.solver_metadata["candidate_count"] == 2
    assert len(result.version.lessons) == 1
    lesson = result.version.lessons[0]
    assert lesson.activity_id == activity.id
    assert lesson.teacher_id == teacher.id
    assert lesson.student_group_id == group.id
    assert lesson.room_id == room.id
    assert lesson.duration_minutes == activity.duration_minutes

    loaded = service.get_schedule_version(result.version.id)
    assert loaded == result.version
    assert session.scalar(select(func.count(ScheduledLesson.id))) == 1


def test_service_translates_database_domain_data_for_solver(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    teacher, group, room, activity = school_data
    captured: list[SchedulingProblem] = []

    def recording_solver(problem: SchedulingProblem) -> SolverResult:
        captured.append(problem)
        return _successful_result(_assignment(activity, room))

    service = _service(session, recording_solver)
    schedule = service.create_schedule("Translation test")

    service.generate_schedule_draft(schedule.id, time_slots, max_solve_seconds=3)

    problem = captured[0]
    assert problem.max_solve_seconds == 3
    assert problem.teachers[0].id == teacher.id
    assert problem.student_groups[0].size == group.size
    assert problem.rooms[0].capacity == room.capacity
    assert problem.activities[0].duration_minutes == activity.duration_minutes
    assert problem.time_slots == time_slots


def test_service_builds_standard_slots_when_draft_slots_are_omitted(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
) -> None:
    _, _, room, activity = school_data
    captured: list[SchedulingProblem] = []

    def recording_solver(problem: SchedulingProblem) -> SolverResult:
        captured.append(problem)
        return _successful_result(_assignment(activity, room))

    service = _service(session, recording_solver)
    schedule = service.create_schedule("Default slot timetable")

    result = service.generate_schedule_draft(schedule.id)

    assert result.version is not None
    slots = captured[0].time_slots
    assert len(slots) == 40
    assert (slots[0].weekday, slots[0].start_time, slots[0].end_time) == (
        0,
        time(8),
        time(9),
    )
    assert (slots[-1].weekday, slots[-1].start_time, slots[-1].end_time) == (
        4,
        time(15),
        time(16),
    )


def test_service_discovers_newest_demo_schedule(session: Session) -> None:
    service = _service(session)
    service.create_schedule("First timetable")
    second = service.create_schedule("Second timetable")

    current = service.get_current_demo_schedule()

    assert current.id == second.id
    assert current.name == "Second timetable"


def test_current_demo_schedule_requires_an_existing_schedule(session: Session) -> None:
    with pytest.raises(ScheduleNotFoundError, match="no demo schedule"):
        _service(session).get_current_demo_schedule()


def test_service_caps_requested_solver_duration(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    _, _, room, activity = school_data
    captured: list[SchedulingProblem] = []

    def recording_solver(problem: SchedulingProblem) -> SolverResult:
        captured.append(problem)
        return _successful_result(_assignment(activity, room))

    repositories = (ScheduleRepository(session), SchedulingDataRepository(session))
    service = SchedulingService(
        *repositories, solver=recording_solver, max_solve_seconds=4
    )
    schedule = service.create_schedule("Bounded solver")

    service.generate_schedule_draft(schedule.id, time_slots, max_solve_seconds=300)

    assert captured[0].max_solve_seconds == 4


def test_generating_again_creates_a_new_draft_version(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    service = _service(session)
    schedule = service.create_schedule("Versioned timetable")

    first = service.generate_schedule_draft(schedule.id, time_slots)
    second = service.generate_schedule_draft(schedule.id, time_slots)

    assert first.version is not None
    assert second.version is not None
    assert first.version.id != second.version.id
    assert second.version.version_number == 2
    assert [item.version_number for item in service.list_schedule_versions(schedule.id)] == [1, 2]
    repository = ScheduleRepository(session)
    assert repository.get_latest_draft(schedule.id).id == second.version.id


def test_publish_draft_and_supersede_previous_publication(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    service = _service(session)
    schedule = service.create_schedule("Published timetable")
    first = service.generate_schedule_draft(schedule.id, time_slots).version
    second = service.generate_schedule_draft(schedule.id, time_slots).version
    assert first is not None and second is not None

    published_first = service.publish_schedule_version(first.id)
    assert published_first.status is ScheduleVersionStatus.PUBLISHED
    published_second = service.publish_schedule_version(second.id)

    assert published_second.status is ScheduleVersionStatus.PUBLISHED
    assert service.get_schedule_version(first.id).status is ScheduleVersionStatus.SUPERSEDED
    assert ScheduleRepository(session).get_published(schedule.id).id == second.id
    published_count = session.scalar(
        select(func.count(ScheduleVersion.id)).where(
            ScheduleVersion.schedule_id == schedule.id,
            ScheduleVersion.status == ScheduleVersionStatus.PUBLISHED,
        )
    )
    assert published_count == 1


def test_published_version_is_not_modified_in_place(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    service = _service(session)
    schedule = service.create_schedule("Immutable publication")
    first = service.generate_schedule_draft(schedule.id, time_slots).version
    assert first is not None
    published = service.publish_schedule_version(first.id)

    with pytest.raises(InvalidScheduleTransitionError):
        service.publish_schedule_version(first.id)

    second = service.generate_schedule_draft(schedule.id, time_slots).version
    assert second is not None
    assert second.id != published.id
    assert second.status is ScheduleVersionStatus.DRAFT
    reloaded = service.get_schedule_version(published.id)
    assert reloaded.status is ScheduleVersionStatus.PUBLISHED
    assert reloaded.lessons == published.lessons


@pytest.mark.parametrize("status", (SolveStatus.INFEASIBLE, SolveStatus.UNKNOWN))
def test_unsolved_result_does_not_persist_version_or_lessons(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
    status: SolveStatus,
) -> None:
    def unsuccessful_solver(problem: SchedulingProblem) -> SolverResult:
        return SolverResult(
            status=status,
            solve_duration_seconds=0.2,
            metadata={"solver_status": status.value, "diagnostic": "preserved"},
        )

    service = _service(session, unsuccessful_solver)
    schedule = service.create_schedule("Unsolved timetable")

    result = service.generate_schedule_draft(schedule.id, time_slots)

    assert result.solver_status is status
    assert result.solve_duration_seconds == 0.2
    assert result.version is None
    assert result.solver_metadata["diagnostic"] == "preserved"
    assert service.list_schedule_versions(schedule.id) == ()
    assert session.scalar(select(func.count(ScheduledLesson.id))) == 0


def test_assignment_free_solver_success_does_not_persist_a_version(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    def empty_solver(problem: SchedulingProblem) -> SolverResult:
        return SolverResult(
            status=SolveStatus.FEASIBLE,
            solve_duration_seconds=0.1,
            metadata={"solver_status": "FEASIBLE"},
        )

    service = _service(session, empty_solver)
    schedule = service.create_schedule("Empty result timetable")

    result = service.generate_schedule_draft(schedule.id, time_slots)

    assert result.version is None
    assert result.message == "solver returned no assignments"
    assert service.list_schedule_versions(schedule.id) == ()


def test_complete_version_can_be_loaded_with_assignments(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    service = _service(session)
    schedule = service.create_schedule("Reload timetable")
    generated = service.generate_schedule_draft(schedule.id, time_slots).version
    assert generated is not None

    session.expire_all()
    loaded = service.get_schedule_version(generated.id)

    assert loaded.lessons
    assert loaded.lessons[0].activity_id == school_data[3].id


def test_schedule_versions_can_be_compared(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    _, _, room, activity = school_data
    results = iter(
        (
            _successful_result(_assignment(activity, room)),
            _successful_result(
                _assignment(
                    activity,
                    room,
                    time_slot_id=2,
                    start_time=time(9),
                    end_time=time(10),
                )
            ),
        )
    )
    service = _service(session, lambda problem: next(results))
    schedule = service.create_schedule("Comparison timetable")
    first = service.generate_schedule_draft(schedule.id, time_slots).version
    second = service.generate_schedule_draft(schedule.id, time_slots).version
    assert first is not None and second is not None

    comparison = service.compare_schedule_versions(first.id, second.id)

    assert comparison.from_version_id == first.id
    assert comparison.to_version_id == second.id
    assert comparison.unchanged == ()
    assert comparison.added == ()
    assert comparison.removed == ()
    assert len(comparison.changed) == 1
    assert comparison.changed[0].before.start_time == time(8)
    assert comparison.changed[0].after.start_time == time(9)


def test_comparison_reports_added_and_removed_lessons(
    session: Session,
    school_data: tuple[Teacher, StudentGroup, Room, Activity],
    time_slots: tuple[TimeSlot, ...],
) -> None:
    teacher, group, _, _ = school_data
    service = _service(session)
    schedule = service.create_schedule("Added lesson comparison")
    first = service.generate_schedule_draft(schedule.id, time_slots).version
    assert first is not None

    added_activity = Activity(
        name="English",
        teacher=teacher,
        student_group=group,
        sessions_per_week=1,
        duration_minutes=60,
        required_room_type="classroom",
    )
    session.add(added_activity)
    session.commit()
    second = service.generate_schedule_draft(schedule.id, time_slots).version
    assert second is not None

    forward = service.compare_schedule_versions(first.id, second.id)
    reverse = service.compare_schedule_versions(second.id, first.id)

    assert [item.activity_id for item in forward.added] == [added_activity.id]
    assert [item.activity_id for item in reverse.removed] == [added_activity.id]
