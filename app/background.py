from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

from sqlmodel import Session, select

from app.billing import process_weekly_payouts
from app.config import settings
from app.database import engine
from app.dispatch import generate_recurring_rides, run_pending_dispatch
from app.models import CameraEvent, CameraSession, NotificationChannel, Ride, RideStatus
from app.notifications import enqueue_notification, has_recent_notification, mark_notification_sent
from app.security import utcnow


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


class BackgroundWorker:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._dispatch_loop()),
            asyncio.create_task(self._camera_snapshot_loop()),
            asyncio.create_task(self._payout_loop()),
            asyncio.create_task(self._scheduled_reminder_loop()),
        ]

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def _dispatch_loop(self) -> None:
        while self._running:
            with Session(engine) as session:
                generate_recurring_rides(session)
                run_pending_dispatch(session)
                session.commit()
            await asyncio.sleep(8)

    async def _camera_snapshot_loop(self) -> None:
        while self._running:
            now = utcnow()
            with Session(engine) as session:
                sessions = session.exec(
                    select(CameraSession).where(CameraSession.is_active.is_(True))
                ).all()
                for camera_session in sessions:
                    interval = timedelta(minutes=max(1, camera_session.snapshot_interval_minutes))
                    last_snapshot = _aware(camera_session.last_snapshot_at) or _aware(camera_session.started_at)
                    if last_snapshot and (now - last_snapshot) < interval:
                        continue
                    ride = session.get(Ride, camera_session.ride_id)
                    if not ride or ride.status in {RideStatus.CANCELLED, RideStatus.COMPLETED}:
                        camera_session.is_active = False
                        camera_session.ended_at = now
                        session.add(camera_session)
                        continue
                    snapshot_url = (
                        f"https://snapshots.pawride.local/{ride.id}/{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}.jpg"
                    )
                    event = CameraEvent(
                        ride_id=ride.id,
                        event_type="snapshot_auto",
                        details="Periodic safety snapshot",
                        snapshot_url=snapshot_url,
                    )
                    camera_session.last_snapshot_at = now
                    session.add(event)
                    session.add(camera_session)
                session.commit()
            await asyncio.sleep(30)

    async def _payout_loop(self) -> None:
        while self._running:
            with Session(engine) as session:
                process_weekly_payouts(session)
                session.commit()
            await asyncio.sleep(60)

    async def _scheduled_reminder_loop(self) -> None:
        while self._running:
            now = utcnow()
            reminder_horizon = now + timedelta(minutes=30)
            with Session(engine) as session:
                rides = session.exec(
                    select(Ride).where(
                        Ride.status == RideStatus.REQUESTED,
                        Ride.scheduled_for.is_not(None),
                        Ride.scheduled_for <= reminder_horizon,
                        Ride.scheduled_for >= now,
                    )
                ).all()
                for ride in rides:
                    if has_recent_notification(
                        session,
                        user_id=ride.dog_parent_user_id,
                        notification_type="scheduled_ride_reminder",
                        ride_id=ride.id,
                    ):
                        continue
                    event = enqueue_notification(
                        session,
                        user_id=ride.dog_parent_user_id,
                        notification_type="scheduled_ride_reminder",
                        title="Upcoming PawRide",
                        body=f"Ride to {ride.dropoff_label or ride.dropoff_address} starts in about 30 minutes.",
                        data={"ride_id": ride.id, "scheduled_for": ride.scheduled_for.isoformat() if ride.scheduled_for else None},
                        channel=NotificationChannel.PUSH,
                    )
                    mark_notification_sent(session, event)
                session.commit()
            await asyncio.sleep(60)


background_worker = BackgroundWorker()
