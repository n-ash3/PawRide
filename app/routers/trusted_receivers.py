from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import Role, TrustedReceiver, User
from app.schemas import TrustedReceiverCreate, TrustedReceiverUpdate
from app.security import generate_receiver_pin, utcnow
from app.services import list_user_roles

router = APIRouter(prefix="/trusted-receivers", tags=["trusted_receivers"])


def _can_access_receiver(current_user: User, roles: set[Role], receiver: TrustedReceiver) -> bool:
    return Role.ADMIN in roles or receiver.owner_user_id == current_user.id


@router.get("")
def list_receivers(
    owner_user_id: str | None = Query(default=None),
    include_inactive: bool = Query(default=True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[TrustedReceiver]:
    roles = set(list_user_roles(session, current_user.id))
    owner = current_user.id
    if owner_user_id and Role.ADMIN in roles:
        owner = owner_user_id
    stmt = select(TrustedReceiver).where(TrustedReceiver.owner_user_id == owner)
    if not include_inactive:
        stmt = stmt.where(TrustedReceiver.is_active.is_(True))
    return session.exec(stmt).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_receiver(
    payload: TrustedReceiverCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TrustedReceiver:
    receiver = TrustedReceiver(
        owner_user_id=current_user.id,
        name=payload.name,
        phone_number=payload.phone_number,
        relationship=payload.relationship,
        photo_url=payload.photo_url,
        pin_code=payload.pin_code or generate_receiver_pin(),
    )
    session.add(receiver)
    session.commit()
    session.refresh(receiver)
    return receiver


@router.get("/{receiver_id}")
def get_receiver(
    receiver_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TrustedReceiver:
    receiver = session.get(TrustedReceiver, receiver_id)
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_receiver(current_user, roles, receiver):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receiver access denied")
    return receiver


@router.patch("/{receiver_id}")
def update_receiver(
    receiver_id: str,
    payload: TrustedReceiverUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TrustedReceiver:
    receiver = session.get(TrustedReceiver, receiver_id)
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_receiver(current_user, roles, receiver):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receiver access denied")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(receiver, key, value)
    receiver.updated_at = utcnow()
    session.add(receiver)
    session.commit()
    session.refresh(receiver)
    return receiver


@router.delete("/{receiver_id}")
def delete_receiver(
    receiver_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    receiver = session.get(TrustedReceiver, receiver_id)
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_receiver(current_user, roles, receiver):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receiver access denied")
    session.delete(receiver)
    session.commit()
    return {"message": "Trusted receiver deleted"}
