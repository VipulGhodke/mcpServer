from __future__ import annotations

import datetime as dt
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def generate_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hearts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    gems: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_active: Mapped[Optional[dt.date]] = mapped_column(Date(), nullable=True)
    learning_language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # e.g., 'de', 'es'
    native_language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)    # e.g., 'en'
    # Adaptive difficulty tracking per user
    current_difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    correct_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Hearts regeneration tracking
    hearts_last_refill_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    lessons: Mapped[List["Lesson"]] = relationship(back_populates="skill")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    lang: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    skill: Mapped["Skill"] = relationship(back_populates="lessons")
    exercises: Mapped[List["Exercise"]] = relationship(back_populates="lesson")


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    choices: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    srs_props: Mapped[dict] = mapped_column(JSON, default=dict)

    lesson: Mapped["Lesson"] = relationship(back_populates="exercises")
    attempts: Mapped[List["Attempt"]] = relationship(back_populates="exercise")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    awarded_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Snapshot difficulty level of the exercise when attempted
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    exercise: Mapped["Exercise"] = relationship(back_populates="attempts")


class StreakLog(Base):
    __tablename__ = "streak_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_streak_day"),
    )


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)


class UserBadge(Base):
    __tablename__ = "user_badges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    badge_id: Mapped[str] = mapped_column(ForeignKey("badges.id"), index=True)
    awarded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
    )


class MediaEvent(Base):
    __tablename__ = "media_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


