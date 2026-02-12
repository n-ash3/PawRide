from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import (
    BackgroundCheckStatus,
    DogSize,
    DisputeStatus,
    DriverApprovalStatus,
    DropoffType,
    NotificationChannel,
    NotificationStatus,
    PayoutStatus,
    PaymentStatus,
    RideStatus,
    Role,
    SubscriptionStatus,
)


class UserOut(BaseModel):
    id: str
    phone_number: str
    name: str | None = None
    photo_url: str | None = None
    active_role: Role
    roles: list[Role]


class OTPRequest(BaseModel):
    phone_number: str


class OTPVerifyRequest(BaseModel):
    phone_number: str
    code: str = Field(min_length=6, max_length=6)
    name: str | None = None
    photo_url: str | None = None
    requested_roles: list[Role] | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class SwitchRoleRequest(BaseModel):
    role: Role


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class DogCreate(BaseModel):
    name: str
    breed: str | None = None
    size: DogSize
    weight_kg: float | None = None
    age_years: int | None = None
    photo_url: str | None = None
    temperament_notes: str | None = None
    special_needs: str | None = None
    vaccination_status: str = "unknown"
    vaccination_document_url: str | None = None
    vaccination_expires_at: datetime | None = None
    vet_name: str | None = None
    vet_phone: str | None = None
    vet_address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None


class DogUpdate(BaseModel):
    name: str | None = None
    breed: str | None = None
    size: DogSize | None = None
    weight_kg: float | None = None
    age_years: int | None = None
    photo_url: str | None = None
    temperament_notes: str | None = None
    special_needs: str | None = None
    vaccination_status: str | None = None
    vaccination_document_url: str | None = None
    vaccination_expires_at: datetime | None = None
    vet_name: str | None = None
    vet_phone: str | None = None
    vet_address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    emergency_contact_relationship: str | None = None


class TrustedReceiverCreate(BaseModel):
    name: str
    phone_number: str
    relationship: str | None = None
    photo_url: str | None = None
    pin_code: str | None = Field(default=None, min_length=6, max_length=6)


class TrustedReceiverUpdate(BaseModel):
    name: str | None = None
    phone_number: str | None = None
    relationship: str | None = None
    photo_url: str | None = None
    pin_code: str | None = Field(default=None, min_length=6, max_length=6)
    is_active: bool | None = None


class SavedDestinationCreate(BaseModel):
    label: str
    destination_type: str
    address_line1: str
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "US"
    latitude: float | None = None
    longitude: float | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    special_instructions: str | None = None
    is_favorite: bool = False


class SavedDestinationUpdate(BaseModel):
    label: str | None = None
    destination_type: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    special_instructions: str | None = None
    is_favorite: bool | None = None


class RideRequestCreate(BaseModel):
    dog_id: str
    pickup_label: str | None = None
    pickup_address: str
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    dropoff_label: str | None = None
    dropoff_address: str
    dropoff_latitude: float | None = None
    dropoff_longitude: float | None = None
    dropoff_type: DropoffType
    trusted_receiver_id: str | None = None
    scheduled_for: datetime | None = None
    recurring_rule: str | None = None
    special_instructions: str | None = None
    distance_km: float = 0.0
    duration_minutes: float = 0.0
    surge_multiplier: float = 1.0
    dog_count: int = 1
    auto_dispatch: bool = True


class RideAssignDriverRequest(BaseModel):
    driver_user_id: str


class RideStatusUpdateRequest(BaseModel):
    status: RideStatus
    note: str | None = None
    metadata: dict | None = None


class RideCancelRequest(BaseModel):
    reason: str | None = None


class DispatchResponseRequest(BaseModel):
    accept: bool
    decline_reason: str | None = None


class TrustedDropoffVerificationRequest(BaseModel):
    receiver_id: str
    pin_code: str = Field(min_length=6, max_length=6)
    photo_url: str
    photo_match: bool = False


class FacilityDropoffVerificationRequest(BaseModel):
    staff_name: str
    photo_url: str


