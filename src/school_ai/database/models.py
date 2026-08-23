"""Core school domain persistence models."""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from school_ai.database.base import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    activities: Mapped[list[Activity]] = relationship(back_populates="teacher")
    availability: Mapped[list[TeacherAvailability]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (CheckConstraint("capacity > 0", name="ck_rooms_capacity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    room_type: Mapped[str] = mapped_column(String(100), nullable=False)

    availability: Mapped[list[RoomAvailability]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )


class StudentGroup(Base):
    __tablename__ = "student_groups"
    __table_args__ = (CheckConstraint("size > 0", name="ck_student_groups_size_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    size: Mapped[int] = mapped_column(nullable=False)

    activities: Mapped[list[Activity]] = relationship(back_populates="student_group")


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            "sessions_per_week > 0", name="ck_activities_sessions_per_week_positive"
        ),
        CheckConstraint(
            "duration_minutes > 0", name="ck_activities_duration_minutes_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    student_group_id: Mapped[int] = mapped_column(
        ForeignKey("student_groups.id"), nullable=False, index=True
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"), nullable=False, index=True
    )
    sessions_per_week: Mapped[int] = mapped_column(nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    required_room_type: Mapped[str] = mapped_column(String(100), nullable=False)

    student_group: Mapped[StudentGroup] = relationship(back_populates="activities")
    teacher: Mapped[Teacher] = relationship(back_populates="activities")


class TeacherAvailability(Base):
    __tablename__ = "teacher_availability"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_availability_weekday"),
        CheckConstraint("start_time < end_time", name="ck_availability_time_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    teacher: Mapped[Teacher] = relationship(back_populates="availability")


class RoomAvailability(Base):
    __tablename__ = "room_availability"
    __table_args__ = (
        CheckConstraint(
            "weekday >= 0 AND weekday <= 6", name="ck_room_availability_weekday"
        ),
        CheckConstraint(
            "start_time < end_time", name="ck_room_availability_time_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    room: Mapped[Room] = relationship(back_populates="availability")


class ScheduleVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"


class Schedule(Base):
    """Logical timetable identity whose history is stored as versions."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    versions: Mapped[list[ScheduleVersion]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleVersion.version_number",
    )


class ScheduleVersion(Base):
    """Immutable lesson snapshot until an explicit publication transition."""

    __tablename__ = "schedule_versions"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id", "version_number", name="uq_schedule_version_number"
        ),
        CheckConstraint(
            "version_number > 0", name="ck_schedule_versions_number_positive"
        ),
        Index(
            "uq_schedule_one_published_version",
            "schedule_id",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED'"),
            sqlite_where=text("status = 'PUBLISHED'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("schedules.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ScheduleVersionStatus] = mapped_column(
        Enum(ScheduleVersionStatus, native_enum=False, length=20),
        nullable=False,
        default=ScheduleVersionStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    solver_status: Mapped[str] = mapped_column(String(20), nullable=False)
    solve_duration_seconds: Mapped[float] = mapped_column(nullable=False)
    solver_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    schedule: Mapped[Schedule] = relationship(back_populates="versions")
    lessons: Mapped[list[ScheduledLesson]] = relationship(
        back_populates="schedule_version",
        cascade="all, delete-orphan",
        order_by="ScheduledLesson.id",
    )


class ScheduledLesson(Base):
    """One persisted assignment in a schedule-version snapshot."""

    __tablename__ = "scheduled_lessons"
    __table_args__ = (
        UniqueConstraint(
            "schedule_version_id",
            "activity_id",
            "session_index",
            name="uq_scheduled_lesson_session",
        ),
        CheckConstraint(
            "session_index >= 0", name="ck_scheduled_lessons_session_nonnegative"
        ),
        CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_scheduled_lessons_weekday",
        ),
        CheckConstraint(
            "start_time < end_time", name="ck_scheduled_lessons_time_range"
        ),
        CheckConstraint(
            "duration_minutes > 0", name="ck_scheduled_lessons_duration_positive"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_version_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_versions.id"), nullable=False, index=True
    )
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id"), nullable=False, index=True
    )
    session_index: Mapped[int] = mapped_column(nullable=False)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id"), nullable=False, index=True
    )
    student_group_id: Mapped[int] = mapped_column(
        ForeignKey("student_groups.id"), nullable=False, index=True
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id"), nullable=False, index=True
    )
    time_slot_id: Mapped[int] = mapped_column(nullable=False)
    weekday: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)

    schedule_version: Mapped[ScheduleVersion] = relationship(
        back_populates="lessons"
    )
    activity: Mapped[Activity] = relationship()
    teacher: Mapped[Teacher] = relationship()
    student_group: Mapped[StudentGroup] = relationship()
    room: Mapped[Room] = relationship()
