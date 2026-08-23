from collections import Counter
from datetime import time

import pytest
from pydantic import ValidationError

from school_ai.solver import (
    ActivityInput,
    Assignment,
    AvailabilityWindow,
    RoomInput,
    SchedulingProblem,
    SolveStatus,
    SolverResult,
    StudentGroupInput,
    TeacherInput,
    TimeSlot,
    solve,
)
from school_ai.solver import engine as solver_engine


@pytest.fixture
def feasible_problem() -> SchedulingProblem:
    return SchedulingProblem(
        teachers=(TeacherInput(id=1), TeacherInput(id=2)),
        student_groups=(
            StudentGroupInput(id=1, size=24),
            StudentGroupInput(id=2, size=18),
        ),
        rooms=(
            RoomInput(id=1, capacity=30, room_type="classroom"),
            RoomInput(id=2, capacity=20, room_type="classroom"),
        ),
        activities=(
            ActivityInput(
                id=1,
                teacher_id=1,
                student_group_id=1,
                sessions_per_week=1,
                duration_minutes=60,
                required_room_type="classroom",
            ),
            ActivityInput(
                id=2,
                teacher_id=2,
                student_group_id=2,
                sessions_per_week=1,
                duration_minutes=60,
                required_room_type="classroom",
            ),
        ),
        time_slots=(
            TimeSlot(id=1, weekday=0, start_time=time(8), end_time=time(9)),
            TimeSlot(id=2, weekday=0, start_time=time(9), end_time=time(10)),
        ),
    )


def _activity(
    identifier: int,
    *,
    teacher_id: int,
    student_group_id: int,
    sessions_per_week: int = 1,
) -> ActivityInput:
    return ActivityInput(
        id=identifier,
        teacher_id=teacher_id,
        student_group_id=student_group_id,
        sessions_per_week=sessions_per_week,
        duration_minutes=60,
        required_room_type="classroom",
    )


def _one_slot(problem: SchedulingProblem) -> tuple[TimeSlot, ...]:
    return (problem.time_slots[0],)


def test_feasible_schedule_returns_structured_result(
    feasible_problem: SchedulingProblem,
) -> None:
    result = solve(feasible_problem)

    assert result.status is SolveStatus.OPTIMAL
    assert len(result.assignments) == 2
    assert result.solve_duration_seconds >= 0
    assert result.objective_value is None
    assert result.metadata["candidate_count"] > 0
    assert result.metadata["solver_status"] == "OPTIMAL"


