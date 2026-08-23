"""Schedule lifecycle orchestration across repositories and the CP-SAT engine."""

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import math

from school_ai.database.models import (
    RoomAvailability,
    Schedule,
    ScheduledLesson,
    ScheduleVersion,
    ScheduleVersionStatus,
    TeacherAvailability,
)
from school_ai.repositories import ScheduleRepository, SchedulingDataRepository
from school_ai.repositories.scheduling_data import SchedulingData
from school_ai.services.dto import (
    GenerateScheduleResult,
    LessonChange,
    ScheduleSummary,
    ScheduledLessonView,
    ScheduleVersionComparison,
    ScheduleVersionView,
)
from school_ai.solver import (
    ActivityInput,
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

Solver = Callable[[SchedulingProblem], SolverResult]


class ScheduleNotFoundError(LookupError):
    pass


class ScheduleVersionNotFoundError(LookupError):
    pass


class InvalidScheduleTransitionError(ValueError):
    pass


def _availability(
    records: Sequence[TeacherAvailability | RoomAvailability],
) -> tuple[AvailabilityWindow, ...]:
    return tuple(
        AvailabilityWindow(
            weekday=record.weekday,
            start_time=record.start_time,
            end_time=record.end_time,
            available=record.available,
        )
        for record in records
    )


def build_scheduling_problem(
    data: SchedulingData,
    time_slots: tuple[TimeSlot, ...],
    max_solve_seconds: float,
) -> SchedulingProblem:
    """Translate persisted school data into the solver's in-memory boundary."""

    return SchedulingProblem(
        teachers=tuple(
            TeacherInput(id=item.id, availability=_availability(item.availability))
            for item in data.teachers
        ),
        student_groups=tuple(
            StudentGroupInput(id=item.id, size=item.size)
            for item in data.student_groups
        ),
        rooms=tuple(
            RoomInput(
                id=item.id,
                capacity=item.capacity,
                room_type=item.room_type,
                availability=_availability(item.availability),
            )
            for item in data.rooms
        ),
        activities=tuple(
            ActivityInput(
                id=item.id,
                teacher_id=item.teacher_id,
                student_group_id=item.student_group_id,
                sessions_per_week=item.sessions_per_week,
                duration_minutes=item.duration_minutes,
                required_room_type=item.required_room_type,
            )
            for item in data.activities
        ),
        time_slots=time_slots,
        max_solve_seconds=max_solve_seconds,
    )


def _lesson_view(lesson: ScheduledLesson) -> ScheduledLessonView:
    return ScheduledLessonView(
        id=lesson.id,
        activity_id=lesson.activity_id,
        session_index=lesson.session_index,
        teacher_id=lesson.teacher_id,
        student_group_id=lesson.student_group_id,
        room_id=lesson.room_id,
        time_slot_id=lesson.time_slot_id,
        weekday=lesson.weekday,
        start_time=lesson.start_time,
        end_time=lesson.end_time,
        duration_minutes=lesson.duration_minutes,
    )


def _version_view(version: ScheduleVersion) -> ScheduleVersionView:
    return ScheduleVersionView(
        id=version.id,
        schedule_id=version.schedule_id,
        version_number=version.version_number,
        status=version.status,
        created_at=version.created_at,
        published_at=version.published_at,
        solver_status=SolveStatus(version.solver_status),
        solve_duration_seconds=version.solve_duration_seconds,
        solver_metadata=dict(version.solver_metadata),
        lessons=tuple(_lesson_view(item) for item in version.lessons),
    )


class SchedulingService:
    def __init__(
        self,
        schedule_repository: ScheduleRepository,
        data_repository: SchedulingDataRepository,
        solver: Solver = solve,
        max_solve_seconds: float = 30.0,
    ) -> None:
        if not math.isfinite(max_solve_seconds) or max_solve_seconds <= 0:
            raise ValueError("max_solve_seconds must be a positive finite number")
        self._schedules = schedule_repository
        self._data = data_repository
        self._solver = solver
        self._max_solve_seconds = max_solve_seconds

    def create_schedule(self, name: str) -> ScheduleSummary:
        if not name.strip():
            raise ValueError("schedule name must not be blank")
        try:
            schedule = self._schedules.create_schedule(name.strip())
            self._schedules.commit()
        except Exception:
            self._schedules.rollback()
            raise
        return ScheduleSummary(id=schedule.id, name=schedule.name)

    def generate_schedule_draft(
        self,
        schedule_id: int,
        time_slots: tuple[TimeSlot, ...],
        max_solve_seconds: float = 10.0,
    ) -> GenerateScheduleResult:
        schedule = self._require_schedule(schedule_id)
        data = self._data.load()
        problem = build_scheduling_problem(
            data, time_slots, min(max_solve_seconds, self._max_solve_seconds)
        )
        result = self._solver(problem)
        if result.status not in (SolveStatus.FEASIBLE, SolveStatus.OPTIMAL):
            return GenerateScheduleResult(
                solver_status=result.status,
                solve_duration_seconds=result.solve_duration_seconds,
                solver_metadata=dict(result.metadata),
                message="solver did not produce a valid schedule",
            )
        if not result.assignments:
            return GenerateScheduleResult(
                solver_status=result.status,
                solve_duration_seconds=result.solve_duration_seconds,
                solver_metadata=dict(result.metadata),
                message="solver returned no assignments",
            )

        durations = {item.id: item.duration_minutes for item in data.activities}
        try:
            version = self._schedules.create_version(schedule, result)
            self._schedules.add_lessons(version, result.assignments, durations)
            self._schedules.commit()
        except Exception:
            self._schedules.rollback()
            raise
        return GenerateScheduleResult(
            solver_status=result.status,
            solve_duration_seconds=result.solve_duration_seconds,
            version=_version_view(version),
            solver_metadata=dict(result.metadata),
            message="draft schedule version created",
        )

    def get_schedule(self, schedule_id: int) -> ScheduleSummary:
        schedule = self._require_schedule(schedule_id)
        draft = self._schedules.get_latest_draft(schedule_id)
        published = self._schedules.get_published(schedule_id)
        return ScheduleSummary(
            id=schedule.id,
            name=schedule.name,
            latest_draft_version_id=draft.id if draft else None,
            published_version_id=published.id if published else None,
        )

    def get_schedule_version(
        self, version_id: int, schedule_id: int | None = None
    ) -> ScheduleVersionView:
        version = self._require_version(version_id)
        self._validate_version_schedule(version, schedule_id)
        return _version_view(version)

    def get_published_schedule_version(
        self, schedule_id: int
    ) -> ScheduleVersionView:
        self._require_schedule(schedule_id)
        version = self._schedules.get_published(schedule_id)
        if version is None:
            raise ScheduleVersionNotFoundError(
                f"schedule {schedule_id} has no published version"
            )
        return _version_view(version)

    def list_schedule_versions(
        self, schedule_id: int
    ) -> tuple[ScheduleVersionView, ...]:
        self._require_schedule(schedule_id)
        return tuple(
            _version_view(item) for item in self._schedules.list_versions(schedule_id)
        )

    def publish_schedule_version(
        self, version_id: int, schedule_id: int | None = None
    ) -> ScheduleVersionView:
        version = self._require_version(version_id)
        self._validate_version_schedule(version, schedule_id)
        if version.status != ScheduleVersionStatus.DRAFT:
            raise InvalidScheduleTransitionError(
                "only a draft schedule version can be published"
            )
        try:
            published = self._schedules.get_published(version.schedule_id)
            if published is not None:
                published.status = ScheduleVersionStatus.SUPERSEDED
                self._schedules.flush()
            version.status = ScheduleVersionStatus.PUBLISHED
            version.published_at = datetime.now(timezone.utc)
            self._schedules.commit()
        except Exception:
            self._schedules.rollback()
            raise
        return _version_view(version)

    def compare_schedule_versions(
        self,
        from_version_id: int,
        to_version_id: int,
        schedule_id: int | None = None,
    ) -> ScheduleVersionComparison:
        before = self._require_version(from_version_id)
        after = self._require_version(to_version_id)
        self._validate_version_schedule(before, schedule_id)
        self._validate_version_schedule(after, schedule_id)
        if before.schedule_id != after.schedule_id:
            raise ValueError("schedule versions must belong to the same schedule")

        before_by_session = {
            (item.activity_id, item.session_index): item for item in before.lessons
        }
        after_by_session = {
            (item.activity_id, item.session_index): item for item in after.lessons
        }
        shared = before_by_session.keys() & after_by_session.keys()
        unchanged = []
        changed = []
        for key in sorted(shared):
            left = _lesson_view(before_by_session[key])
            right = _lesson_view(after_by_session[key])
            if self._same_assignment(left, right):
                unchanged.append(right)
            else:
                changed.append(LessonChange(before=left, after=right))

        return ScheduleVersionComparison(
            from_version_id=before.id,
            to_version_id=after.id,
            unchanged=tuple(unchanged),
            added=tuple(
                _lesson_view(after_by_session[key])
                for key in sorted(after_by_session.keys() - before_by_session.keys())
            ),
            removed=tuple(
                _lesson_view(before_by_session[key])
                for key in sorted(before_by_session.keys() - after_by_session.keys())
            ),
            changed=tuple(changed),
        )

    def _require_schedule(self, schedule_id: int) -> Schedule:
        schedule = self._schedules.get_schedule(schedule_id)
        if schedule is None:
            raise ScheduleNotFoundError(f"schedule {schedule_id} not found")
        return schedule

    def _require_version(self, version_id: int) -> ScheduleVersion:
        version = self._schedules.get_version(version_id)
        if version is None:
            raise ScheduleVersionNotFoundError(
                f"schedule version {version_id} not found"
            )
        return version

    @staticmethod
    def _validate_version_schedule(
        version: ScheduleVersion, schedule_id: int | None
    ) -> None:
        if schedule_id is not None and version.schedule_id != schedule_id:
            raise ScheduleVersionNotFoundError(
                f"schedule version {version.id} not found for schedule {schedule_id}"
            )

    @staticmethod
    def _same_assignment(
        left: ScheduledLessonView, right: ScheduledLessonView
    ) -> bool:
        return (
            left.teacher_id,
            left.student_group_id,
            left.room_id,
            left.time_slot_id,
            left.weekday,
            left.start_time,
            left.end_time,
            left.duration_minutes,
        ) == (
            right.teacher_id,
            right.student_group_id,
            right.room_id,
            right.time_slot_id,
            right.weekday,
            right.start_time,
            right.end_time,
            right.duration_minutes,
        )
