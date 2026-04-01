from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from src.api.schemas import EventCreate, EventPublic, EventUpdate
from src.auth.dependencies import get_current_user
from src.db.models import Event, User
from src.db.session import get_db

router = APIRouter(prefix="/events", tags=["events"])


def _to_public(e: Event) -> EventPublic:
    return EventPublic(
        id=e.id,
        organizer_id=e.organizer_id,
        title=e.title,
        description=e.description,
        location_name=e.location_name,
        latitude=e.latitude,
        longitude=e.longitude,
        starts_at=e.starts_at,
        ends_at=e.ends_at,
        capacity=e.capacity,
        is_cancelled=e.is_cancelled,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


@router.get(
    "",
    response_model=list[EventPublic],
    summary="List events",
    description="Lists upcoming events with optional text query and pagination.",
    operation_id="events_list",
)
def list_events(
    q: str | None = Query(None, description="Optional search query matched against title"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[EventPublic]:
    stmt: Select = select(Event).where(Event.is_cancelled == False)  # noqa: E712
    now = datetime.now(timezone.utc)
    stmt = stmt.where(Event.starts_at >= now).order_by(Event.starts_at.asc())
    if q:
        stmt = stmt.where(func.lower(Event.title).contains(q.lower()))
    events = db.scalars(stmt.limit(limit).offset(offset)).all()
    return [_to_public(e) for e in events]


@router.get(
    "/{event_id}",
    response_model=EventPublic,
    summary="Get an event",
    description="Fetch a single event by id.",
    operation_id="events_get",
)
def get_event(event_id: int, db: Session = Depends(get_db)) -> EventPublic:
    e = db.get(Event, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return _to_public(e)


@router.post(
    "",
    response_model=EventPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create event",
    description="Creates an event owned by the authenticated user.",
    operation_id="events_create",
)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EventPublic:
    e = Event(
        organizer_id=user.id,
        title=payload.title,
        description=payload.description,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        capacity=payload.capacity,
        is_cancelled=False,
        updated_at=datetime.utcnow(),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _to_public(e)


@router.patch(
    "/{event_id}",
    response_model=EventPublic,
    summary="Update event",
    description="Updates an event; only organizer may update.",
    operation_id="events_update",
)
def update_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EventPublic:
    e = db.get(Event, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    if e.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Only organizer may update this event")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    e.updated_at = datetime.utcnow()
    db.add(e)
    db.commit()
    db.refresh(e)
    return _to_public(e)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel event",
    description="Cancels an event (soft delete via is_cancelled); only organizer may cancel.",
    operation_id="events_cancel",
)
def cancel_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    e = db.get(Event, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    if e.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Only organizer may cancel this event")
    e.is_cancelled = True
    e.updated_at = datetime.utcnow()
    db.add(e)
    db.commit()
    return None
