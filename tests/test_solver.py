from collections import Counter
from datetime import time

import pytest

from school_ai.solver import (
    ActivityInput,
    AvailabilityWindow,
    RoomInput,
    SchedulingProblem,
    SolveStatus,
    StudentGroupInput,
    TeacherInput,
    TimeSlot,
    solve,
)


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
