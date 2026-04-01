"""
ORM models for the responsive event platform.

Note: For the purposes of this step, we implement a pragmatic schema that supports:
- auth/users
- events + RSVPs + comments
- messaging (threads + messages)
- notifications
- moderation (reports)
- analytics events

Migrations are not included here; CI will create tables on startup for dev usage.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    moderator = "moderator"


class NotificationType(str, enum.Enum):
    system = "system"
    rsvp = "rsvp"
    comment = "comment"
    message = "message"
    moderation = "moderation"


class ReportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    events: Mapped[list["Event"]] = relationship(back_populates="organizer", cascade="all,delete-orphan")
    rsvps: Mapped[list["RSVP"]] = relationship(back_populates="user", cascade="all,delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="author", cascade="all,delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    location_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    organizer: Mapped["User"] = relationship(back_populates="events")
    rsvps: Mapped[list["RSVP"]] = relationship(back_populates="event", cascade="all,delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="event", cascade="all,delete-orphan")


class RSVP(Base):
    __tablename__ = "rsvps"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_rsvp_event_user"),
        Index("ix_rsvps_event", "event_id"),
        Index("ix_rsvps_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    event: Mapped["Event"] = relationship(back_populates="rsvps")
    user: Mapped["User"] = relationship(back_populates="rsvps")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_event", "event_id"),
        Index("ix_comments_author", "author_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_removed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    event: Mapped["Event"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(back_populates="comments")


class Thread(Base):
    __tablename__ = "threads"
    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_thread_pair"),
        Index("ix_threads_user_a", "user_a_id"),
        Index("ix_threads_user_b", "user_b_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    messages: Mapped[list["Message"]] = relationship(back_populates="thread", cascade="all,delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_thread", "thread_id"),
        Index("ix_messages_sender", "sender_id"),
        Index("ix_messages_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    thread: Mapped["Thread"] = relationship(back_populates="messages")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user", "user_id"),
        Index("ix_notifications_read", "is_read"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), default=NotificationType.system, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_status", "status"),
        Index("ix_reports_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # event|comment|message|user
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.open, nullable=False)
    moderator_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_type", "type"),
        Index("ix_analytics_created", "created_at"),
        Index("ix_analytics_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
