from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.config import settings
from app.models import (
    DriverPayout,
    PayoutMethod,
    PayoutStatus,
    SubscriptionPlan,
    SubscriptionStatus,
    UserSubscription,
)
from app.security import utcnow


def _aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


def next_weekly_payout_time(from_dt=None):
    now = _aware(from_dt or utcnow())
    days_ahead = (settings.weekly_payout_weekday - now.weekday()) % 7
    candidate = now + timedelta(days=days_ahead)
    if days_ahead == 0:
        candidate = candidate + timedelta(days=7)
    return candidate.replace(hour=12, minute=0, second=0, microsecond=0)


def get_or_create_default_plan(session: Session) -> SubscriptionPlan:
    plan = session.exec(select(SubscriptionPlan).where(SubscriptionPlan.code == "PAWRIDE_PASS")).first()
    if plan:
        return plan
    plan = SubscriptionPlan(
        code="PAWRIDE_PASS",
        name="PawRide Pass",
        monthly_price=settings.default_pass_price_monthly,
        discount_percent=settings.default_pass_discount_percent,
        priority_matching=True,
        is_active=True,
    )
    session.add(plan)
    session.flush()
    return plan


def active_subscription_for_user(session: Session, user_id: str) -> UserSubscription | None:
    now = utcnow()
    subs = session.exec(
        select(UserSubscription)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(UserSubscription.created_at.desc())
    ).all()
    for sub in subs:
        renews_at = _aware(sub.renews_at)
        if renews_at and renews_at < now:
            sub.status = SubscriptionStatus.EXPIRED
            sub.updated_at = now
            session.add(sub)
            continue
        return sub
    return None


def subscription_discount_percent(session: Session, user_id: str) -> float:
    sub = active_subscription_for_user(session, user_id)
    if not sub:
        return 0.0
    plan = session.get(SubscriptionPlan, sub.plan_id)
    if not plan or not plan.is_active:
        return 0.0
    return plan.discount_percent


def schedule_driver_payout(
    session: Session,
    driver_user_id: str,
    payment_id: str,
    amount: float,
    currency: str,
) -> DriverPayout:
    payout = DriverPayout(
        driver_user_id=driver_user_id,
        payment_id=payment_id,
        amount=amount,
        currency=currency,
        status=PayoutStatus.PENDING,
        method=PayoutMethod.WEEKLY,
        scheduled_for=next_weekly_payout_time(),
    )
    session.add(payout)
    return payout


def process_weekly_payouts(session: Session) -> int:
    now = utcnow()
    payouts = session.exec(
        select(DriverPayout).where(
            DriverPayout.status == PayoutStatus.PENDING,
            DriverPayout.method == PayoutMethod.WEEKLY,
            DriverPayout.scheduled_for <= now,
        )
    ).all()
    for payout in payouts:
        payout.status = PayoutStatus.PAID
        payout.processed_at = now
        payout.updated_at = now
        session.add(payout)
    return len(payouts)


def process_instant_payout(session: Session, payout: DriverPayout) -> DriverPayout:
    if payout.status != PayoutStatus.PENDING:
        return payout
    fee = round((payout.amount * settings.instant_payout_fee_percent) / 100.0, 2)
    payout.fee_amount = fee
    payout.amount = round(max(0.0, payout.amount - fee), 2)
    payout.method = PayoutMethod.INSTANT
    payout.status = PayoutStatus.PAID
    payout.processed_at = utcnow()
    payout.updated_at = utcnow()
    session.add(payout)
    return payout
