from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.api.schemas import MessageCreate, MessagePublic, ThreadPublic
from src.auth.dependencies import get_current_user
from src.db.models import Message, Thread, User
from src.db.session import get_db

router = APIRouter(prefix="/messaging", tags=["messaging"])


def _thread_public(t: Thread) -> ThreadPublic:
    return ThreadPublic(id=t.id, user_a_id=t.user_a_id, user_b_id=t.user_b_id, created_at=t.created_at)


def _message_public(m: Message) -> MessagePublic:
    return MessagePublic(id=m.id, thread_id=m.thread_id, sender_id=m.sender_id, body=m.body, created_at=m.created_at)


@router.get(
    "/threads",
    response_model=list[ThreadPublic],
    summary="List my threads",
    operation_id="messaging_threads_list",
)
def list_threads(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ThreadPublic]:
    threads = db.scalars(
        select(Thread)
        .where(or_(Thread.user_a_id == user.id, Thread.user_b_id == user.id))
        .order_by(Thread.created_at.desc())
    ).all()
    return [_thread_public(t) for t in threads]


@router.post(
    "/threads",
    response_model=ThreadPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create/get a 1:1 thread",
    description="Creates a thread with another user (or returns existing).",
    operation_id="messaging_threads_create",
)
def create_thread(
    other_user_id: int = Query(..., description="The user id to chat with"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ThreadPublic:
    if other_user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot create thread with yourself")

    a, b = sorted([user.id, other_user_id])
    existing = db.scalar(select(Thread).where(and_(Thread.user_a_id == a, Thread.user_b_id == b)))
    if existing:
        return _thread_public(existing)

    thread = Thread(user_a_id=a, user_b_id=b)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return _thread_public(thread)


@router.get(
    "/threads/{thread_id}/messages",
    response_model=list[MessagePublic],
    summary="List messages in thread",
    operation_id="messaging_messages_list",
)
def list_messages(
    thread_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MessagePublic]:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=403, detail="Not a participant of this thread")

    msgs = db.scalars(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_message_public(m) for m in msgs][::-1]


@router.post(
    "/threads/{thread_id}/messages",
    response_model=MessagePublic,
    status_code=status.HTTP_201_CREATED,
    summary="Send message (REST)",
    description="Creates a message in the thread. For realtime delivery use WebSocket.",
    operation_id="messaging_messages_send",
)
def send_message(
    thread_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessagePublic:
    thread = db.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if user.id not in (thread.user_a_id, thread.user_b_id):
        raise HTTPException(status_code=403, detail="Not a participant of this thread")

    msg = Message(thread_id=thread_id, sender_id=user.id, body=payload.body)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_public(msg)
