from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import CommentCreate, CommentPublic
from src.auth.dependencies import get_current_user, require_role
from src.db.models import Comment, Event, User, UserRole
from src.db.session import get_db

router = APIRouter(prefix="/events/{event_id}/comments", tags=["comments"])


def _to_public(c: Comment) -> CommentPublic:
    return CommentPublic(
        id=c.id,
        event_id=c.event_id,
        author_id=c.author_id,
        body=c.body,
        is_removed=c.is_removed,
        created_at=c.created_at,
    )


@router.get(
    "",
    response_model=list[CommentPublic],
    summary="List comments for an event",
    operation_id="comments_list",
)
def list_comments(event_id: int, db: Session = Depends(get_db)) -> list[CommentPublic]:
    if not db.get(Event, event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    comments = db.scalars(select(Comment).where(Comment.event_id == event_id).order_by(Comment.created_at.asc())).all()
    return [_to_public(c) for c in comments]


@router.post(
    "",
    response_model=CommentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create comment",
    description="Create a comment on an event as the authenticated user.",
    operation_id="comments_create",
)
def create_comment(
    event_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CommentPublic:
    event = db.get(Event, event_id)
    if not event or event.is_cancelled:
        raise HTTPException(status_code=404, detail="Event not found")
    c = Comment(event_id=event_id, author_id=user.id, body=payload.body, is_removed=False)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_public(c)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove comment (moderation)",
    description="Marks a comment as removed. Requires admin/moderator.",
    operation_id="comments_remove",
)
def remove_comment(
    event_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.moderator)),
) -> None:
    c = db.get(Comment, comment_id)
    if not c or c.event_id != event_id:
        raise HTTPException(status_code=404, detail="Comment not found")
    c.is_removed = True
    db.add(c)
    db.commit()
    return None
