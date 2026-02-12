from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import Role, SavedDestination, User
from app.schemas import SavedDestinationCreate, SavedDestinationUpdate
from app.security import utcnow
from app.services import list_user_roles

router = APIRouter(prefix="/saved-destinations", tags=["saved_destinations"])


def _can_access_destination(current_user: User, roles: set[Role], destination: SavedDestination) -> bool:
    return Role.ADMIN in roles or destination.owner_user_id == current_user.id


@router.get("")
def list_destinations(
    owner_user_id: str | None = Query(default=None),
    favorites_only: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[SavedDestination]:
    roles = set(list_user_roles(session, current_user.id))
    owner = current_user.id
    if owner_user_id and Role.ADMIN in roles:
        owner = owner_user_id
    stmt = select(SavedDestination).where(SavedDestination.owner_user_id == owner)
    if favorites_only:
        stmt = stmt.where(SavedDestination.is_favorite.is_(True))
    return session.exec(stmt).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_destination(
    payload: SavedDestinationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SavedDestination:
    destination = SavedDestination(owner_user_id=current_user.id, **payload.model_dump())
    session.add(destination)
    session.commit()
    session.refresh(destination)
    return destination


@router.get("/{destination_id}")
def get_destination(
    destination_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SavedDestination:
    destination = session.get(SavedDestination, destination_id)
    if not destination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_destination(current_user, roles, destination):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Destination access denied")
    return destination


@router.patch("/{destination_id}")
def update_destination(
    destination_id: str,
    payload: SavedDestinationUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SavedDestination:
    destination = session.get(SavedDestination, destination_id)
    if not destination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_destination(current_user, roles, destination):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Destination access denied")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(destination, key, value)
    destination.updated_at = utcnow()
    session.add(destination)
    session.commit()
    session.refresh(destination)
    return destination


@router.delete("/{destination_id}")
def delete_destination(
    destination_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    destination = session.get(SavedDestination, destination_id)
    if not destination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_destination(current_user, roles, destination):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Destination access denied")
    session.delete(destination)
    session.commit()
    return {"message": "Saved destination deleted"}
