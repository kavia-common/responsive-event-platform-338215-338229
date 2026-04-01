"""
FastAPI backend for the Responsive Event Platform.

Provides:
- REST API for auth, events, RSVPs, comments, messaging, notifications, moderation, analytics.
- WebSocket API for realtime messaging/notifications.

Authentication:
- Use /auth/register and /auth/login to obtain a JWT access token.
- Send "Authorization: Bearer <token>" header for REST requests.
- For WebSocket, pass token as query param: /ws?token=<token>

Realtime:
- WebSocket is hosted at `/ws` (same host/port as REST).
- Next.js client should set:
  - NEXT_PUBLIC_API_BASE_URL: e.g. "https://<backend-host>:<port>"
  - NEXT_PUBLIC_WS_BASE_URL: e.g. "wss://<backend-host>:<port>"
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError
from sqlalchemy import select

from src.api.routers.analytics import router as analytics_router
from src.api.routers.auth import router as auth_router
from src.api.routers.comments import router as comments_router
from src.api.routers.events import router as events_router
from src.api.routers.messaging import router as messaging_router
from src.api.routers.moderation import router as moderation_router
from src.api.routers.notifications import router as notifications_router
from src.api.routers.rsvps import router as rsvps_router
from src.auth.security import decode_token
from src.core.settings import get_settings
from src.db.base import Base
from src.db.models import Notification, NotificationType, Thread, User
from src.db.session import get_engine, session_scope
from src.realtime.manager import ConnectionManager

openapi_tags = [
    {"name": "auth", "description": "User registration and login."},
    {"name": "events", "description": "Event discovery and management."},
    {"name": "rsvps", "description": "Event RSVPs."},
    {"name": "comments", "description": "Event comments."},
    {"name": "messaging", "description": "Direct messaging threads and messages."},
    {"name": "notifications", "description": "User notifications."},
    {"name": "moderation", "description": "Reporting and moderation workflows."},
    {"name": "analytics", "description": "Client analytics ingestion and summaries."},
    {"name": "realtime", "description": "WebSocket realtime API for chat/notifications."},
    {"name": "system", "description": "System endpoints and operational docs."},
]

app = FastAPI(
    title="Responsive Event Platform API",
    description="Backend API providing events, social interactions, messaging, notifications, moderation, and analytics.",
    version="0.3.1",
    openapi_tags=openapi_tags,
)

settings = get_settings()

# CORS:
# - In preview, the Next.js frontend is typically served from a different origin/port.
# - Configure allowed origins via CORS_ALLOW_ORIGINS (comma-separated) for a tighter policy.
# - Default "*" keeps local/dev friction low.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()


@app.on_event("startup")
def _startup_prepare_schema() -> None:
    """
    Prepare database schema on startup.

    Current behavior:
    - Calls SQLAlchemy `Base.metadata.create_all()` to ensure tables exist in preview/dev.

    Migration workflow alignment:
    - The Postgres container has a canonical migration entrypoint (`postgresql_database/migrate.sh`).
      This backend does not run that script directly; instead it assumes the DB container
      has applied migrations (or uses create_all for this minimal stack).
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


@app.get("/", tags=["system"], summary="Health check", operation_id="health_check")
def health_check():
    """Simple liveness check endpoint."""
    return {"message": "Healthy"}


@app.get(
    "/docs/realtime",
    tags=["system"],
    summary="WebSocket usage help",
    description="Shows how to connect to WebSocket endpoints for realtime updates.",
    operation_id="realtime_docs",
)
def realtime_docs():
    """Return instructions for WebSocket usage."""
    return {
        "websocket": {
            "url": "/ws?token=<JWT>",
            "notes": [
                "Send JSON messages with a 'type' field.",
                "Supported client-to-server types:",
                "- ping",
                "- message_send {thread_id:int, body:str}",
                "Server-to-client event types:",
                "- pong",
                "- message_new {message: {...}}",
                "- notification_new {notification: {...}}",
            ],
        }
    }


# --- REST routers ---
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(rsvps_router)
app.include_router(comments_router)
app.include_router(messaging_router)
app.include_router(notifications_router)
app.include_router(moderation_router)
app.include_router(analytics_router)


async def _get_user_from_ws_token(token: str) -> User:
    """Validate JWT token and return User for websocket connections."""
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(sub)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    with session_scope() as db:
        user = db.scalar(select(User).where(User.id == user_id))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found/inactive")
        return user


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for realtime messaging & notifications.

    Connect:
      ws(s)://<host>/ws?token=<JWT>

    Client messages:
      - {"type":"ping"}
      - {"type":"message_send","thread_id":123,"body":"Hello"}
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    try:
        user = await _get_user_from_ws_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await manager.connect(user.id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "message_send":
                thread_id = data.get("thread_id")
                body = (data.get("body") or "").strip()
                if not isinstance(thread_id, int) or not body:
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid message_send payload"}
                    )
                    continue

                # Validate thread participant and persist the message; then broadcast to both participants.
                with session_scope() as db:
                    thread = db.get(Thread, thread_id)
                    if not thread or user.id not in (thread.user_a_id, thread.user_b_id):
                        await websocket.send_json(
                            {"type": "error", "message": "Thread not found or access denied"}
                        )
                        continue

                    from src.db.models import Message  # local import to avoid circulars

                    m = Message(thread_id=thread_id, sender_id=user.id, body=body)
                    db.add(m)
                    db.commit()
                    db.refresh(m)

                    payload = {
                        "type": "message_new",
                        "message": {
                            "id": m.id,
                            "thread_id": m.thread_id,
                            "sender_id": m.sender_id,
                            "body": m.body,
                            "created_at": m.created_at.isoformat(),
                        },
                    }

                    # Create a notification for the other user.
                    other_user_id = (
                        thread.user_b_id if user.id == thread.user_a_id else thread.user_a_id
                    )
                    n = Notification(
                        user_id=other_user_id,
                        type=NotificationType.message,
                        title="New message",
                        body=body[:200],
                        is_read=False,
                    )
                    db.add(n)
                    db.commit()
                    db.refresh(n)

                    notif_payload = {
                        "type": "notification_new",
                        "notification": {
                            "id": n.id,
                            "user_id": n.user_id,
                            "type": n.type.value,
                            "title": n.title,
                            "body": n.body,
                            "is_read": n.is_read,
                            "created_at": n.created_at.isoformat(),
                        },
                    }

                # Broadcast outside the DB session.
                await manager.send_to_user(thread.user_a_id, payload)
                await manager.send_to_user(thread.user_b_id, payload)
                await manager.send_to_user(other_user_id, notif_payload)
                continue

            await websocket.send_json({"type": "error", "message": "Unknown message type"})
    except WebSocketDisconnect:
        await manager.disconnect(user.id, websocket)
    except Exception:
        await manager.disconnect(user.id, websocket)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
