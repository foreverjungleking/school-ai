"""Deterministic OR-Tools CP-SAT school scheduling engine."""

from collections import defaultdict
from datetime import time

from ortools.sat.python import cp_model

from school_ai.solver.dto import (
    ActivityInput,
    Assignment,
    AvailabilityWindow,
    SchedulingProblem,
    SolveStatus,
    SolverResult,
    TimeSlot,
)

_MINUTES_PER_DAY = 24 * 60


def _minute_of_day(value: time) -> int:
    return value.hour * 60 + value.minute


def _week_minute(weekday: int, value: time) -> int:
    return weekday * _MINUTES_PER_DAY + _minute_of_day(value)


def _end_time(slot: TimeSlot, duration_minutes: int) -> time:
    end_minute = _minute_of_day(slot.start_time) + duration_minutes
    return time(end_minute // 60, end_minute % 60)


def _fits_slot(activity: ActivityInput, slot: TimeSlot) -> bool:
    return _minute_of_day(slot.start_time) + activity.duration_minutes <= _minute_of_day(
        slot.end_time
    )


def _allowed_by_availability(
    windows: tuple[AvailabilityWindow, ...],
    weekday: int,
    start_minute: int,
    end_minute: int,
) -> bool:
    same_day = [window for window in windows if window.weekday == weekday]
    unavailable = [window for window in same_day if not window.available]
    if any(
        start_minute < _minute_of_day(window.end_time)
        and end_minute > _minute_of_day(window.start_time)
        for window in unavailable
    ):
        return False

    available = [window for window in same_day if window.available]
    if not available:
        return not any(window.available for window in windows)
    return any(
        start_minute >= _minute_of_day(window.start_time)
        and end_minute <= _minute_of_day(window.end_time)
        for window in available
    )


def solve(problem: SchedulingProblem) -> SolverResult:
    """Build and solve a timetable using only hard CP-SAT constraints."""

    model = cp_model.CpModel()
    teachers = {teacher.id: teacher for teacher in problem.teachers}
    groups = {group.id: group for group in problem.student_groups}

    choices: dict[tuple[int, int], list[cp_model.IntVar]] = defaultdict(list)
    candidate_data: dict[
        tuple[int, int, int, int], tuple[cp_model.IntVar, ActivityInput, TimeSlot]
    ] = {}
    teacher_intervals: dict[int, list[cp_model.IntervalVar]] = defaultdict(list)
    group_intervals: dict[int, list[cp_model.IntervalVar]] = defaultdict(list)
    room_intervals: dict[int, list[cp_model.IntervalVar]] = defaultdict(list)

    for activity in problem.activities:
        teacher = teachers[activity.teacher_id]
        group = groups[activity.student_group_id]
        for session_index in range(activity.sessions_per_week):
            session_key = (activity.id, session_index)
            for slot in problem.time_slots:
                start_minute = _minute_of_day(slot.start_time)
                end_minute = start_minute + activity.duration_minutes
                if not _fits_slot(activity, slot) or not _allowed_by_availability(
                    teacher.availability, slot.weekday, start_minute, end_minute
                ):
                    continue

                for room in problem.rooms:
                    if room.capacity < group.size:
                        continue
                    if (
                        activity.required_room_type is not None
                        and room.room_type != activity.required_room_type
                    ):
                        continue
                    if not _allowed_by_availability(
                        room.availability, slot.weekday, start_minute, end_minute
                    ):
                        continue

                    key = (activity.id, session_index, slot.id, room.id)
                    selected = model.new_bool_var(
                        f"assign_a{activity.id}_s{session_index}_t{slot.id}_r{room.id}"
                    )
                    interval = model.new_optional_fixed_size_interval_var(
                        _week_minute(slot.weekday, slot.start_time),
                        activity.duration_minutes,
                        selected,
                        f"interval_a{activity.id}_s{session_index}_t{slot.id}_r{room.id}",
                    )
                    choices[session_key].append(selected)
                    candidate_data[key] = (selected, activity, slot)
                    teacher_intervals[activity.teacher_id].append(interval)
                    group_intervals[activity.student_group_id].append(interval)
                    room_intervals[room.id].append(interval)

            model.add_exactly_one(choices[session_key])

    for intervals in teacher_intervals.values():
        model.add_no_overlap(intervals)
    for intervals in group_intervals.values():
        model.add_no_overlap(intervals)
    for intervals in room_intervals.values():
        model.add_no_overlap(intervals)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = problem.max_solve_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    raw_status = solver.solve(model)
    status = {
        cp_model.OPTIMAL: SolveStatus.OPTIMAL,
        cp_model.FEASIBLE: SolveStatus.FEASIBLE,
        cp_model.INFEASIBLE: SolveStatus.INFEASIBLE,
        cp_model.UNKNOWN: SolveStatus.UNKNOWN,
    }.get(raw_status, SolveStatus.UNKNOWN)

    assignments: list[Assignment] = []
    if status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
        for (activity_id, session_index, slot_id, room_id), (
            selected,
            activity,
            slot,
        ) in candidate_data.items():
            if solver.boolean_value(selected):
                assignments.append(
                    Assignment(
                        activity_id=activity_id,
                        session_index=session_index,
                        teacher_id=activity.teacher_id,
                        student_group_id=activity.student_group_id,
                        room_id=room_id,
                        time_slot_id=slot_id,
                        weekday=slot.weekday,
                        start_time=slot.start_time,
                        end_time=_end_time(slot, activity.duration_minutes),
                    )
                )
        assignments.sort(
            key=lambda item: (
                item.weekday,
                item.start_time,
                item.activity_id,
                item.session_index,
            )
        )

    return SolverResult(
        status=status,
        assignments=tuple(assignments),
        solve_duration_seconds=solver.wall_time,
        objective_value=None,
        metadata={
            "candidate_count": len(candidate_data),
            "conflicts": solver.num_conflicts,
            "branches": solver.num_branches,
            "solver_status": solver.status_name(raw_status),
            "deterministic_time": solver.response_proto.deterministic_time,
        },
    )