def test_teacher_cannot_be_double_booked(
    feasible_problem: SchedulingProblem,
) -> None:
    problem = feasible_problem.model_copy(
        update={
            "activities": (
                _activity(1, teacher_id=1, student_group_id=1),
                _activity(2, teacher_id=1, student_group_id=2),
            ),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_student_group_cannot_be_double_booked(
    feasible_problem: SchedulingProblem,
) -> None:
    problem = feasible_problem.model_copy(
        update={
            "activities": (
                _activity(1, teacher_id=1, student_group_id=1),
                _activity(2, teacher_id=2, student_group_id=1),
            ),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_room_cannot_be_double_booked(feasible_problem: SchedulingProblem) -> None:
    problem = feasible_problem.model_copy(
        update={
            "rooms": (feasible_problem.rooms[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_teacher_unavailability_is_respected(
    feasible_problem: SchedulingProblem,
) -> None:
    unavailable_teacher = TeacherInput(
        id=1,
        availability=(
            AvailabilityWindow(
                weekday=0,
                start_time=time(8),
                end_time=time(9),
                available=False,
            ),
        ),
    )
    problem = feasible_problem.model_copy(
        update={
            "teachers": (unavailable_teacher, feasible_problem.teachers[1]),
            "activities": (feasible_problem.activities[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_room_unavailability_is_respected(
    feasible_problem: SchedulingProblem,
) -> None:
    unavailable_rooms = tuple(
        room.model_copy(
            update={
                "availability": (
                    AvailabilityWindow(
                        weekday=0,
                        start_time=time(8),
                        end_time=time(9),
                        available=False,
                    ),
                )
            }
        )
        for room in feasible_problem.rooms
    )
    problem = feasible_problem.model_copy(
        update={
            "rooms": unavailable_rooms,
            "activities": (feasible_problem.activities[1],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_all_required_sessions_are_scheduled(
    feasible_problem: SchedulingProblem,
) -> None:
    activity = _activity(
        1, teacher_id=1, student_group_id=1, sessions_per_week=2
    )
    problem = feasible_problem.model_copy(update={"activities": (activity,)})

    result = solve(problem)

    assert result.status is SolveStatus.OPTIMAL
    assert Counter(item.activity_id for item in result.assignments) == {1: 2}
    assert {item.session_index for item in result.assignments} == {0, 1}


def test_room_capacity_is_respected(feasible_problem: SchedulingProblem) -> None:
    undersized = RoomInput(id=1, capacity=10, room_type="classroom")
    problem = feasible_problem.model_copy(
        update={
            "rooms": (undersized,),
            "activities": (feasible_problem.activities[0],),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_solver_uses_a_room_with_sufficient_capacity(
    feasible_problem: SchedulingProblem,
) -> None:
    problem = feasible_problem.model_copy(
        update={"activities": (feasible_problem.activities[0],)}
    )

    result = solve(problem)

    assert result.status is SolveStatus.OPTIMAL
    assert result.assignments[0].room_id == 1


def test_impossible_problem_returns_infeasible_cleanly(
    feasible_problem: SchedulingProblem,
) -> None:
    problem = feasible_problem.model_copy(update={"rooms": ()})

    result = solve(problem)

    assert result.status is SolveStatus.INFEASIBLE
    assert result.assignments == ()
    assert result.objective_value is None


def test_every_assignment_satisfies_all_hard_constraints(
    feasible_problem: SchedulingProblem,
) -> None:
    teacher_window = AvailabilityWindow(
        weekday=0, start_time=time(8), end_time=time(10)
    )
    room_window = AvailabilityWindow(
        weekday=0, start_time=time(8), end_time=time(10)
    )
    problem = feasible_problem.model_copy(
        update={
            "teachers": tuple(
                teacher.model_copy(update={"availability": (teacher_window,)})
                for teacher in feasible_problem.teachers
            ),
            "rooms": tuple(
                room.model_copy(update={"availability": (room_window,)})
                for room in feasible_problem.rooms
            ),
        }
    )

    result = solve(problem)
    assert result.status is SolveStatus.OPTIMAL

    activities = {item.id: item for item in problem.activities}
    groups = {item.id: item for item in problem.student_groups}
    rooms = {item.id: item for item in problem.rooms}
    expected_sessions = {
        activity.id: activity.sessions_per_week for activity in problem.activities
    }
    assert Counter(item.activity_id for item in result.assignments) == expected_sessions

    for assignment in result.assignments:
        activity = activities[assignment.activity_id]
        room = rooms[assignment.room_id]
        assert assignment.teacher_id == activity.teacher_id
        assert assignment.student_group_id == activity.student_group_id
        assert room.capacity >= groups[activity.student_group_id].size
        assert room.room_type == activity.required_room_type
        assert teacher_window.start_time <= assignment.start_time
        assert assignment.end_time <= teacher_window.end_time
        assert room_window.start_time <= assignment.start_time
        assert assignment.end_time <= room_window.end_time

    for index, left in enumerate(result.assignments):
        for right in result.assignments[index + 1 :]:
            overlaps = (
                left.weekday == right.weekday
                and left.start_time < right.end_time
                and right.start_time < left.end_time
            )
            if overlaps:
                assert left.teacher_id != right.teacher_id
                assert left.student_group_id != right.student_group_id
                assert left.room_id != right.room_id


@pytest.mark.parametrize(
    ("collection_name", "duplicate_item"),
    (
        ("teachers", TeacherInput(id=1)),
        ("student_groups", StudentGroupInput(id=1, size=10)),
        ("rooms", RoomInput(id=1, capacity=10, room_type="classroom")),
        (
            "activities",
            ActivityInput(
                id=1,
                teacher_id=1,
                student_group_id=1,
                sessions_per_week=1,
                duration_minutes=60,
                required_room_type="classroom",
            ),
        ),
        (
            "time_slots",
            TimeSlot(id=1, weekday=1, start_time=time(10), end_time=time(11)),
        ),
    ),
)
def test_problem_rejects_duplicate_ids(
    feasible_problem: SchedulingProblem,
    collection_name: str,
    duplicate_item: object,
) -> None:
    data = feasible_problem.model_dump()
    data[collection_name] = (*data[collection_name], duplicate_item)

    with pytest.raises(ValidationError, match="duplicate .* id"):
        SchedulingProblem.model_validate(data)


@pytest.mark.parametrize(
    ("reference_name", "unknown_id"),
    (("teacher_id", 999), ("student_group_id", 999)),
)
def test_problem_rejects_unknown_activity_references(
    feasible_problem: SchedulingProblem,
    reference_name: str,
    unknown_id: int,
) -> None:
    data = feasible_problem.model_dump()
    data["activities"][0][reference_name] = unknown_id

    with pytest.raises(ValidationError, match=f"unknown {reference_name} {unknown_id}"):
        SchedulingProblem.model_validate(data)


@pytest.mark.parametrize(
    "collection_name",
    ("teachers", "student_groups", "rooms", "activities", "time_slots"),
)
def test_problem_rejects_empty_scheduling_collections(
    feasible_problem: SchedulingProblem,
    collection_name: str,
) -> None:
    data = feasible_problem.model_dump()
    data[collection_name] = []

    with pytest.raises(ValidationError, match="at least 1 item"):
        SchedulingProblem.model_validate(data)


def test_problem_rejects_non_finite_solve_limit(
    feasible_problem: SchedulingProblem,
) -> None:
    data = feasible_problem.model_dump()
    data["max_solve_seconds"] = float("nan")

    with pytest.raises(ValidationError, match="finite number"):
        SchedulingProblem.model_validate(data)


def test_no_availability_records_are_unrestricted(
    feasible_problem: SchedulingProblem,
) -> None:
    problem = feasible_problem.model_copy(
        update={"activities": (feasible_problem.activities[0],)}
    )

    assert solve(problem).status is SolveStatus.OPTIMAL


def test_available_windows_are_a_global_weekday_whitelist(
    feasible_problem: SchedulingProblem,
) -> None:
    teacher = TeacherInput(
        id=1,
        availability=(
            AvailabilityWindow(weekday=1, start_time=time(8), end_time=time(10)),
        ),
    )
    problem = feasible_problem.model_copy(
        update={
            "teachers": (teacher,),
            "activities": (feasible_problem.activities[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    result = solve(problem)

    assert result.status is SolveStatus.INFEASIBLE
    assert result.metadata["candidate_count"] == 0


def test_session_must_fit_completely_inside_whitelist_window(
    feasible_problem: SchedulingProblem,
) -> None:
    teacher = TeacherInput(
        id=1,
        availability=(
            AvailabilityWindow(weekday=0, start_time=time(8, 30), end_time=time(10)),
        ),
    )
    problem = feasible_problem.model_copy(
        update={
            "teachers": (teacher,),
            "activities": (feasible_problem.activities[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_blackout_takes_precedence_over_overlapping_whitelist(
    feasible_problem: SchedulingProblem,
) -> None:
    teacher = TeacherInput(
        id=1,
        availability=(
            AvailabilityWindow(weekday=0, start_time=time(8), end_time=time(10)),
            AvailabilityWindow(
                weekday=0,
                start_time=time(8, 30),
                end_time=time(9, 30),
                available=False,
            ),
        ),
    )
    problem = feasible_problem.model_copy(
        update={
            "teachers": (teacher,),
            "activities": (feasible_problem.activities[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


def test_blackout_on_another_weekday_does_not_restrict_session(
    feasible_problem: SchedulingProblem,
) -> None:
    teacher = TeacherInput(
        id=1,
        availability=(
            AvailabilityWindow(
                weekday=1,
                start_time=time(8),
                end_time=time(9),
                available=False,
            ),
        ),
    )
    problem = feasible_problem.model_copy(
        update={
            "teachers": (teacher,),
            "activities": (feasible_problem.activities[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    assert solve(problem).status is SolveStatus.OPTIMAL


def test_activity_may_match_slot_and_availability_boundaries_exactly(
    feasible_problem: SchedulingProblem,
) -> None:
    boundary = AvailabilityWindow(weekday=0, start_time=time(8), end_time=time(9))
    problem = feasible_problem.model_copy(
        update={
            "teachers": (TeacherInput(id=1, availability=(boundary,)),),
            "rooms": (
                RoomInput(
                    id=1,
                    capacity=30,
                    room_type="classroom",
                    availability=(boundary,),
                ),
            ),
            "activities": (feasible_problem.activities[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    result = solve(problem)

    assert result.status is SolveStatus.OPTIMAL
    assert result.assignments[0].start_time == time(8)
    assert result.assignments[0].end_time == time(9)


def test_activity_longer_than_slot_has_no_candidate(
    feasible_problem: SchedulingProblem,
) -> None:
    activity = feasible_problem.activities[0].model_copy(
        update={"duration_minutes": 61}
    )
    problem = feasible_problem.model_copy(
        update={"activities": (activity,), "time_slots": _one_slot(feasible_problem)}
    )

    result = solve(problem)

    assert result.status is SolveStatus.INFEASIBLE
    assert result.metadata["candidate_count"] == 0


def test_time_slots_reject_cross_day_ranges() -> None:
    with pytest.raises(ValidationError, match="start_time must be before end_time"):
        TimeSlot(id=1, weekday=0, start_time=time(23, 30), end_time=time(0, 30))


@pytest.mark.parametrize("resource", ("teacher", "student_group", "room"))
def test_partially_overlapping_slot_ids_conflict(
    feasible_problem: SchedulingProblem,
    resource: str,
) -> None:
    teacher_ids = (1, 1) if resource == "teacher" else (1, 2)
    group_ids = (1, 1) if resource == "student_group" else (1, 2)
    rooms = (
        (feasible_problem.rooms[0],)
        if resource == "room"
        else feasible_problem.rooms
    )
    activities = tuple(
        _activity(
            index + 1,
            teacher_id=teacher_ids[index],
            student_group_id=group_ids[index],
        )
        for index in range(2)
    )
    slots = (
        TimeSlot(id=1, weekday=0, start_time=time(8), end_time=time(9)),
        TimeSlot(id=2, weekday=0, start_time=time(8, 30), end_time=time(9, 30)),
    )
    problem = feasible_problem.model_copy(
        update={"rooms": rooms, "activities": activities, "time_slots": slots}
    )

    assert solve(problem).status is SolveStatus.INFEASIBLE


@pytest.mark.parametrize("reason", ("teacher", "room", "capacity", "room_type"))
def test_impossible_candidates_are_filtered_before_modeling(
    feasible_problem: SchedulingProblem,
    reason: str,
) -> None:
    blackout = AvailabilityWindow(
        weekday=0, start_time=time(8), end_time=time(9), available=False
    )
    teacher = (
        TeacherInput(id=1, availability=(blackout,))
        if reason == "teacher"
        else TeacherInput(id=1)
    )
    room = RoomInput(
        id=1,
        capacity=10 if reason == "capacity" else 30,
        room_type="laboratory" if reason == "room_type" else "classroom",
        availability=(blackout,) if reason == "room" else (),
    )
    problem = feasible_problem.model_copy(
        update={
            "teachers": (teacher,),
            "rooms": (room,),
            "activities": (feasible_problem.activities[0],),
            "time_slots": _one_slot(feasible_problem),
        }
    )

    result = solve(problem)

    assert result.status is SolveStatus.INFEASIBLE
    assert result.metadata["candidate_count"] == 0


def test_unknown_status_is_distinct_and_returns_no_assignments(
    feasible_problem: SchedulingProblem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnknownSolver:
        wall_time = 0.25
        num_conflicts = 0
        num_branches = 0

        class response_proto:
            deterministic_time = 0.0

        def __init__(self) -> None:
            self.parameters = type("Parameters", (), {})()

        def solve(self, model: object) -> int:
            return solver_engine.cp_model.UNKNOWN

        def status_name(self, status: int) -> str:
            return "UNKNOWN"

    monkeypatch.setattr(solver_engine.cp_model, "CpSolver", UnknownSolver)

    result = solver_engine.solve(feasible_problem)

    assert result.status is SolveStatus.UNKNOWN
    assert result.assignments == ()
    assert result.solve_duration_seconds == 0.25
    assert result.metadata["solver_status"] == "UNKNOWN"


def test_unsolved_result_dto_rejects_assignments() -> None:
    assignment = Assignment(
        activity_id=1,
        session_index=0,
        teacher_id=1,
        student_group_id=1,
        room_id=1,
        time_slot_id=1,
        weekday=0,
        start_time=time(8),
        end_time=time(9),
    )

    with pytest.raises(ValidationError, match="cannot contain assignments"):
        SolverResult(
            status=SolveStatus.INFEASIBLE,
            assignments=(assignment,),
            solve_duration_seconds=0,
        )


def test_feasible_result_dto_can_contain_assignments() -> None:
    assignment = Assignment(
        activity_id=1,
        session_index=0,
        teacher_id=1,
        student_group_id=1,
        room_id=1,
        time_slot_id=1,
        weekday=0,
        start_time=time(8),
        end_time=time(9),
    )

    result = SolverResult(
        status=SolveStatus.FEASIBLE,
        assignments=(assignment,),
        solve_duration_seconds=0,
    )

    assert result.assignments == (assignment,)


def test_result_rejects_non_finite_duration() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        SolverResult(
            status=SolveStatus.UNKNOWN,
            solve_duration_seconds=float("nan"),
        )
