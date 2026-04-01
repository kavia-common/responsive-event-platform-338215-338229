from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.schemas import AnalyticsIngest, AnalyticsSummary
from src.auth.dependencies import get_current_user, require_role
from src.db.models import AnalyticsEvent, Comment, Message, Notification, RSVP, User, UserRole
from src.db.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post(
    "/events",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest analytics event",
    description="Store a client analytics event (e.g. event_view).",
    operation_id="analytics_ingest",
)
def ingest(
    payload: AnalyticsIngest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ev = AnalyticsEvent(
        type=payload.type,
        user_id=user.id,
        event_id=payload.event_id,
        metadata_json=json.dumps(payload.metadata),
    )
    db.add(ev)
    db.commit()
    return {"message": "Accepted"}


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="Get analytics summary",
    description="Returns counts for key tables and unread notifications for the current user.",
    operation_id="analytics_summary",
)
def summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalyticsSummary:
    total_rsvps = int(db.scalar(select(func.count()).select_from(RSVP)) or 0)
    total_comments = int(db.scalar(select(func.count()).select_from(Comment)) or 0)
    total_messages = int(db.scalar(select(func.count()).select_from(Message)) or 0)
    unread = int(
        db.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.is_read == False)  # noqa: E712
        )
        or 0
    )

    # total_events is tracked in analytics_events for this minimal summary;
    # admins often want system-level totals for events viewed, etc.
    total_events = int(db.scalar(select(func.count()).select_from(AnalyticsEvent).where(AnalyticsEvent.type == "event_view")) or 0)

    return AnalyticsSummary(
        total_events=total_events,
        total_rsvps=total_rsvps,
        total_comments=total_comments,
        total_messages=total_messages,
        notifications_unread=unread,
    )


@router.get(
    "/admin/volume",
    response_model=dict,
    summary="Admin analytics volume",
    description="Admin/moderator endpoint returning counts of ingested analytics by type.",
    operation_id="analytics_admin_volume",
)
def admin_volume(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.moderator)),
) -> dict:
    rows = db.execute(
        select(AnalyticsEvent.type, func.count().label("count"))
        .group_by(AnalyticsEvent.type)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    return {"by_type": [{"type": r[0], "count": int(r[1])} for r in rows]}
