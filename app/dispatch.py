from __future__ import annotations

from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from sqlmodel import Session, select

from app.config import settings
from app.models import (
    Dog,
    DogSize,
    DriverApprovalStatus,
    DriverLocationUpdate,
    DriverOfferResponse,
    DriverProfile,
    RecurringRidePlan,
    Ride,
    RideDispatchAttempt,
    RideStatus,
)
from app.security import utcnow
from app.services import calculate_estimated_fare, create_ride_status_event


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


def dog_requires_crate(dog: Dog) -> bool:
    special = (dog.special_needs or "").lower()
    temperament = (dog.temperament_notes or "").lower()
    return "crate" in special or "crate" in temperament or "kennel" in special


def size_rank(size: DogSize) -> int:
    if size == DogSize.SMALL:
        return 1
    if size == DogSize.MEDIUM:
        return 2
    if size == DogSize.LARGE:
        return 3
    return 4


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return radius_km * c


def _latest_driver_locations(session: Session) -> dict[str, DriverLocationUpdate]:
    updates = session.exec(select(DriverLocationUpdate).order_by(DriverLocationUpdate.recorded_at.desc())).all()
    latest: dict[str, DriverLocationUpdate] = {}
    for update in updates:
        if update.driver_user_id not in latest:
            latest[update.driver_user_id] = update
    return latest


def _driver_eligible_for_dog(driver: DriverProfile, dog: Dog, dog_count: int) -> bool:
    if driver.approval_status != DriverApprovalStatus.APPROVED:
        return False
    if not driver.is_online:
        return False
    if driver.rating < settings.driver_minimum_rating:
        return False
    if size_rank(driver.max_dog_size) < size_rank(dog.size):
        return False
    if driver.max_dogs_per_ride < dog_count:
        return False
    if dog_requires_crate(dog) and not driver.has_crate:
        return False
    return True


def _candidate_drivers(
    session: Session,
    ride: Ride,
    dog: Dog,
    radius_km: float,
) -> list[tuple[DriverProfile, float]]:
    drivers = session.exec(select(DriverProfile)).all()
    latest_locations = _latest_driver_locations(session)
    candidates: list[tuple[DriverProfile, float]] = []

    for driver in drivers:
        if not _driver_eligible_for_dog(driver, dog, ride.dog_count):
            continue
        location = latest_locations.get(driver.user_id)
        if not location:
            continue
        if ride.pickup_latitude is None or ride.pickup_longitude is None:
            distance = 0.0
        else:
            distance = haversine_km(
                ride.pickup_latitude,
                ride.pickup_longitude,
                location.latitude,
                location.longitude,
            )
        if distance <= radius_km:
            candidates.append((driver, round(distance, 3)))

    candidates.sort(key=lambda item: item[1])
    return candidates


def expire_pending_offers(session: Session, ride: Ride) -> int:
    now = utcnow()
    pending = session.exec(
        select(RideDispatchAttempt).where(
            RideDispatchAttempt.ride_id == ride.id,
            RideDispatchAttempt.response == DriverOfferResponse.PENDING,
        )
    ).all()
    changed = 0
    for attempt in pending:
        expires_at = _aware(attempt.expires_at)
        if expires_at and expires_at <= now:
            attempt.response = DriverOfferResponse.TIMED_OUT
            attempt.responded_at = now
            session.add(attempt)
            changed += 1
    return changed


def current_pending_offer(session: Session, ride_id: str) -> RideDispatchAttempt | None:
    now = utcnow()
    attempts = session.exec(
        select(RideDispatchAttempt)
        .where(
            RideDispatchAttempt.ride_id == ride_id,
            RideDispatchAttempt.response == DriverOfferResponse.PENDING,
        )
        .order_by(RideDispatchAttempt.offered_at.desc())
    ).all()
    for attempt in attempts:
        expires_at = _aware(attempt.expires_at)
        if expires_at and expires_at > now:
            return attempt
    return None


