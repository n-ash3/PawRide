from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlmodel import Session, select

from app.database import get_session
from app.models import Role, User, UserRole
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/verify-otp")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise credentials_error from exc

    if payload.get("type") != "access":
        raise credentials_error

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_error
    return user


def get_user_roles(session: Session, user_id: str) -> list[Role]:
    rows = session.exec(select(UserRole).where(UserRole.user_id == user_id)).all()
    return [row.role for row in rows]


def require_role(*required_roles: Role) -> Callable:
    def checker(
        current_user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> User:
        roles = set(get_user_roles(session, current_user.id))
        if not roles.intersection(required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(r.value for r in required_roles)}",
            )
        return current_user

    return checker
