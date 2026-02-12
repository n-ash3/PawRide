from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import NotificationEvent, NotificationStatus, Role
from app.schemas import NotificationMarkReadRequest
from app.security import utcnow
from app.services import list_user_roles

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me")
def my_notifications(
    limit: int = Query(default=100, ge=1, le=500),
    include_read: bool = Query(default=True),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[NotificationEvent]:
    stmt = (
        select(NotificationEvent)
        .where(NotificationEvent.user_id == current_user.id)
        .order_by(NotificationEvent.created_at.desc())
        .limit(limit)
    )
    if not include_read:
        stmt = stmt.where(NotificationEvent.status != NotificationStatus.READ)
    return session.exec(stmt).all()


@router.get("/me/unread-count")
def unread_count(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    unread = session.exec(
        select(NotificationEvent).where(
            NotificationEvent.user_id == current_user.id,
            NotificationEvent.status != NotificationStatus.READ,
        )
    ).all()
    return {"unread_count": len(unread)}


@router.post("/me/read")
def mark_read(
    payload: NotificationMarkReadRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    if payload.notification_ids:
        notifications = session.exec(
            select(NotificationEvent).where(
                NotificationEvent.user_id == current_user.id,
                NotificationEvent.id.in_(payload.notification_ids),
            )
        ).all()
    else:
        notifications = session.exec(
            select(NotificationEvent).where(NotificationEvent.user_id == current_user.id)
        ).all()
    now = utcnow()
    for notification in notifications:
        notification.status = NotificationStatus.READ
        notification.read_at = now
        session.add(notification)
    session.commit()
    return {"updated": len(notifications)}


@router.get("/admin/all")
def admin_notification_feed(
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[NotificationEvent]:
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return session.exec(select(NotificationEvent).order_by(NotificationEvent.created_at.desc()).limit(limit)).all()
