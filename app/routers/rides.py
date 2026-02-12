from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import (
    Dog,
    DropoffType,
    ReceiverVerificationAttempt,
    Ride,
    RideStatus,
    RideStatusEvent,
    Role,
    TrustedReceiver,
    UserRole,
)
from app.realtime import realtime_manager
from app.schemas import (
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
    session.commit()
    session.refresh(ride)

    await realtime_manager.broadcast_ride(
        ride.id,
        {"event": "ride_requested", "ride_id": ride.id, "status": ride.status.value},
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

    create_ride_status_event(
        session,
        ride.id,
        payload.status,
        created_by_user_id=current_user.id,
        note=payload.note,
        metadata=payload.metadata,
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
    elif attempt_number >= 3:
        response["action"] = "verification_failed_max_attempts"
        response["message"] = "Verification failed 3 times. Do not hand off dog and contact owner."

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
