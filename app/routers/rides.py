from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.dependencies import get_current_user
from app.dispatch import current_pending_offer, dispatch_ride_once, respond_to_offer, run_pending_dispatch
from app.models import (
    CameraEvent,
    CameraSession,
    Dog,
    DriverOfferResponse,
    DropoffType,
    NotificationChannel,
    RecurringRidePlan,
    ReceiverVerificationAttempt,
    Ride,
    RideDispatchAttempt,
    RideStatus,
    RideStatusEvent,
    Role,
    TrustedReceiver,
    UserRole,
)
from app.notifications import enqueue_notification, mark_notification_sent
from app.realtime import realtime_manager
from app.schemas import (
    DispatchResponseRequest,
    FacilityDropoffVerificationRequest,
    RideAssignDriverRequest,
    RideCancelRequest,
    RideRequestCreate,
    RideStatusUpdateRequest,
    TrustedDropoffVerificationRequest,
)
from app.security import utcnow
from app.services import (
    assert_ride_access,
    calculate_estimated_fare,
    cancel_fee_for_ride,
    create_ride_status_event,
    list_user_roles,
    validate_ride_transition,
)

router = APIRouter(prefix="/rides", tags=["rides"])


def _ride_or_404(session: Session, ride_id: str) -> Ride:
    ride = session.get(Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    return ride


def _driver_or_admin_for_ride(session: Session, current_user_id: str, ride: Ride) -> bool:
    roles = set(list_user_roles(session, current_user_id))
    if Role.ADMIN in roles:
        return True
    return ride.driver_user_id == current_user_id


def _notify_ride_event(
    session: Session,
    ride: Ride,
    event_type: str,
    parent_message: str,
    driver_message: str | None = None,
) -> None:
    parent_event = enqueue_notification(
        session,
        user_id=ride.dog_parent_user_id,
        notification_type=event_type,
        title="PawRide Update",
        body=parent_message,
        data={"ride_id": ride.id, "status": ride.status.value},
        channel=NotificationChannel.PUSH,
    )
    mark_notification_sent(session, parent_event)
    if ride.driver_user_id and driver_message:
        driver_event = enqueue_notification(
            session,
            user_id=ride.driver_user_id,
            notification_type=event_type,
            title="PawRide Driver Update",
            body=driver_message,
            data={"ride_id": ride.id, "status": ride.status.value},
            channel=NotificationChannel.PUSH,
        )
        mark_notification_sent(session, driver_event)


def _next_recurring_run(reference_time, rule: str):
    if rule == "daily":
        return reference_time + timedelta(days=1)
    if rule == "weekly":
        return reference_time + timedelta(days=7)
    if rule == "weekdays":
        nxt = reference_time + timedelta(days=1)
        while nxt.weekday() > 4:
            nxt = nxt + timedelta(days=1)
        return nxt
    if rule.startswith("every_") and rule.endswith("_days"):
        raw = rule[len("every_") : -len("_days")]
        if raw.isdigit():
            return reference_time + timedelta(days=max(1, int(raw)))
    return None


@router.post("/estimate")
def estimate_ride_fare(
    payload: RideRequestCreate,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    dog = session.get(Dog, payload.dog_id)
    if not dog or dog.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")
    estimate = calculate_estimated_fare(
        dog=dog,
        distance_km=payload.distance_km,
        duration_minutes=payload.duration_minutes,
        dog_count=payload.dog_count,
        surge_multiplier=payload.surge_multiplier,
    )
    return estimate


@router.post("", status_code=status.HTTP_201_CREATED)
async def request_ride(
    payload: RideRequestCreate,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Ride:
    dog = session.get(Dog, payload.dog_id)
    if not dog or dog.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")

    if payload.scheduled_for and payload.scheduled_for > utcnow() + timedelta(days=7):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scheduled rides can only be booked up to 7 days ahead",
        )

    if payload.dropoff_type == DropoffType.TRUSTED_PERSON and not payload.trusted_receiver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="trusted_receiver_id is required for trusted person dropoff",
        )

    if payload.trusted_receiver_id:
        receiver = session.get(TrustedReceiver, payload.trusted_receiver_id)
        if not receiver or receiver.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trusted receiver",
            )

    fare = calculate_estimated_fare(
        dog=dog,
        distance_km=payload.distance_km,
        duration_minutes=payload.duration_minutes,
        dog_count=payload.dog_count,
        surge_multiplier=payload.surge_multiplier,
    )

    ride = Ride(
        dog_parent_user_id=current_user.id,
        dog_id=payload.dog_id,
        dog_count=payload.dog_count,
        pickup_label=payload.pickup_label,
        pickup_address=payload.pickup_address,
        pickup_latitude=payload.pickup_latitude,
        pickup_longitude=payload.pickup_longitude,
        dropoff_label=payload.dropoff_label,
        dropoff_address=payload.dropoff_address,
        dropoff_latitude=payload.dropoff_latitude,
        dropoff_longitude=payload.dropoff_longitude,
        dropoff_type=payload.dropoff_type,
        trusted_receiver_id=payload.trusted_receiver_id,
        scheduled_for=payload.scheduled_for,
        recurring_rule=payload.recurring_rule,
        special_instructions=payload.special_instructions,
        fare_total=fare["fare_total"],
        base_fare=fare["base_fare"],
        distance_km=payload.distance_km,
        duration_minutes=payload.duration_minutes,
        surge_multiplier=fare["surge_multiplier"],
        size_surcharge=fare["size_surcharge"],
        additional_dog_fee=fare["additional_dog_fee"],
    )
    session.add(ride)
    session.flush()
    create_ride_status_event(
        session,
        ride_id=ride.id,
        status_value=RideStatus.REQUESTED,
        created_by_user_id=current_user.id,
        metadata={
            "dropoff_type": payload.dropoff_type.value,
            "scheduled_for": payload.scheduled_for.isoformat() if payload.scheduled_for else None,
        },
    )
    if payload.recurring_rule:
        reference = payload.scheduled_for or utcnow()
        next_run = _next_recurring_run(reference, payload.recurring_rule)
        if next_run:
            session.add(
                RecurringRidePlan(
                    owner_user_id=current_user.id,
                    dog_id=payload.dog_id,
                    pickup_label=payload.pickup_label,
                    pickup_address=payload.pickup_address,
                    pickup_latitude=payload.pickup_latitude,
                    pickup_longitude=payload.pickup_longitude,
                    dropoff_label=payload.dropoff_label,
                    dropoff_address=payload.dropoff_address,
                    dropoff_latitude=payload.dropoff_latitude,
                    dropoff_longitude=payload.dropoff_longitude,
                    dropoff_type=payload.dropoff_type,
                    trusted_receiver_id=payload.trusted_receiver_id,
                    recurring_rule=payload.recurring_rule,
                    special_instructions=payload.special_instructions,
                    distance_km=payload.distance_km,
                    duration_minutes=payload.duration_minutes,
                    dog_count=payload.dog_count,
                    next_run_at=next_run,
                )
            )

    dispatch_result = {"action": "not_attempted"}
    now = utcnow()
    can_auto_dispatch = (
        payload.auto_dispatch
        and (
            payload.scheduled_for is None
            or payload.scheduled_for <= now + timedelta(minutes=30)
        )
    )
    if can_auto_dispatch:
        dispatch_result = dispatch_ride_once(session, ride)
        if dispatch_result.get("action") == "offered":
            driver_id = dispatch_result.get("driver_user_id")
            if driver_id:
                driver_offer_event = enqueue_notification(
                    session,
                    user_id=driver_id,
                    notification_type="new_ride_offer",
                    title="New PawRide request nearby",
                    body=f"Offer expires in {settings.dispatch_offer_timeout_seconds} seconds",
                    data={"ride_id": ride.id, "dog_id": payload.dog_id},
                    channel=NotificationChannel.PUSH,
                )
                mark_notification_sent(session, driver_offer_event)
    _notify_ride_event(
        session,
        ride,
        event_type="ride_requested",
        parent_message="Your PawRide request is in progress. We are matching a driver.",
    )
    session.commit()
    session.refresh(ride)

    await realtime_manager.broadcast_ride(
        ride.id,
        {"event": "ride_requested", "ride_id": ride.id, "status": ride.status.value},
    )
    if dispatch_result.get("action") == "offered":
        await realtime_manager.broadcast_ride(
            ride.id,
            {
                "event": "driver_offer_sent",
                "ride_id": ride.id,
                "driver_user_id": dispatch_result.get("driver_user_id"),
                "expires_in_seconds": settings.dispatch_offer_timeout_seconds,
            },
        )
    return ride


