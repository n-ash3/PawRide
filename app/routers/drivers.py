from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import DogSize, DriverProfile, DriverApprovalStatus, Payment, PaymentStatus, Role
from app.schemas import BecomeDriverRequest, DriverOnlineRequest, DriverProfileUpsertRequest
from app.security import utcnow
from app.services import ensure_role, list_user_roles

router = APIRouter(prefix="/drivers", tags=["drivers"])


def _ensure_driver_role(session: Session, user_id: str) -> None:
    roles = set(list_user_roles(session, user_id))
    if Role.DRIVER not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver role required")


def _compatible_driver_sizes(required_size: DogSize) -> list[DogSize]:
    if required_size == DogSize.SMALL:
        return [DogSize.SMALL, DogSize.MEDIUM, DogSize.LARGE, DogSize.XLARGE]
    if required_size == DogSize.MEDIUM:
        return [DogSize.MEDIUM, DogSize.LARGE, DogSize.XLARGE]
    if required_size == DogSize.LARGE:
        return [DogSize.LARGE, DogSize.XLARGE]
    return [DogSize.XLARGE]


@router.post("/become-driver")
def become_driver(
    payload: BecomeDriverRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    ensure_role(session, current_user.id, Role.DRIVER)
    if payload.create_profile_if_missing:
        profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == current_user.id)).first()
        if not profile:
            session.add(DriverProfile(user_id=current_user.id))
    session.commit()
    return {"message": "Driver role added", "approval_status": DriverApprovalStatus.PENDING.value}


@router.get("/me/profile")
def get_my_driver_profile(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> DriverProfile:
    _ensure_driver_role(session, current_user.id)
    profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == current_user.id)).first()
    if not profile:
        profile = DriverProfile(user_id=current_user.id)
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


@router.put("/me/profile")
def upsert_my_driver_profile(
    payload: DriverProfileUpsertRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> DriverProfile:
    _ensure_driver_role(session, current_user.id)
    profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == current_user.id)).first()
    if not profile:
        profile = DriverProfile(user_id=current_user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    profile.updated_at = utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.post("/me/online")
def set_driver_online_status(
    payload: DriverOnlineRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    _ensure_driver_role(session, current_user.id)
    profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == current_user.id)).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Driver profile not found")
    if profile.approval_status != DriverApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Driver is not approved (current status: {profile.approval_status.value})",
        )
    profile.is_online = payload.is_online
    profile.updated_at = utcnow()
    session.add(profile)
    session.commit()
    return {"is_online": profile.is_online}


@router.get("/me/earnings")
def driver_earnings(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> dict:
    _ensure_driver_role(session, current_user.id)
    profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == current_user.id)).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")
    payments = session.exec(
        select(Payment).where(
            Payment.driver_user_id == current_user.id,
            Payment.status == PaymentStatus.CHARGED,
        )
    ).all()
    total = round(sum(payment.driver_payout_amount for payment in payments), 2)
    tips = round(sum(payment.tip_amount for payment in payments), 2)
    return {
        "driver_user_id": current_user.id,
        "total_earnings": total,
        "tips_total": tips,
        "ride_count": profile.ride_count,
    }


@router.get("/available")
def list_available_drivers(
    required_size: DogSize = Query(default=DogSize.SMALL),
    minimum_rating: float = Query(default=4.0),
    session: Session = Depends(get_session),
    _current_user=Depends(get_current_user),
) -> list[DriverProfile]:
    # Distance/radius filtering can be layered on once geospatial indexing is added.
    compatible_sizes = _compatible_driver_sizes(required_size)
    return session.exec(
        select(DriverProfile).where(
            DriverProfile.is_online.is_(True),
            DriverProfile.approval_status == DriverApprovalStatus.APPROVED,
            DriverProfile.rating >= minimum_rating,
            DriverProfile.max_dog_size.in_(compatible_sizes),
        )
    ).all()
