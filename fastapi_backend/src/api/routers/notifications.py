from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import NotificationMarkRead, NotificationPublic
from src.auth.dependencies import get_current_user
from src.db.models import Notification, User
from src.db.session import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_public(n: Notification) -> NotificationPublic:
    return NotificationPublic(
        id=n.id,
        user_id=n.user_id,
        type=n.type.value,
        title=n.title,
        body=n.body,
        is_read=n.is_read,
        created_at=n.created_at,
    )


@router.get(
    "",
    response_model=list[NotificationPublic],
    summary="List my notifications",
    operation_id="notifications_list",
)
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[NotificationPublic]:
    ns = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())).all()
    return [_to_public(n) for n in ns]


@router.patch(
    "/{notification_id}",
    response_model=NotificationPublic,
    summary="Mark notification read/unread",
    operation_id="notifications_mark_read",
)
def mark_read(
    notification_id: int,
    payload: NotificationMarkRead,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationPublic:
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        # Do not leak existence
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = payload.is_read
    db.add(n)
    db.commit()
    db.refresh(n)
    return _to_public(n)
