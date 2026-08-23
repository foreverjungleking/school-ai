"""Read-only persistence operations for school-domain API queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from school_ai.database.models import Activity, Room, StudentGroup, Teacher


class SchoolDataRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_teachers(self) -> list[Teacher]:
        return list(
            self._session.scalars(
                select(Teacher)
                .options(selectinload(Teacher.availability))
                .order_by(Teacher.id)
            ).all()
        )

    def get_teacher(self, teacher_id: int) -> Teacher | None:
        return self._session.scalar(
            select(Teacher)
            .where(Teacher.id == teacher_id)
            .options(selectinload(Teacher.availability))
        )

    def list_rooms(self) -> list[Room]:
        return list(
            self._session.scalars(
                select(Room)
                .options(selectinload(Room.availability))
                .order_by(Room.id)
            ).all()
        )

    def get_room(self, room_id: int) -> Room | None:
        return self._session.scalar(
            select(Room)
            .where(Room.id == room_id)
            .options(selectinload(Room.availability))
        )

    def list_student_groups(self) -> list[StudentGroup]:
        return list(
            self._session.scalars(
                select(StudentGroup).order_by(StudentGroup.id)
            ).all()
        )

    def get_student_group(self, group_id: int) -> StudentGroup | None:
        return self._session.get(StudentGroup, group_id)

    def list_activities(self) -> list[Activity]:
        return list(
            self._session.scalars(select(Activity).order_by(Activity.id)).all()
        )

    def get_activity(self, activity_id: int) -> Activity | None:
        return self._session.get(Activity, activity_id)
