"""Core school domain persistence models."""

from __future__ import annotations

from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Time
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
