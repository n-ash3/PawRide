from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import (
    Dog,
    DriverApprovalStatus,
    DriverProfile,
    Payment,
    PaymentStatus,
    PromoCode,
    Ride,
    RideStatus,
    Role,
    User,
    UserRole,
)
from app.schemas import AdminAssignRoleRequest, AdminDriverApprovalRequest, AdminRemoveRoleRequest
from app.security import utcnow
from app.services import ensure_role, list_user_roles

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(session: Session, current_user_id: str) -> None:
    roles = set(list_user_roles(session, current_user_id))
    if Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def _aware(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


@router.get("/users")
def list_users(
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[dict]:
    _require_admin(session, current_user.id)
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if search:
        stmt = select(User).where(User.phone_number.contains(search)).order_by(User.created_at.desc()).limit(limit)
    users = session.exec(stmt).all()
    response = []
    for user in users:
        response.append(
            {
                "id": user.id,
                "phone_number": user.phone_number,
                "name": user.name,
                "active_role": user.active_role,
                "roles": list_user_roles(session, user.id),
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
        )
    return response


@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
def add_user_role(
    user_id: str,
    payload: AdminAssignRoleRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    _require_admin(session, current_user.id)
    target_user = session.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ensure_role(session, target_user.id, payload.role)
    session.commit()
    return {"user_id": user_id, "roles": list_user_roles(session, user_id)}


@router.post("/users/{user_id}/roles/remove")
def remove_user_role(
    user_id: str,
    payload: AdminRemoveRoleRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    _require_admin(session, current_user.id)
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    roles_before = list_user_roles(session, user_id)
    if payload.role not in roles_before:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found")
    remaining_roles = [role for role in roles_before if role != payload.role]
    if not remaining_roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must keep at least one role")

    role_row = session.exec(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role == payload.role)
    ).first()
    session.delete(role_row)
    if user.active_role == payload.role:
        user.active_role = remaining_roles[0]
        user.updated_at = utcnow()
        session.add(user)
    session.commit()
    return {"user_id": user_id, "roles": remaining_roles}


@router.get("/rides")
def list_all_rides(
    status_filter: RideStatus | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[Ride]:
    _require_admin(session, current_user.id)
    stmt = select(Ride).order_by(Ride.created_at.desc()).limit(limit)
    if status_filter:
        stmt = (
            select(Ride)
            .where(Ride.status == status_filter)
            .order_by(Ride.created_at.desc())
            .limit(limit)
        )
    return session.exec(stmt).all()


@router.get("/drivers/pending")
def pending_drivers(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[DriverProfile]:
    _require_admin(session, current_user.id)
    return session.exec(
        select(DriverProfile).where(DriverProfile.approval_status == DriverApprovalStatus.PENDING)
    ).all()


@router.post("/drivers/{user_id}/approval")
def approve_or_reject_driver(
    user_id: str,
    payload: AdminDriverApprovalRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> DriverProfile:
    _require_admin(session, current_user.id)
    profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == user_id)).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    profile.approval_status = payload.approval_status
    profile.updated_at = utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/analytics/overview")
def analytics_overview(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    _require_admin(session, current_user.id)
    active_statuses = {
        RideStatus.ACCEPTED,
        RideStatus.DRIVER_EN_ROUTE,
        RideStatus.ARRIVED_AT_PICKUP,
        RideStatus.DOG_PICKED_UP,
        RideStatus.IN_TRANSIT,
        RideStatus.ARRIVED_AT_DROPOFF,
        RideStatus.VERIFYING_RECEIVER,
    }
    rides = session.exec(select(Ride)).all()
    users = session.exec(select(User)).all()
    drivers = session.exec(select(DriverProfile)).all()
    dogs = session.exec(select(Dog)).all()
    payments = session.exec(select(Payment).where(Payment.status == PaymentStatus.CHARGED)).all()
    revenue = round(sum(payment.amount for payment in payments), 2)
    return {
        "active_rides": len([ride for ride in rides if ride.status in active_statuses]),
        "completed_rides": len([ride for ride in rides if ride.status == RideStatus.COMPLETED]),
        "cancelled_rides": len([ride for ride in rides if ride.status == RideStatus.CANCELLED]),
        "total_revenue": revenue,
        "new_signups": len([user for user in users if (utcnow() - _aware(user.created_at)).days < 1]),
        "drivers_pending": len([driver for driver in drivers if driver.approval_status.value == "pending"]),
        "drivers_online": len([driver for driver in drivers if driver.is_online]),
        "dog_count": len(dogs),
    }


@router.get("/analytics/dog-size-distribution")
def dog_size_distribution(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    _require_admin(session, current_user.id)
    dogs = session.exec(select(Dog)).all()
    distribution: dict[str, int] = {}
    for dog in dogs:
        distribution[dog.size.value] = distribution.get(dog.size.value, 0) + 1
    return distribution


@router.get("/promo-codes")
def list_promo_codes(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[PromoCode]:
    _require_admin(session, current_user.id)
    return session.exec(select(PromoCode).order_by(PromoCode.created_at.desc())).all()