class DriverProfileUpsertRequest(BaseModel):
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_color: str | None = None
    vehicle_plate: str | None = None
    vehicle_photo_url: str | None = None
    has_crate: bool | None = None
    seat_cover: bool | None = None
    ac_available: bool | None = None
    max_dog_size: DogSize | None = None
    max_dogs_per_ride: int | None = None
    accommodation_notes: str | None = None
    license_doc_url: str | None = None
    insurance_doc_url: str | None = None
    registration_doc_url: str | None = None
    animal_handling_cert_url: str | None = None
    background_check_status: BackgroundCheckStatus | None = None
    camera_device_ref: str | None = None


class DriverOnlineRequest(BaseModel):
    is_online: bool


class BecomeDriverRequest(BaseModel):
    create_profile_if_missing: bool = True


class PaymentMethodCreateRequest(BaseModel):
    provider_method_id: str
    brand: str | None = None
    last4: str | None = None
    exp_month: int | None = None
    exp_year: int | None = None
    is_default: bool = False


class ChargeRideRequest(BaseModel):
    ride_id: str
    payment_method_id: str
    tip_amount: float = 0.0
    promo_code: str | None = None


class RefundPaymentRequest(BaseModel):
    amount: float | None = None
    reason: str | None = None


class PromoCodeCreateRequest(BaseModel):
    code: str
    discount_percent: float = Field(ge=0, le=100)
    usage_limit: int | None = None
    expires_at: datetime | None = None
    is_active: bool = True


class RatingCreateRequest(BaseModel):
    ride_id: str
    to_user_id: str
    score: int = Field(ge=1, le=5)
    dog_comfort_score: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None
    tags: list[str] = Field(default_factory=list)


class CameraStartRequest(BaseModel):
    stream_url: str | None = None


class CameraSnapshotRequest(BaseModel):
    snapshot_url: str
    details: str | None = None


class CameraAlertRequest(BaseModel):
    event_type: str
    details: str | None = None


class AdminDriverApprovalRequest(BaseModel):
    approval_status: DriverApprovalStatus
    note: str | None = None


class AdminAssignRoleRequest(BaseModel):
    role: Role


class AdminRemoveRoleRequest(BaseModel):
    role: Role


class LocationUpdatePayload(BaseModel):
    latitude: float
    longitude: float
    heading: float | None = None
    speed_kph: float | None = None
    ride_id: str | None = None


class PaymentOut(BaseModel):
    id: str
    ride_id: str | None
    status: PaymentStatus
    amount: float
    tip_amount: float
    currency: str
    promo_code: str | None
    discount_amount: float
    driver_payout_amount: float
    platform_fee_amount: float
    created_at: datetime


class SubscriptionCreateRequest(BaseModel):
    plan_code: str = "PAWRIDE_PASS"


class SubscriptionCancelRequest(BaseModel):
    immediate: bool = False


class PayoutInstantRequest(BaseModel):
    payout_id: str


class PlatformSettingUpsertRequest(BaseModel):
    key: str
    value: str


class DisputeCreateRequest(BaseModel):
    ride_id: str
    against_user_id: str | None = None
    reason: str
    details: str | None = None


class DisputeResolveRequest(BaseModel):
    status: DisputeStatus
    resolution_note: str | None = None
    refund_payment_id: str | None = None


class NotificationMarkReadRequest(BaseModel):
    notification_ids: list[str] = Field(default_factory=list)


class NotificationOut(BaseModel):
    id: str
    notification_type: str
    title: str
    body: str
    channel: NotificationChannel
    status: NotificationStatus
    created_at: datetime
    read_at: datetime | None = None


class DriverPayoutOut(BaseModel):
    id: str
    payment_id: str | None
    amount: float
    currency: str
    status: PayoutStatus
    method: str
    fee_amount: float
    scheduled_for: datetime
    processed_at: datetime | None = None


class UserSubscriptionOut(BaseModel):
    id: str
    plan_id: str
    status: SubscriptionStatus
    started_at: datetime
    renews_at: datetime | None
    ended_at: datetime | None
