from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Role(str, Enum):
    DOG_PARENT = "dog_parent"
    DRIVER = "driver"
    ADMIN = "admin"


class DogSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"


class RideStatus(str, Enum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    DRIVER_EN_ROUTE = "driver_en_route"
    ARRIVED_AT_PICKUP = "arrived_at_pickup"
    DOG_PICKED_UP = "dog_picked_up"
    IN_TRANSIT = "in_transit"
    ARRIVED_AT_DROPOFF = "arrived_at_dropoff"
    VERIFYING_RECEIVER = "verifying_receiver"
    DOG_DELIVERED = "dog_delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DropoffType(str, Enum):
    DAYCARE = "daycare"
    GROOMER = "groomer"
    VET = "vet"
    TRUSTED_PERSON = "trusted_person"
    HOME = "home"
    PARK = "park"
    OTHER = "other"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CHARGED = "charged"
    REFUNDED = "refunded"
    FAILED = "failed"


class DriverApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class BackgroundCheckStatus(str, Enum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    CLEARED = "cleared"
    FAILED = "failed"


class User(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    phone_number: str = Field(index=True, unique=True)
    name: str | None = None
    photo_url: str | None = None
    active_role: Role = Field(default=Role.DOG_PARENT)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UserRole(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    role: Role = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)


class OTPCode(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    phone_number: str = Field(index=True)
    code: str
    expires_at: datetime
    consumed: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class RefreshToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(index=True, unique=True)
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Dog(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    breed: str | None = None
    size: DogSize
    weight_kg: float | None = None
    age_years: int | None = None
    photo_url: str | None = None
    temperament_notes: str | None = None
    special_needs: str | None = None
    vaccination_status: str = Field(default="unknown")
    vaccination_document_url: str | None = None
    vaccination_expires_at: datetime | None = None
    vet_name: str | None = None
    vet_phone: str | None = None
    vet_address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class TrustedReceiver(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    phone_number: str
    relationship: str | None = None
    photo_url: str | None = None
    pin_code: str = Field(index=True, min_length=6, max_length=6)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SavedDestination(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    owner_user_id: str = Field(foreign_key="user.id", index=True)
    label: str
    destination_type: str
    address_line1: str
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = "US"
    latitude: float | None = None
    longitude: float | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    special_instructions: str | None = None
    is_favorite: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Ride(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    dog_parent_user_id: str = Field(foreign_key="user.id", index=True)
    dog_id: str = Field(foreign_key="dog.id", index=True)
    driver_user_id: str | None = Field(default=None, foreign_key="user.id", index=True)
    trusted_receiver_id: str | None = Field(default=None, foreign_key="trustedreceiver.id", index=True)

    pickup_label: str | None = None
    pickup_address: str
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None

    dropoff_label: str | None = None
    dropoff_address: str
    dropoff_latitude: float | None = None
    dropoff_longitude: float | None = None
    dropoff_type: DropoffType

    scheduled_for: datetime | None = Field(default=None, index=True)
    recurring_rule: str | None = None
    special_instructions: str | None = None

    status: RideStatus = Field(default=RideStatus.REQUESTED, index=True)
    status_updated_at: datetime = Field(default_factory=utcnow)

    camera_stream_url: str | None = None
    pickup_verification_photo_url: str | None = None
    dropoff_verification_photo_url: str | None = None

    fare_total: float = 0.0
    base_fare: float = 0.0
    distance_km: float = 0.0
    duration_minutes: float = 0.0
    surge_multiplier: float = 1.0
    size_surcharge: float = 0.0
    additional_dog_fee: float = 0.0
    promo_discount_amount: float = 0.0

    cancellation_fee: float = 0.0
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None

    requested_at: datetime = Field(default_factory=utcnow)
    accepted_at: datetime | None = None
    pickup_arrived_at: datetime | None = None
    dog_picked_up_at: datetime | None = None
    dropoff_arrived_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class RideStatusEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ride_id: str = Field(foreign_key="ride.id", index=True)
    status: RideStatus
    note: str | None = None
    created_by_user_id: str | None = Field(default=None, foreign_key="user.id")
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utcnow)


class DriverProfile(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, unique=True)
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_color: str | None = None
    vehicle_plate: str | None = None
    vehicle_photo_url: str | None = None

    has_crate: bool = Field(default=False)
    seat_cover: bool = Field(default=False)
    ac_available: bool = Field(default=False)
    max_dog_size: DogSize = Field(default=DogSize.MEDIUM)
    max_dogs_per_ride: int = Field(default=1)
    accommodation_notes: str | None = None

    license_doc_url: str | None = None
    insurance_doc_url: str | None = None
    registration_doc_url: str | None = None
    animal_handling_cert_url: str | None = None

    background_check_status: BackgroundCheckStatus = Field(default=BackgroundCheckStatus.NOT_STARTED)
    approval_status: DriverApprovalStatus = Field(default=DriverApprovalStatus.PENDING, index=True)

    camera_device_ref: str | None = None
    rating: float = 5.0
    ride_count: int = 0
    is_online: bool = Field(default=False, index=True)
    total_earnings: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DriverLocationUpdate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    driver_user_id: str = Field(foreign_key="user.id", index=True)
    ride_id: str | None = Field(default=None, foreign_key="ride.id", index=True)
    latitude: float
    longitude: float
    heading: float | None = None
    speed_kph: float | None = None
    recorded_at: datetime = Field(default_factory=utcnow, index=True)


class PaymentMethod(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    provider: str = Field(default="stripe")
    provider_method_id: str
    brand: str | None = None
    last4: str | None = None
    exp_month: int | None = None
    exp_year: int | None = None
    is_default: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Payment(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    ride_id: str | None = Field(default=None, foreign_key="ride.id", index=True)
    payer_user_id: str = Field(foreign_key="user.id", index=True)
    driver_user_id: str | None = Field(default=None, foreign_key="user.id", index=True)
    stripe_payment_intent_id: str | None = None
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, index=True)
    amount: float = 0.0
    tip_amount: float = 0.0
    currency: str = "usd"
    promo_code: str | None = None
    discount_amount: float = 0.0
    driver_payout_amount: float = 0.0
    platform_fee_amount: float = 0.0
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Rating(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    ride_id: str = Field(foreign_key="ride.id", index=True)
    from_user_id: str = Field(foreign_key="user.id", index=True)
    to_user_id: str = Field(foreign_key="user.id", index=True)
    score: int = Field(ge=1, le=5)
    dog_comfort_score: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None
    tags_csv: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class PromoCode(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    code: str = Field(index=True, unique=True)
    discount_percent: float = Field(ge=0, le=100)
    usage_limit: int | None = None
    used_count: int = 0
    expires_at: datetime | None = None
    is_active: bool = Field(default=True)
    created_by_user_id: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)


class CameraEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ride_id: str = Field(foreign_key="ride.id", index=True)
    event_type: str = Field(index=True)
    details: str | None = None
    snapshot_url: str | None = None
    created_by_user_id: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)


class ReceiverVerificationAttempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ride_id: str = Field(foreign_key="ride.id", index=True)
    receiver_id: str = Field(foreign_key="trustedreceiver.id", index=True)
    attempt_number: int
    pin_entered: str | None = None
    pin_match: bool = False
    photo_url: str | None = None
    photo_match: bool = False
    success: bool = False
    created_at: datetime = Field(default_factory=utcnow)
