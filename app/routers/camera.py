from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.dependencies import get_current_user
from app.models import CameraEvent, CameraSession, NotificationChannel, Ride, Role
from app.notifications import enqueue_notification, mark_notification_sent
from app.realtime import realtime_manager
from app.schemas import CameraAlertRequest, CameraSnapshotRequest, CameraStartRequest
from app.security import utcnow
from app.services import assert_ride_access, list_user_roles

router = APIRouter(prefix="/camera", tags=["camera"])


def _ride_or_404(session: Session, ride_id: str) -> Ride:
    ride = session.get(Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    return ride


def _driver_or_admin(session: Session, ride: Ride, user_id: str) -> bool:
    roles = set(list_user_roles(session, user_id))
    return Role.ADMIN in roles or ride.driver_user_id == user_id


@router.post("/rides/{ride_id}/start")
async def start_stream(
    ride_id: str,
    payload: CameraStartRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    ride = _ride_or_404(session, ride_id)
    if not _driver_or_admin(session, ride, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver or admin required")
    stream_url = payload.stream_url or f"webrtc://pawride.local/ride/{ride.id}/{uuid4().hex}"
    ride.camera_stream_url = stream_url
    ride.updated_at = utcnow()
    existing_session = session.exec(select(CameraSession).where(CameraSession.ride_id == ride.id)).first()
    if existing_session:
        existing_session.stream_url = stream_url
        existing_session.is_active = True
        existing_session.started_at = utcnow()
        existing_session.ended_at = None
        existing_session.snapshot_interval_minutes = settings.camera_auto_snapshot_interval_minutes
        session.add(existing_session)
    else:
        session.add(
            CameraSession(
                ride_id=ride.id,
                stream_url=stream_url,
                started_by_user_id=current_user.id,
                snapshot_interval_minutes=settings.camera_auto_snapshot_interval_minutes,
            )
        )
    event = CameraEvent(
        ride_id=ride.id,
        event_type="stream_started",
        details="In-car stream started",
        created_by_user_id=current_user.id,
    )
    session.add(ride)
    session.add(event)
    notify = enqueue_notification(
        session,
        user_id=ride.dog_parent_user_id,
        notification_type="camera_stream_started",
        title="Live camera is ready",
        body="Your dog's in-car camera stream is now available.",
        data={"ride_id": ride.id, "stream_url": stream_url},
        channel=NotificationChannel.PUSH,
    )
    mark_notification_sent(session, notify)
    session.commit()
    await realtime_manager.broadcast_ride(
        ride.id,
        {"event": "camera_stream_started", "ride_id": ride.id, "stream_url": stream_url},
    )
    return {"ride_id": ride.id, "stream_url": stream_url}


@router.post("/rides/{ride_id}/join")
async def join_stream(
    ride_id: str,
    reconnect: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    if not ride.camera_stream_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active stream for this ride")
    session_row = session.exec(select(CameraSession).where(CameraSession.ride_id == ride.id)).first()
    if session_row and reconnect:
        session_row.reconnect_count += 1
        session.add(session_row)
        session.commit()
    return {"ride_id": ride.id, "stream_url": ride.camera_stream_url}


@router.post("/rides/{ride_id}/snapshot", status_code=status.HTTP_201_CREATED)
async def snapshot(
    ride_id: str,
    payload: CameraSnapshotRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> CameraEvent:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    event = CameraEvent(
        ride_id=ride.id,
        event_type="snapshot_captured",
        details=payload.details,
        snapshot_url=payload.snapshot_url,
        created_by_user_id=current_user.id,
    )
    camera_session = session.exec(select(CameraSession).where(CameraSession.ride_id == ride.id)).first()
    if camera_session:
        camera_session.last_snapshot_at = utcnow()
        session.add(camera_session)
    session.add(event)
    session.commit()
    session.refresh(event)
    await realtime_manager.broadcast_ride(
        ride.id,
        {
            "event": "camera_snapshot",
            "ride_id": ride.id,
            "snapshot_url": payload.snapshot_url,
            "created_by_user_id": current_user.id,
        },
    )
    return event


@router.post("/rides/{ride_id}/alert", status_code=status.HTTP_201_CREATED)
async def camera_alert(
    ride_id: str,
    payload: CameraAlertRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> CameraEvent:
    ride = _ride_or_404(session, ride_id)
    if not _driver_or_admin(session, ride, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver or admin required")
    event = CameraEvent(
        ride_id=ride.id,
        event_type=payload.event_type,
        details=payload.details,
        created_by_user_id=current_user.id,
    )
    session.add(event)
    parent_notification = enqueue_notification(
        session,
        user_id=ride.dog_parent_user_id,
        notification_type=f"camera_alert_{payload.event_type}",
        title="PawRide camera alert",
        body=payload.details or f"Alert: {payload.event_type}",
        data={"ride_id": ride.id, "event_type": payload.event_type},
        channel=NotificationChannel.PUSH,
    )
    mark_notification_sent(session, parent_notification)
    session.commit()
    session.refresh(event)
    await realtime_manager.broadcast_ride(
        ride.id,
        {"event": "camera_alert", "ride_id": ride.id, "alert_type": payload.event_type, "details": payload.details},
    )
    return event


@router.post("/rides/{ride_id}/end")
async def end_stream(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    ride = _ride_or_404(session, ride_id)
    if not _driver_or_admin(session, ride, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver or admin required")
    ride.camera_stream_url = None
    ride.updated_at = utcnow()
    session_row = session.exec(select(CameraSession).where(CameraSession.ride_id == ride.id)).first()
    if session_row:
        session_row.is_active = False
        session_row.ended_at = utcnow()
        session.add(session_row)
    event = CameraEvent(
        ride_id=ride.id,
        event_type="stream_ended",
        details="In-car stream ended",
        created_by_user_id=current_user.id,
    )
    session.add(ride)
    session.add(event)
    notify = enqueue_notification(
        session,
        user_id=ride.dog_parent_user_id,
        notification_type="camera_stream_ended",
        title="Live camera ended",
        body="In-car stream ended for this ride.",
        data={"ride_id": ride.id},
        channel=NotificationChannel.PUSH,
    )
    mark_notification_sent(session, notify)
    session.commit()
    await realtime_manager.broadcast_ride(
        ride.id,
        {"event": "camera_stream_ended", "ride_id": ride.id},
    )
    return {"ride_id": ride.id, "stream_active": False}


@router.get("/rides/{ride_id}/events")
def camera_events(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[CameraEvent]:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    return session.exec(select(CameraEvent).where(CameraEvent.ride_id == ride.id).order_by(CameraEvent.created_at.asc())).all()


@router.get("/rides/{ride_id}/session")
def camera_session_status(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> CameraSession | None:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    return session.exec(select(CameraSession).where(CameraSession.ride_id == ride.id)).first()
