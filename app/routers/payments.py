from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.dependencies import get_current_user
from app.models import DriverProfile, Payment, PaymentMethod, PaymentStatus, PromoCode, Ride, Role
from app.schemas import (
    ChargeRideRequest,
    PaymentMethodCreateRequest,
    PromoCodeCreateRequest,
    RefundPaymentRequest,
)
from app.security import utcnow
from app.services import list_user_roles

router = APIRouter(prefix="/payments", tags=["payments"])


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


@router.post("/methods", status_code=status.HTTP_201_CREATED)
def add_payment_method(
    payload: PaymentMethodCreateRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> PaymentMethod:
    if payload.is_default:
        existing_defaults = session.exec(
            select(PaymentMethod).where(
                PaymentMethod.user_id == current_user.id,
                PaymentMethod.is_default.is_(True),
            )
        ).all()
        for method in existing_defaults:
            method.is_default = False
            session.add(method)
    method = PaymentMethod(user_id=current_user.id, **payload.model_dump())
    session.add(method)
    session.commit()
    session.refresh(method)
    return method


@router.get("/methods")
def list_payment_methods(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[PaymentMethod]:
    return session.exec(
        select(PaymentMethod).where(PaymentMethod.user_id == current_user.id).order_by(PaymentMethod.created_at.desc())
    ).all()


@router.post("/charge", status_code=status.HTTP_201_CREATED)
def charge_ride(
    payload: ChargeRideRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Payment:
    ride = session.get(Ride, payload.ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    roles = set(list_user_roles(session, current_user.id))
    if ride.dog_parent_user_id != current_user.id and Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Payment access denied")
    if not ride.driver_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride has no assigned driver")

    payment_method = session.get(PaymentMethod, payload.payment_method_id)
    if not payment_method or payment_method.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment method")

    existing_payment = session.exec(
        select(Payment).where(Payment.ride_id == ride.id, Payment.status == PaymentStatus.CHARGED)
    ).first()
    if existing_payment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride already charged")

    discount_amount = 0.0
    if payload.promo_code:
        promo = session.exec(select(PromoCode).where(PromoCode.code == payload.promo_code)).first()
        if not promo or not promo.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid promo code")
        if promo.expires_at and _aware(promo.expires_at) < utcnow():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promo code expired")
        if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promo code usage limit reached")
        discount_amount = round((ride.fare_total * promo.discount_percent) / 100.0, 2)
        promo.used_count += 1
        session.add(promo)

    subtotal = max(0.0, ride.fare_total - discount_amount)
    tip_amount = max(0.0, payload.tip_amount)
    total_amount = round(subtotal + tip_amount, 2)

    driver_base_payout = round(subtotal * settings.default_driver_commission_rate, 2)
    driver_payout_amount = round(driver_base_payout + tip_amount, 2)
    platform_fee_amount = round(total_amount - driver_payout_amount, 2)

    payment = Payment(
        ride_id=ride.id,
        payer_user_id=current_user.id,
        driver_user_id=ride.driver_user_id,
        stripe_payment_intent_id=f"pi_{uuid4().hex}",
        status=PaymentStatus.CHARGED,
        amount=total_amount,
        tip_amount=tip_amount,
        currency=settings.default_currency,
        promo_code=payload.promo_code,
        discount_amount=discount_amount,
        driver_payout_amount=driver_payout_amount,
        platform_fee_amount=platform_fee_amount,
    )
    session.add(payment)

    profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == ride.driver_user_id)).first()
    if profile:
        profile.total_earnings = round(profile.total_earnings + driver_payout_amount, 2)
        session.add(profile)

    session.commit()
    session.refresh(payment)
    return payment


@router.get("/history")
def payment_history(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[Payment]:
    roles = set(list_user_roles(session, current_user.id))
    stmt = select(Payment).order_by(Payment.created_at.desc())
    if Role.ADMIN not in roles:
        stmt = stmt.where((Payment.payer_user_id == current_user.id) | (Payment.driver_user_id == current_user.id))
    return session.exec(stmt).all()


@router.post("/{payment_id}/refund")
def refund_payment(
    payment_id: str,
    payload: RefundPaymentRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Payment:
    payment = session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    if payment.status != PaymentStatus.CHARGED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only charged payments can be refunded")

    refund_amount = payload.amount if payload.amount is not None else payment.amount
    if refund_amount <= 0 or refund_amount > payment.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refund amount")

    payment.status = PaymentStatus.REFUNDED
    payment.failure_reason = payload.reason
    payment.updated_at = utcnow()
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


@router.post("/promo-codes", status_code=status.HTTP_201_CREATED)
def create_promo_code(
    payload: PromoCodeCreateRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> PromoCode:
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    code = payload.code.upper().strip()
    existing = session.exec(select(PromoCode).where(PromoCode.code == code)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promo code already exists")
    promo = PromoCode(
        code=code,
        discount_percent=payload.discount_percent,
        usage_limit=payload.usage_limit,
        expires_at=payload.expires_at,
        is_active=payload.is_active,
        created_by_user_id=current_user.id,
    )
    session.add(promo)
    session.commit()
    session.refresh(promo)
    return promo
