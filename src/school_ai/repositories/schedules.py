"""Focused persistence operations for schedules and their version snapshots."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from school_ai.database.models import (
    Schedule,
    ScheduledLesson,
    ScheduleVersion,
    ScheduleVersionStatus,
)
from school_ai.solver import Assignment, SolverResult


class ScheduleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_schedule(self, name: str) -> Schedule:
        schedule = Schedule(name=name)
        self._session.add(schedule)
        self._session.flush()
        return schedule

    def get_schedule(self, schedule_id: int) -> Schedule | None:
        return self._session.get(Schedule, schedule_id)

    def get_current_schedule(self) -> Schedule | None:
        return self._session.scalar(
            select(Schedule).order_by(Schedule.id.desc()).limit(1)
        )

    def create_version(
        self, schedule: Schedule, solver_result: SolverResult
    ) -> ScheduleVersion:
        latest_number = self._session.scalar(
            select(func.max(ScheduleVersion.version_number)).where(
                ScheduleVersion.schedule_id == schedule.id
            )
        )
        version = ScheduleVersion(
            schedule=schedule,
            version_number=(latest_number or 0) + 1,
            status=ScheduleVersionStatus.DRAFT,
            solver_status=solver_result.status.value,
            solve_duration_seconds=solver_result.solve_duration_seconds,
            solver_metadata=dict(solver_result.metadata),
        )
        self._session.add(version)
        self._session.flush()
        return version

    def add_lessons(
        self,
        version: ScheduleVersion,
        assignments: tuple[Assignment, ...],
        durations_by_activity: dict[int, int],
    ) -> None:
        lessons = [
            ScheduledLesson(
                schedule_version=version,
                activity_id=assignment.activity_id,
                session_index=assignment.session_index,
                teacher_id=assignment.teacher_id,
                student_group_id=assignment.student_group_id,
                room_id=assignment.room_id,
                time_slot_id=assignment.time_slot_id,
                weekday=assignment.weekday,
                start_time=assignment.start_time,
                end_time=assignment.end_time,
                duration_minutes=durations_by_activity[assignment.activity_id],
            )
            for assignment in assignments
        ]
        self._session.add_all(lessons)
        self._session.flush()

    def get_version(self, version_id: int) -> ScheduleVersion | None:
        return self._session.scalar(
            select(ScheduleVersion)
            .where(ScheduleVersion.id == version_id)
            .options(selectinload(ScheduleVersion.lessons))
        )

    def list_versions(self, schedule_id: int) -> list[ScheduleVersion]:
        return list(
            self._session.scalars(
                select(ScheduleVersion)
                .where(ScheduleVersion.schedule_id == schedule_id)
                .options(selectinload(ScheduleVersion.lessons))
                .order_by(ScheduleVersion.version_number)
            ).all()
        )

    def get_latest_draft(self, schedule_id: int) -> ScheduleVersion | None:
        return self._session.scalar(
            select(ScheduleVersion)
            .where(
                ScheduleVersion.schedule_id == schedule_id,
                ScheduleVersion.status == ScheduleVersionStatus.DRAFT,
            )
            .options(selectinload(ScheduleVersion.lessons))
            .order_by(ScheduleVersion.version_number.desc())
            .limit(1)
        )

    def get_published(self, schedule_id: int) -> ScheduleVersion | None:
        return self._session.scalar(
            select(ScheduleVersion)
            .where(
                ScheduleVersion.schedule_id == schedule_id,
                ScheduleVersion.status == ScheduleVersionStatus.PUBLISHED,
            )
            .options(selectinload(ScheduleVersion.lessons))
        )

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
