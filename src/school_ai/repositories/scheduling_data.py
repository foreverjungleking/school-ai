"""Queries for the domain data required to build a scheduling problem."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from school_ai.database.models import Activity, Room, StudentGroup, Teacher


@dataclass(frozen=True)
class SchedulingData:
    teachers: tuple[Teacher, ...]
    student_groups: tuple[StudentGroup, ...]
    rooms: tuple[Room, ...]
    activities: tuple[Activity, ...]


class SchedulingDataRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self) -> SchedulingData:
        teachers = self._session.scalars(
            select(Teacher)
            .options(selectinload(Teacher.availability))
            .order_by(Teacher.id)
        ).all()
        groups = self._session.scalars(
            select(StudentGroup).order_by(StudentGroup.id)
        ).all()
        rooms = self._session.scalars(
            select(Room)
            .options(selectinload(Room.availability))
            .order_by(Room.id)
        ).all()
        activities = self._session.scalars(
            select(Activity).order_by(Activity.id)
        ).all()
        return SchedulingData(
            teachers=tuple(teachers),
            student_groups=tuple(groups),
            rooms=tuple(rooms),
            activities=tuple(activities),
        )
