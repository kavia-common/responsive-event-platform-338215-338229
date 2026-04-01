from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import ReportCreate, ReportPublic, ReportUpdate
from src.auth.dependencies import get_current_user, require_role
from src.db.models import Report, ReportStatus, User, UserRole
from src.db.session import get_db

router = APIRouter(prefix="/moderation", tags=["moderation"])


def _to_public(r: Report) -> ReportPublic:
    return ReportPublic(
        id=r.id,
        reporter_id=r.reporter_id,
        target_type=r.target_type,
        target_id=r.target_id,
        reason=r.reason,
        status=r.status.value,
        moderator_note=r.moderator_note,
        created_at=r.created_at,
        resolved_at=r.resolved_at,
    )


@router.post(
    "/reports",
    response_model=ReportPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a report",
    description="Report an event/comment/message/user for moderation review.",
    operation_id="moderation_reports_create",
)
def create_report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportPublic:
    r = Report(reporter_id=user.id, target_type=payload.target_type, target_id=payload.target_id, reason=payload.reason)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _to_public(r)


@router.get(
    "/reports",
    response_model=list[ReportPublic],
    summary="List reports (admin/moderator)",
    operation_id="moderation_reports_list",
)
def list_reports(
    status_filter: str | None = Query(None, description="Filter by status: open|resolved|dismissed"),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.moderator)),
) -> list[ReportPublic]:
    stmt = select(Report).order_by(Report.created_at.desc())
    if status_filter:
        try:
            stmt = stmt.where(Report.status == ReportStatus(status_filter))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid status_filter")
    reports = db.scalars(stmt).all()
    return [_to_public(r) for r in reports]


@router.patch(
    "/reports/{report_id}",
    response_model=ReportPublic,
    summary="Update report status/note (admin/moderator)",
    operation_id="moderation_reports_update",
)
def update_report(
    report_id: int,
    payload: ReportUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.moderator)),
) -> ReportPublic:
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        r.status = ReportStatus(data["status"])
        if r.status in (ReportStatus.resolved, ReportStatus.dismissed):
            r.resolved_at = datetime.utcnow()
        else:
            r.resolved_at = None

    if "moderator_note" in data and data["moderator_note"] is not None:
        r.moderator_note = data["moderator_note"]

    db.add(r)
    db.commit()
    db.refresh(r)
    return _to_public(r)
