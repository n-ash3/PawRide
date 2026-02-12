from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.dependencies import get_current_user
from app.models import OTPCode, RefreshToken, Role, User
from app.schemas import (
    AuthResponse,
    LogoutRequest,
    OTPRequest,
    OTPVerifyRequest,
    RefreshRequest,
    SwitchRoleRequest,
    UserOut,
)
from app.security import (
    create_access_token,
    create_refresh_token,
    generate_otp_code,
    hash_token,
    token_subject,
    utcnow,
)
from app.services import ensure_role, list_user_roles

router = APIRouter(prefix="/auth", tags=["auth"])


def _with_timezone(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utcnow().tzinfo)
    return dt


def _user_out(session: Session, user: User) -> UserOut:
    return UserOut(
        id=user.id,
        phone_number=user.phone_number,
        name=user.name,
        photo_url=user.photo_url,
        active_role=user.active_role,
        roles=list_user_roles(session, user.id),
    )


@router.post("/request-otp")
def request_otp(payload: OTPRequest, session: Session = Depends(get_session)) -> dict:
    code = generate_otp_code()
    otp = OTPCode(
        phone_number=payload.phone_number,
        code=code,
        expires_at=utcnow() + timedelta(minutes=settings.otp_exp_minutes),
    )
    session.add(otp)
    session.commit()
    return {
        "message": "OTP generated",
        "otp_expires_in_minutes": settings.otp_exp_minutes,
        "dev_code": code if settings.environment != "production" else None,
    }


@router.post("/verify-otp", response_model=AuthResponse)
def verify_otp(payload: OTPVerifyRequest, session: Session = Depends(get_session)) -> AuthResponse:
    otp = session.exec(
        select(OTPCode)
        .where(
            OTPCode.phone_number == payload.phone_number,
            OTPCode.code == payload.code,
            OTPCode.consumed.is_(False),
        )
        .order_by(OTPCode.created_at.desc())
    ).first()
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    if _with_timezone(otp.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    otp.consumed = True

    user = session.exec(select(User).where(User.phone_number == payload.phone_number)).first()
    if not user:
        user = User(
            phone_number=payload.phone_number,
            name=payload.name,
            photo_url=payload.photo_url,
            active_role=Role.DOG_PARENT,
        )
        session.add(user)
        session.flush()

    if payload.name:
        user.name = payload.name
    if payload.photo_url:
        user.photo_url = payload.photo_url

    ensure_role(session, user.id, Role.DOG_PARENT)
    if payload.requested_roles:
        for role in payload.requested_roles:
            ensure_role(session, user.id, role)
    roles = list_user_roles(session, user.id)
    if user.active_role not in roles:
        user.active_role = roles[0]

    refresh_token = create_refresh_token(user.id)
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_exp_days),
    )
    session.add(refresh_record)
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)

    return AuthResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
        user=_user_out(session, user),
    )


@router.post("/refresh", response_model=AuthResponse)
def refresh_tokens(payload: RefreshRequest, session: Session = Depends(get_session)) -> AuthResponse:
    user_id = token_subject(payload.refresh_token, "refresh")
    hashed = hash_token(payload.refresh_token)
    record = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == hashed,
        )
    ).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if record.revoked_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
    if _with_timezone(record.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")

    record.revoked_at = utcnow()
    new_refresh = create_refresh_token(user.id)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_exp_days),
        )
    )
    session.add(record)
    session.commit()
    return AuthResponse(
        access_token=create_access_token(user.id),
        refresh_token=new_refresh,
        user=_user_out(session, user),
    )


@router.post("/switch-role", response_model=UserOut)
def switch_role(
    payload: SwitchRoleRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    roles = list_user_roles(session, current_user.id)
    if payload.role not in roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not assigned to user")
    current_user.active_role = payload.role
    current_user.updated_at = utcnow()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return _user_out(session, current_user)


@router.get("/me", response_model=UserOut)
def me(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return _user_out(session, current_user)


@router.post("/logout")
def logout(payload: LogoutRequest, session: Session = Depends(get_session)) -> dict:
    try:
        user_id = token_subject(payload.refresh_token, "refresh")
    except ValueError:
        return {"message": "Logged out"}
    record = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == hash_token(payload.refresh_token),
        )
    ).first()
    if record and not record.revoked_at:
        record.revoked_at = utcnow()
        session.add(record)
        session.commit()
    return {"message": "Logged out"}