def dispatch_ride_once(session: Session, ride: Ride) -> dict:
    if ride.status != RideStatus.REQUESTED or ride.driver_user_id:
        return {"action": "skipped"}

    dog = session.get(Dog, ride.dog_id)
    if not dog:
        return {"action": "failed", "reason": "dog_not_found"}

    expire_pending_offers(session, ride)
    existing_offer = current_pending_offer(session, ride.id)
    if existing_offer:
        return {"action": "pending_offer_exists", "attempt_id": existing_offer.id}

    radius = ride.dispatch_radius_km or settings.dispatch_initial_radius_km
    candidates = _candidate_drivers(session, ride, dog, radius)
    offered_driver_ids = {
        attempt.driver_user_id
        for attempt in session.exec(select(RideDispatchAttempt).where(RideDispatchAttempt.ride_id == ride.id)).all()
    }
    next_candidate = next((item for item in candidates if item[0].user_id not in offered_driver_ids), None)
    if not next_candidate:
        if radius < settings.dispatch_max_radius_km:
            ride.dispatch_radius_km = min(radius + settings.dispatch_radius_step_km, settings.dispatch_max_radius_km)
            ride.last_dispatch_at = utcnow()
            session.add(ride)
            return {"action": "radius_expanded", "radius_km": ride.dispatch_radius_km}
        return {"action": "no_driver_found", "radius_km": radius}

    existing_attempts = session.exec(select(RideDispatchAttempt).where(RideDispatchAttempt.ride_id == ride.id)).all()
    sequence_number = len(existing_attempts) + 1
    driver, distance = next_candidate
    now = utcnow()
    attempt = RideDispatchAttempt(
        ride_id=ride.id,
        driver_user_id=driver.user_id,
        sequence_number=sequence_number,
        radius_km=radius,
        distance_km=distance,
        offered_at=now,
        expires_at=now + timedelta(seconds=settings.dispatch_offer_timeout_seconds),
    )
    ride.last_dispatch_at = now
    session.add(ride)
    session.add(attempt)
    session.flush()
    return {
        "action": "offered",
        "attempt_id": attempt.id,
        "driver_user_id": driver.user_id,
        "distance_km": distance,
        "expires_in_seconds": settings.dispatch_offer_timeout_seconds,
    }


def respond_to_offer(
    session: Session,
    ride: Ride,
    driver_user_id: str,
    accept: bool,
    decline_reason: str | None = None,
) -> dict:
    pending = current_pending_offer(session, ride.id)
    if not pending or pending.driver_user_id != driver_user_id:
        return {"action": "no_pending_offer"}

    now = utcnow()
    pending.responded_at = now
    if accept:
        pending.response = DriverOfferResponse.ACCEPTED
        ride.driver_user_id = driver_user_id
        ride.status = RideStatus.ACCEPTED
        ride.accepted_at = now
        ride.matched_at = now
        ride.status_updated_at = now
        ride.updated_at = now
        create_ride_status_event(
            session,
            ride_id=ride.id,
            status_value=RideStatus.ACCEPTED,
            created_by_user_id=driver_user_id,
            note="Driver accepted dispatch offer",
        )
        session.add(ride)
        session.add(pending)
        return {"action": "accepted", "driver_user_id": driver_user_id}

    pending.response = DriverOfferResponse.DECLINED
    pending.decline_reason = decline_reason
    session.add(pending)
    return {"action": "declined", "driver_user_id": driver_user_id}


def _next_run(current, recurring_rule: str, weekday: int):
    if recurring_rule == "daily":
        return current + timedelta(days=1)
    if recurring_rule == "weekly":
        return current + timedelta(days=7)
    if recurring_rule == "weekdays":
        next_dt = current + timedelta(days=1)
        while next_dt.weekday() > 4:
            next_dt = next_dt + timedelta(days=1)
        return next_dt
    if recurring_rule.startswith("every_") and recurring_rule.endswith("_days"):
        raw = recurring_rule[len("every_") : -len("_days")]
        if raw.isdigit():
            return current + timedelta(days=max(1, int(raw)))
    if recurring_rule.startswith("weekday_"):
        target = recurring_rule.split("weekday_")[-1]
        mapping = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        target_weekday = mapping.get(target, weekday)
        next_dt = current + timedelta(days=1)
        while next_dt.weekday() != target_weekday:
            next_dt = next_dt + timedelta(days=1)
        return next_dt
    return None


