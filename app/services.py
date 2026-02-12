from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.config import settings
from app.models import (
    Dog,
    DogSize,
    Ride,
    RideStatus,
    RideStatusEvent,
    Role,
    User,
    UserRole,
)


RIDE_TRANSITIONS: dict[RideStatus, set[RideStatus]] = {
    RideStatus.REQUESTED: {
        RideStatus.ACCEPTED,
        RideStatus.CANCELLED,
    },
    RideStatus.ACCEPTED: {
        RideStatus.DRIVER_EN_ROUTE,
        RideStatus.CANCELLED,
    },
    RideStatus.DRIVER_EN_ROUTE: {
        RideStatus.ARRIVED_AT_PICKUP,
        RideStatus.CANCELLED,
    },
    RideStatus.ARRIVED_AT_PICKUP: {
        RideStatus.DOG_PICKED_UP,
        RideStatus.CANCELLED,
    },
    RideStatus.DOG_PICKED_UP: {
        RideStatus.IN_TRANSIT,
        RideStatus.CANCELLED,
    },
    RideStatus.IN_TRANSIT: {
        RideStatus.ARRIVED_AT_DROPOFF,
        RideStatus.CANCELLED,
    },
    RideStatus.ARRIVED_AT_DROPOFF: {
        RideStatus.VERIFYING_RECEIVER,
        RideStatus.DOG_DELIVERED,
    },
    RideStatus.VERIFYING_RECEIVER: {
        RideStatus.DOG_DELIVERED,
    },
    RideStatus.DOG_DELIVERED: {
        RideStatus.COMPLETED,
    },
    RideStatus.COMPLETED: set(),
    RideStatus.CANCELLED: set(),
}


def ensure_role(session: Session, user_id: str, role: Role) -> None:
    existing = session.exec(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role)
    ).first()
    if not existing:
        session.add(UserRole(user_id=user_id, role=role))


def list_user_roles(session: Session, user_id: str) -> list[Role]:
    roles = session.exec(select(UserRole).where(UserRole.user_id == user_id)).all()
    return [role.role for role in roles]


def assert_ride_access(session: Session, ride: Ride, current_user: User) -> None:
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN in roles:
        return
    if ride.dog_parent_user_id == current_user.id:
        return
    if ride.driver_user_id == current_user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ride access denied")


def create_ride_status_event(
    session: Session,
    ride_id: str,
    status_value: RideStatus,
    created_by_user_id: str | None = None,
    note: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RideStatusEvent:
    event = RideStatusEvent(
        ride_id=ride_id,
        status=status_value,
        created_by_user_id=created_by_user_id,
        note=note,
        metadata_json=metadata,
    )
    session.add(event)
    return event


def validate_ride_transition(current_status: RideStatus, next_status: RideStatus) -> None:
    allowed = RIDE_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition {current_status.value} -> {next_status.value}",
        )


def size_surcharge(size: DogSize) -> float:
    if size == DogSize.MEDIUM:
        return settings.size_surcharge_medium
    if size == DogSize.LARGE:
        return settings.size_surcharge_large
    if size == DogSize.XLARGE:
        return settings.size_surcharge_xlarge
    return 0.0


def calculate_estimated_fare(
    dog: Dog,
    distance_km: float,
    duration_minutes: float,
    dog_count: int = 1,
    surge_multiplier: float = 1.0,
) -> dict[str, float]:
    base = settings.base_fare
    distance_component = max(0.0, distance_km) * settings.per_km_fare
    duration_component = max(0.0, duration_minutes) * settings.per_minute_fare
    size_component = size_surcharge(dog.size)
    additional_dogs = max(0, dog_count - 1)
    additional_dog_component = additional_dogs * settings.additional_dog_fee
    subtotal = base + distance_component + duration_component + size_component + additional_dog_component
    total = round(subtotal * max(1.0, surge_multiplier), 2)
    return {
        "base_fare": round(base, 2),
        "distance_component": round(distance_component, 2),
        "duration_component": round(duration_component, 2),
        "size_surcharge": round(size_component, 2),
        "additional_dog_fee": round(additional_dog_component, 2),
        "surge_multiplier": round(max(1.0, surge_multiplier), 2),
        "fare_total": total,
    }


def cancel_fee_for_ride(ride: Ride, now: datetime) -> float:
    if ride.requested_at:
        elapsed_min = (now - ride.requested_at).total_seconds() / 60
    else:
        elapsed_min = settings.free_cancel_window_minutes + 1
    if elapsed_min <= settings.free_cancel_window_minutes:
        return 0.0
    if ride.status in {RideStatus.REQUESTED, RideStatus.ACCEPTED, RideStatus.DRIVER_EN_ROUTE}:
        return settings.cancel_fee_en_route
    if ride.status in {
        RideStatus.ARRIVED_AT_PICKUP,
        RideStatus.DOG_PICKED_UP,
        RideStatus.IN_TRANSIT,
        RideStatus.ARRIVED_AT_DROPOFF,
        RideStatus.VERIFYING_RECEIVER,
    }:
        return settings.cancel_fee_with_dog
    return 0.0
