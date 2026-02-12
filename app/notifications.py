from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models import NotificationChannel, NotificationEvent, NotificationStatus
from app.security import utcnow


def enqueue_notification(
    session: Session,
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    channel: NotificationChannel = NotificationChannel.PUSH,
) -> NotificationEvent:
    event = NotificationEvent(
        user_id=user_id,
        channel=channel,
        notification_type=notification_type,
        title=title,
        body=body,
        data_json=data,
        status=NotificationStatus.QUEUED,
    )
    session.add(event)
    return event


def mark_notification_sent(session: Session, event: NotificationEvent) -> NotificationEvent:
    event.status = NotificationStatus.SENT
    event.sent_at = utcnow()
    session.add(event)
    return event


def has_recent_notification(
    session: Session,
    user_id: str,
    notification_type: str,
    ride_id: str | None = None,
) -> bool:
    entries = session.exec(
        select(NotificationEvent)
        .where(
            NotificationEvent.user_id == user_id,
            NotificationEvent.notification_type == notification_type,
        )
        .order_by(NotificationEvent.created_at.desc())
        .limit(20)
    ).all()
    if ride_id is None:
        return bool(entries)
    for entry in entries:
        payload = entry.data_json or {}
        if str(payload.get("ride_id")) == ride_id:
            return True
    return False