def generate_recurring_rides(session: Session) -> int:
    now = utcnow()
    plans = session.exec(
        select(RecurringRidePlan).where(
            RecurringRidePlan.is_active.is_(True),
            RecurringRidePlan.next_run_at <= now,
        )
    ).all()
    generated = 0
    for plan in plans:
        dog = session.get(Dog, plan.dog_id)
        if not dog:
            plan.is_active = False
            session.add(plan)
            continue
        fare = calculate_estimated_fare(
            dog=dog,
            distance_km=plan.distance_km,
            duration_minutes=plan.duration_minutes,
            dog_count=plan.dog_count,
            surge_multiplier=1.0,
        )
        ride = Ride(
            dog_parent_user_id=plan.owner_user_id,
            dog_id=plan.dog_id,
            dog_count=plan.dog_count,
            pickup_label=plan.pickup_label,
            pickup_address=plan.pickup_address,
            pickup_latitude=plan.pickup_latitude,
            pickup_longitude=plan.pickup_longitude,
            dropoff_label=plan.dropoff_label,
            dropoff_address=plan.dropoff_address,
            dropoff_latitude=plan.dropoff_latitude,
            dropoff_longitude=plan.dropoff_longitude,
            dropoff_type=plan.dropoff_type,
            trusted_receiver_id=plan.trusted_receiver_id,
            scheduled_for=plan.next_run_at,
            recurring_rule=plan.recurring_rule,
            special_instructions=plan.special_instructions,
            fare_total=fare["fare_total"],
            base_fare=fare["base_fare"],
            distance_km=plan.distance_km,
            duration_minutes=plan.duration_minutes,
            surge_multiplier=1.0,
            size_surcharge=fare["size_surcharge"],
            additional_dog_fee=fare["additional_dog_fee"],
        )
        session.add(ride)
        generated += 1

        next_run_ref = _aware(plan.next_run_at)
        nxt = _next_run(next_run_ref, plan.recurring_rule, next_run_ref.weekday())
        if nxt:
            plan.next_run_at = nxt
            plan.updated_at = now
            session.add(plan)
        else:
            plan.is_active = False
            plan.updated_at = now
            session.add(plan)
    return generated


def run_scheduled_matching(session: Session) -> list[str]:
    now = utcnow()
    horizon = now + timedelta(minutes=settings.scheduled_match_lead_minutes)
    rides = session.exec(
        select(Ride).where(
            Ride.status == RideStatus.REQUESTED,
            Ride.driver_user_id.is_(None),
            Ride.scheduled_for.is_not(None),
            Ride.scheduled_for <= horizon,
        )
    ).all()
    dispatched: list[str] = []
    for ride in rides:
        result = dispatch_ride_once(session, ride)
        if result.get("action") in {"offered", "pending_offer_exists", "radius_expanded"}:
            dispatched.append(ride.id)
    return dispatched


def run_pending_dispatch(session: Session) -> list[str]:
    now = utcnow()
    rides = session.exec(
        select(Ride).where(
            Ride.status == RideStatus.REQUESTED,
            Ride.driver_user_id.is_(None),
        )
    ).all()
    processed: list[str] = []
    for ride in rides:
        if ride.scheduled_for and _aware(ride.scheduled_for) > now + timedelta(minutes=settings.scheduled_match_lead_minutes):
            continue
        result = dispatch_ride_once(session, ride)
        if result.get("action") not in {"skipped"}:
            processed.append(ride.id)
    return processed
