from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.schemas import RSVPPublic
from src.auth.dependencies import get_current_user
from src.db.models import Event, RSVP, User
from src.db.session import get_db

router = APIRouter(prefix="/events/{event_id}/rsvps", tags=["rsvps"])


def _to_public(r: RSVP) -> RSVPPublic:
    return RSVPPublic(id=r.id, event_id=r.event_id, user_id=r.user_id, created_at=r.created_at)


@router.get(
    "",
    response_model=list[RSVPPublic],
    summary="List RSVPs for an event",
    operation_id="rsvps_list",
)
def list_rsvps(event_id: int, db: Session = Depends(get_db)) -> list[RSVPPublic]:
    if not db.get(Event, event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    rsvps = db.scalars(select(RSVP).where(RSVP.event_id == event_id).order_by(RSVP.created_at.desc())).all()
    return [_to_public(r) for r in rsvps]


@router.post(
    "",
    response_model=RSVPPublic,
    status_code=status.HTTP_201_CREATED,
    summary="RSVP to an event",
    description="Creates an RSVP for the current user. Returns the RSVP record.",
    operation_id="rsvps_create",
)
def create_rsvp(event_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> RSVPPublic:
    event = db.get(Event, event_id)
    if not event or event.is_cancelled:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.capacity is not None:
        count = db.scalar(select(func.count()).select_from(RSVP).where(RSVP.event_id == event_id))
        if count is not None and int(count) >= int(event.capacity):
            raise HTTPException(status_code=409, detail="Event is at capacity")

    existing = db.scalar(select(RSVP).where(RSVP.event_id == event_id, RSVP.user_id == user.id))
    if existing:
        return _to_public(existing)

    rsvp = RSVP(event_id=event_id, user_id=user.id)
    db.add(rsvp)
    db.commit()
    db.refresh(rsvp)
    return _to_public(rsvp)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove RSVP",
    description="Deletes the RSVP for the current user on this event.",
    operation_id="rsvps_delete",
)
def delete_rsvp(event_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    rsvp = db.scalar(select(RSVP).where(RSVP.event_id == event_id, RSVP.user_id == user.id))
    if not rsvp:
        return None
    db.delete(rsvp)
    db.commit()
    return None
