from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import Dispute, Ride, Role
from app.schemas import DisputeCreateRequest
from app.services import list_user_roles

router = APIRouter(prefix="/disputes", tags=["disputes"])


def _can_access_dispute(session: Session, dispute: Dispute, user_id: str) -> bool:
    roles = set(list_user_roles(session, user_id))
    return (
        Role.ADMIN in roles
        or dispute.opened_by_user_id == user_id
        or dispute.against_user_id == user_id
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_dispute(
    payload: DisputeCreateRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Dispute:
    ride = session.get(Ride, payload.ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if current_user.id not in {ride.dog_parent_user_id, ride.driver_user_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only ride participants can create disputes")
    dispute = Dispute(
        ride_id=ride.id,
        opened_by_user_id=current_user.id,
        against_user_id=payload.against_user_id,
        reason=payload.reason,
        details=payload.details,
    )
    session.add(dispute)
    session.commit()
    session.refresh(dispute)
    return dispute


@router.get("/me")
def my_disputes(
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[Dispute]:
    return session.exec(
        select(Dispute).where(
            (Dispute.opened_by_user_id == current_user.id) | (Dispute.against_user_id == current_user.id)
        )
    ).all()


@router.get("/{dispute_id}")
def get_dispute(
    dispute_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Dispute:
    dispute = session.get(Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    if not _can_access_dispute(session, dispute, current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dispute access denied")
    return dispute
