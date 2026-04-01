"""Pydantic schemas for API requests/responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class APIMessage(BaseModel):
    message: str = Field(..., description="Human readable message")


# ---- Auth/User ----
class UserPublic(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    created_at: datetime


class UserCreate(BaseModel):
    email: str = Field(..., description="Unique email address")
    display_name: str = Field(..., description="Display name shown publicly")
    password: str = Field(..., min_length=8, description="Plaintext password (min length 8)")


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: Literal["bearer"] = Field("bearer", description="Token type")


# ---- Events ----
class EventCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: str = Field("", description="Event description/notes")
    location_name: str = Field("", max_length=200)
    latitude: float | None = Field(None, description="Latitude if known")
    longitude: float | None = Field(None, description="Longitude if known")
    starts_at: datetime
    ends_at: datetime | None = None
    capacity: int | None = Field(None, ge=1)


class EventUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = None
    location_name: str | None = Field(None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    capacity: int | None = Field(None, ge=1)
    is_cancelled: bool | None = None


class EventPublic(BaseModel):
    id: int
    organizer_id: int
    title: str
    description: str
    location_name: str
    latitude: float | None
    longitude: float | None
    starts_at: datetime
    ends_at: datetime | None
    capacity: int | None
    is_cancelled: bool
    created_at: datetime
    updated_at: datetime


# ---- RSVP ----
class RSVPPublic(BaseModel):
    id: int
    event_id: int
    user_id: int
    created_at: datetime


# ---- Comments ----
class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


class CommentPublic(BaseModel):
    id: int
    event_id: int
    author_id: int
    body: str
    is_removed: bool
    created_at: datetime


# ---- Messaging ----
class ThreadPublic(BaseModel):
    id: int
    user_a_id: int
    user_b_id: int
    created_at: datetime


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class MessagePublic(BaseModel):
    id: int
    thread_id: int
    sender_id: int
    body: str
    created_at: datetime


# ---- Notifications ----
class NotificationPublic(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    body: str
    is_read: bool
    created_at: datetime


class NotificationMarkRead(BaseModel):
    is_read: bool = Field(..., description="Whether the notification is read")


# ---- Moderation ----
class ReportCreate(BaseModel):
    target_type: Literal["event", "comment", "message", "user"] = Field(..., description="Entity type being reported")
    target_id: int = Field(..., description="ID of entity being reported")
    reason: str = Field(..., min_length=1, max_length=5000)


class ReportPublic(BaseModel):
    id: int
    reporter_id: int
    target_type: str
    target_id: int
    reason: str
    status: str
    moderator_note: str
    created_at: datetime
    resolved_at: datetime | None


class ReportUpdate(BaseModel):
    status: Literal["open", "resolved", "dismissed"] | None = None
    moderator_note: str | None = None


# ---- Analytics ----
class AnalyticsIngest(BaseModel):
    type: str = Field(..., max_length=80, description="Event name, e.g. event_view, rsvp_create")
    event_id: int | None = Field(None, description="Related event id if applicable")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AnalyticsSummary(BaseModel):
    total_events: int
    total_rsvps: int
    total_comments: int
    total_messages: int
    notifications_unread: int
