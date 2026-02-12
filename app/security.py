from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
import random

from jose import JWTError, jwt

from app.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str) -> str:
    expire = utcnow() + timedelta(minutes=settings.access_token_exp_minutes)
    payload = {"sub": subject, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    expire = utcnow() + timedelta(days=settings.refresh_token_exp_days)
    nonce = token_urlsafe(12)
    payload = {"sub": subject, "type": "refresh", "nonce": nonce, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def token_subject(token: str, expected_type: str) -> str:
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
    token_type = payload.get("type")
    if token_type != expected_type:
        raise ValueError("Invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise ValueError("Missing token subject")
    return sub


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def generate_otp_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def generate_receiver_pin() -> str:
    return f"{random.randint(0, 999999):06d}"