@router.get("")
def list_rides(
    status_filter: RideStatus | None = Query(default=None),
    include_all: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[Ride]:
    roles = set(list_user_roles(session, current_user.id))
    stmt = select(Ride)
    if Role.ADMIN not in roles or not include_all:
        stmt = stmt.where((Ride.dog_parent_user_id == current_user.id) | (Ride.driver_user_id == current_user.id))
    if status_filter:
        stmt = stmt.where(Ride.status == status_filter)
    stmt = stmt.order_by(Ride.created_at.desc())
    return session.exec(stmt).all()


@router.get("/{ride_id}")
def get_ride(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Ride:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    return ride


@router.get("/{ride_id}/events")
def ride_events(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[RideStatusEvent]:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    return session.exec(
        select(RideStatusEvent).where(RideStatusEvent.ride_id == ride_id).order_by(RideStatusEvent.created_at.asc())
    ).all()


@router.get("/{ride_id}/dispatch/attempts")
def dispatch_attempts(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[RideDispatchAttempt]:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    attempts = session.exec(
        select(RideDispatchAttempt)
        .where(RideDispatchAttempt.ride_id == ride_id)
        .order_by(RideDispatchAttempt.sequence_number.asc())
    ).all()
    return attempts


@router.post("/{ride_id}/dispatch/run")
async def run_dispatch_for_ride(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    ride = _ride_or_404(session, ride_id)
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN not in roles and ride.dog_parent_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin or ride owner can trigger dispatch")
    result = dispatch_ride_once(session, ride)
    if result.get("action") == "offered" and result.get("driver_user_id"):
        offer_event = enqueue_notification(
            session,
            user_id=result["driver_user_id"],
            notification_type="new_ride_offer",
            title="New PawRide request nearby",
            body=f"Offer expires in {settings.dispatch_offer_timeout_seconds} seconds",
            data={"ride_id": ride.id, "dog_id": ride.dog_id},
            channel=NotificationChannel.PUSH,
        )
        mark_notification_sent(session, offer_event)
    session.commit()
    if result.get("action") == "offered":
        await realtime_manager.broadcast_ride(
            ride.id,
            {
                "event": "driver_offer_sent",
                "ride_id": ride.id,
                "driver_user_id": result.get("driver_user_id"),
                "expires_in_seconds": settings.dispatch_offer_timeout_seconds,
            },
        )
    return result


@router.post("/{ride_id}/dispatch/respond")
async def respond_dispatch_offer(
    ride_id: str,
    payload: DispatchResponseRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    roles = set(list_user_roles(session, current_user.id))
    if Role.DRIVER not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")
    ride = _ride_or_404(session, ride_id)
    result = respond_to_offer(
        session,
        ride=ride,
        driver_user_id=current_user.id,
        accept=payload.accept,
        decline_reason=payload.decline_reason,
    )
    if result.get("action") == "accepted":
        _notify_ride_event(
            session,
            ride,
            event_type="ride_accepted",
            parent_message="A driver accepted your dog's ride.",
            driver_message="You accepted this PawRide request.",
        )
    elif result.get("action") == "declined":
        dispatch_result = dispatch_ride_once(session, ride)
        result["next_dispatch"] = dispatch_result
        if dispatch_result.get("action") == "offered" and dispatch_result.get("driver_user_id"):
            offer_event = enqueue_notification(
                session,
                user_id=dispatch_result["driver_user_id"],
                notification_type="new_ride_offer",
                title="New PawRide request nearby",
                body=f"Offer expires in {settings.dispatch_offer_timeout_seconds} seconds",
                data={"ride_id": ride.id, "dog_id": ride.dog_id},
                channel=NotificationChannel.PUSH,
            )
            mark_notification_sent(session, offer_event)
    session.commit()
    await realtime_manager.broadcast_ride(
        ride.id,
        {"event": "dispatch_response", "ride_id": ride.id, **result},
    )
    return result


@router.post("/dispatch/run-pending")
def run_pending_dispatches(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    processed = run_pending_dispatch(session)
    session.commit()
    return {"processed_rides": processed, "count": len(processed)}


@router.get("/recurring/plans")
def list_recurring_plans(
    include_inactive: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[RecurringRidePlan]:
    roles = set(list_user_roles(session, current_user.id))
    stmt = select(RecurringRidePlan)
    if Role.ADMIN not in roles:
        stmt = stmt.where(RecurringRidePlan.owner_user_id == current_user.id)
    if not include_inactive:
        stmt = stmt.where(RecurringRidePlan.is_active.is_(True))
    return session.exec(stmt.order_by(RecurringRidePlan.created_at.desc())).all()


@router.delete("/recurring/plans/{plan_id}")
def disable_recurring_plan(
    plan_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    plan = session.get(RecurringRidePlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring plan not found")
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN not in roles and plan.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    plan.is_active = False
    plan.updated_at = utcnow()
    session.add(plan)
    session.commit()
    return {"plan_id": plan_id, "is_active": False}


@router.post("/{ride_id}/assign-driver")
async def assign_driver(
    ride_id: str,
    payload: RideAssignDriverRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Ride:
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    ride = _ride_or_404(session, ride_id)
    if ride.status in {RideStatus.CANCELLED, RideStatus.COMPLETED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride is no longer assignable")
    has_driver_role = session.exec(
        select(UserRole).where(UserRole.user_id == payload.driver_user_id, UserRole.role == Role.DRIVER)
    ).first()
    if not has_driver_role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user is not a driver")
    ride.driver_user_id = payload.driver_user_id
    if ride.status == RideStatus.REQUESTED:
        ride.status = RideStatus.ACCEPTED
        ride.accepted_at = utcnow()
    ride.status_updated_at = utcnow()
    ride.updated_at = utcnow()
    create_ride_status_event(
        session,
        ride.id,
        ride.status,
        created_by_user_id=current_user.id,
        note="Driver assigned",
        metadata={"driver_user_id": payload.driver_user_id},
    )
    _notify_ride_event(
        session,
        ride,
        event_type="driver_assigned",
        parent_message="A driver has been assigned to your ride.",
        driver_message="You have been assigned a PawRide trip.",
    )
    session.add(ride)
    session.commit()
    session.refresh(ride)
    await realtime_manager.broadcast_ride(
        ride.id,
        {
            "event": "driver_assigned",
            "ride_id": ride.id,
            "driver_user_id": ride.driver_user_id,
            "status": ride.status.value,
        },
    )
    return ride


@router.post("/{ride_id}/accept")
async def accept_ride(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Ride:
    roles = set(list_user_roles(session, current_user.id))
    if Role.DRIVER not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")
    ride = _ride_or_404(session, ride_id)
    if ride.status != RideStatus.REQUESTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride cannot be accepted")
    if ride.driver_user_id and ride.driver_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride offered to a different driver")
    pending_offer = current_pending_offer(session, ride.id)
    if pending_offer and pending_offer.driver_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ride is currently offered to a different driver",
        )
    if pending_offer and pending_offer.driver_user_id == current_user.id:
        result = respond_to_offer(session, ride, current_user.id, accept=True)
        if result.get("action") != "accepted":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to accept dispatch offer")
        _notify_ride_event(
            session,
            ride,
            event_type="ride_accepted",
            parent_message="Your driver accepted the ride request.",
            driver_message="You accepted this ride.",
        )
        session.commit()
        session.refresh(ride)
        await realtime_manager.broadcast_ride(
            ride.id,
            {"event": "ride_accepted", "ride_id": ride.id, "driver_user_id": current_user.id, "status": ride.status.value},
        )
        return ride
    ride.driver_user_id = current_user.id
    ride.status = RideStatus.ACCEPTED
    ride.accepted_at = utcnow()
    ride.status_updated_at = utcnow()
    ride.updated_at = utcnow()
    create_ride_status_event(
        session,
        ride.id,
        RideStatus.ACCEPTED,
        created_by_user_id=current_user.id,
        note="Ride accepted by driver",
    )
    _notify_ride_event(
        session,
        ride,
        event_type="ride_accepted",
        parent_message="Your driver accepted the ride request.",
        driver_message="You accepted this ride.",
    )
    session.add(ride)
    session.commit()
    session.refresh(ride)
    await realtime_manager.broadcast_ride(
        ride.id,
        {"event": "ride_accepted", "ride_id": ride.id, "driver_user_id": current_user.id, "status": ride.status.value},
    )
    return ride


@router.post("/{ride_id}/status")
async def update_ride_status(
    ride_id: str,
    payload: RideStatusUpdateRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Ride:
    ride = _ride_or_404(session, ride_id)
    if not _driver_or_admin_for_ride(session, current_user.id, ride):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver or admin required")
    if payload.status == RideStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use dedicated cancel endpoint for cancellations",
        )
    validate_ride_transition(ride.status, payload.status)
    if payload.status != RideStatus.ACCEPTED and not ride.driver_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride must have an assigned driver before status updates",
        )

    now = utcnow()
    ride.status = payload.status
    ride.status_updated_at = now
    ride.updated_at = now
    if payload.status == RideStatus.ACCEPTED:
        ride.accepted_at = now
    elif payload.status == RideStatus.DRIVER_EN_ROUTE:
        pass
    elif payload.status == RideStatus.ARRIVED_AT_PICKUP:
        ride.pickup_arrived_at = now
    elif payload.status == RideStatus.DOG_PICKED_UP:
        ride.dog_picked_up_at = now
    elif payload.status == RideStatus.ARRIVED_AT_DROPOFF:
        ride.dropoff_arrived_at = now
    elif payload.status == RideStatus.COMPLETED:
        ride.completed_at = now
        if ride.camera_stream_url:
            ride.camera_stream_url = None
            active_session = session.exec(
                select(CameraSession).where(CameraSession.ride_id == ride.id, CameraSession.is_active.is_(True))
            ).first()
            if active_session:
                active_session.is_active = False
                active_session.ended_at = now
                session.add(active_session)
            session.add(
                CameraEvent(
                    ride_id=ride.id,
                    event_type="stream_ended",
                    details="Auto-ended when ride completed",
                    created_by_user_id=current_user.id,
                )
            )

    create_ride_status_event(
        session,
        ride.id,
        payload.status,
        created_by_user_id=current_user.id,
        note=payload.note,
        metadata=payload.metadata,
    )
    status_messages = {
        RideStatus.DRIVER_EN_ROUTE: "Driver is on the way to pickup.",
        RideStatus.ARRIVED_AT_PICKUP: "Driver has arrived at pickup.",
        RideStatus.DOG_PICKED_UP: "Your dog has been picked up. Live camera is available.",
        RideStatus.IN_TRANSIT: "Ride is in transit.",
        RideStatus.ARRIVED_AT_DROPOFF: "Driver arrived at dropoff location.",
        RideStatus.VERIFYING_RECEIVER: "Dropoff verification in progress.",
        RideStatus.DOG_DELIVERED: "Your dog has been safely handed off.",
        RideStatus.COMPLETED: "Ride completed. Please rate your driver.",
    }
    if payload.status in status_messages:
        _notify_ride_event(
            session,
            ride,
            event_type=f"ride_status_{payload.status.value}",
            parent_message=status_messages[payload.status],
            driver_message=status_messages[payload.status],
        )
    session.add(ride)
    session.commit()
    session.refresh(ride)

    await realtime_manager.broadcast_ride(
        ride.id,
        {
            "event": "ride_status_updated",
            "ride_id": ride.id,
            "status": ride.status.value,
            "updated_by": current_user.id,
        },
    )
    return ride


@router.post("/{ride_id}/cancel")
async def cancel_ride(
    ride_id: str,
    payload: RideCancelRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Ride:
    ride = _ride_or_404(session, ride_id)
    assert_ride_access(session, ride, current_user)
    if ride.status in {RideStatus.CANCELLED, RideStatus.COMPLETED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride cannot be cancelled")

    now = utcnow()
    fee = cancel_fee_for_ride(ride, now)
    ride.status = RideStatus.CANCELLED
    ride.cancellation_reason = payload.reason
    ride.cancellation_fee = fee
    ride.cancelled_at = now
    ride.status_updated_at = now
    ride.updated_at = now
    create_ride_status_event(
        session,
        ride.id,
        RideStatus.CANCELLED,
        created_by_user_id=current_user.id,
        note=payload.reason,
        metadata={"cancellation_fee": fee},
    )
    _notify_ride_event(
        session,
        ride,
        event_type="ride_cancelled",
        parent_message=f"Ride cancelled. Fee: ${fee:.2f}",
        driver_message="Ride was cancelled.",
    )
    session.add(ride)
    session.commit()
    session.refresh(ride)
    await realtime_manager.broadcast_ride(
        ride.id,
        {
            "event": "ride_cancelled",
            "ride_id": ride.id,
            "status": ride.status.value,
            "cancellation_fee": fee,
        },
    )
    return ride


@router.post("/{ride_id}/verify/trusted-person")
async def verify_trusted_receiver(
    ride_id: str,
    payload: TrustedDropoffVerificationRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    ride = _ride_or_404(session, ride_id)
    if not _driver_or_admin_for_ride(session, current_user.id, ride):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver or admin required")
    if ride.dropoff_type != DropoffType.TRUSTED_PERSON:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride is not a trusted-person dropoff")
    if ride.status not in {RideStatus.ARRIVED_AT_DROPOFF, RideStatus.VERIFYING_RECEIVER}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride is not ready for receiver verification")
    if ride.trusted_receiver_id != payload.receiver_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Receiver does not match ride")
    receiver = session.get(TrustedReceiver, payload.receiver_id)
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver not found")

    attempts = session.exec(
        select(ReceiverVerificationAttempt).where(ReceiverVerificationAttempt.ride_id == ride.id)
    ).all()
    failed_attempts = len([attempt for attempt in attempts if not attempt.success])
    if failed_attempts >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receiver verification already failed 3 times; contact owner and do not hand off dog",
        )
    attempt_number = len(attempts) + 1
    pin_match = receiver.pin_code == payload.pin_code
    photo_match = payload.photo_match
    success = pin_match and photo_match
    attempt = ReceiverVerificationAttempt(
        ride_id=ride.id,
        receiver_id=payload.receiver_id,
        attempt_number=attempt_number,
        pin_entered=payload.pin_code,
        pin_match=pin_match,
        photo_url=payload.photo_url,
        photo_match=photo_match,
        success=success,
    )
    session.add(attempt)

    if ride.status == RideStatus.ARRIVED_AT_DROPOFF:
        validate_ride_transition(ride.status, RideStatus.VERIFYING_RECEIVER)
    ride.status = RideStatus.VERIFYING_RECEIVER
    ride.status_updated_at = utcnow()
    ride.updated_at = utcnow()
    create_ride_status_event(
        session,
        ride.id,
        RideStatus.VERIFYING_RECEIVER,
        created_by_user_id=current_user.id,
        note="Trusted receiver verification attempt",
        metadata={"attempt_number": attempt_number, "pin_match": pin_match, "photo_match": photo_match},
    )

    response = {
        "ride_id": ride.id,
        "attempt_number": attempt_number,
        "pin_match": pin_match,
        "photo_match": photo_match,
        "success": success,
    }
    if success:
        validate_ride_transition(ride.status, RideStatus.DOG_DELIVERED)
        ride.status = RideStatus.DOG_DELIVERED
        ride.dropoff_verification_photo_url = payload.photo_url
        ride.status_updated_at = utcnow()
        create_ride_status_event(
            session,
            ride.id,
            RideStatus.DOG_DELIVERED,
            created_by_user_id=current_user.id,
            note="Trusted receiver verified",
        )
        _notify_ride_event(
            session,
            ride,
            event_type="dropoff_verified",
            parent_message="Trusted receiver verified successfully.",
            driver_message="Dropoff verified successfully.",
        )
    elif attempt_number >= 3:
        response["action"] = "verification_failed_max_attempts"
        response["message"] = "Verification failed 3 times. Do not hand off dog and contact owner."
        _notify_ride_event(
            session,
            ride,
            event_type="dropoff_verification_failed",
            parent_message="Dropoff verification failed 3 times. Driver was instructed to hold your dog and contact you.",
            driver_message="Verification failed 3 times. Contact the dog owner.",
        )

    session.add(ride)
    session.commit()
    await realtime_manager.broadcast_ride(
        ride.id,
        {
            "event": "trusted_receiver_verification",
            "ride_id": ride.id,
            **response,
            "status": ride.status.value,
        },
    )
    return response


@router.post("/{ride_id}/verify/facility")
async def verify_facility_dropoff(
    ride_id: str,
    payload: FacilityDropoffVerificationRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    ride = _ride_or_404(session, ride_id)
    if not _driver_or_admin_for_ride(session, current_user.id, ride):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver or admin required")
    if ride.dropoff_type == DropoffType.TRUSTED_PERSON:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use trusted-person verification endpoint")
    if ride.status not in {RideStatus.ARRIVED_AT_DROPOFF, RideStatus.VERIFYING_RECEIVER}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride is not ready for dropoff verification")

    if ride.status == RideStatus.ARRIVED_AT_DROPOFF:
        validate_ride_transition(ride.status, RideStatus.DOG_DELIVERED)
    ride.status = RideStatus.DOG_DELIVERED
    ride.dropoff_verification_photo_url = payload.photo_url
    ride.status_updated_at = utcnow()
    ride.updated_at = utcnow()
    create_ride_status_event(
        session,
        ride.id,
        RideStatus.DOG_DELIVERED,
        created_by_user_id=current_user.id,
        note="Facility handoff verified",
        metadata={"staff_name": payload.staff_name, "photo_url": payload.photo_url},
    )
    _notify_ride_event(
        session,
        ride,
        event_type="facility_dropoff_verified",
        parent_message=f"Dog handed off to {payload.staff_name}.",
        driver_message=f"Handoff recorded with {payload.staff_name}.",
    )
    session.add(ride)
    session.commit()
    await realtime_manager.broadcast_ride(
        ride.id,
        {
            "event": "facility_dropoff_verified",
            "ride_id": ride.id,
            "staff_name": payload.staff_name,
            "photo_url": payload.photo_url,
            "status": ride.status.value,
        },
    )
    return {"ride_id": ride.id, "status": ride.status.value, "staff_name": payload.staff_name}
