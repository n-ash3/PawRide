from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import Dog, Role, User
from app.schemas import DogCreate, DogUpdate
from app.security import utcnow
from app.services import list_user_roles

router = APIRouter(prefix="/dogs", tags=["dogs"])


def _can_access_dog(current_user: User, roles: set[Role], dog: Dog) -> bool:
    return Role.ADMIN in roles or dog.owner_user_id == current_user.id


@router.get("")
def list_dogs(
    owner_user_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Dog]:
    roles = set(list_user_roles(session, current_user.id))
    if Role.ADMIN in roles and owner_user_id:
        return session.exec(select(Dog).where(Dog.owner_user_id == owner_user_id)).all()
    return session.exec(select(Dog).where(Dog.owner_user_id == current_user.id)).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_dog(
    payload: DogCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Dog:
    dog = Dog(owner_user_id=current_user.id, **payload.model_dump())
    session.add(dog)
    session.commit()
    session.refresh(dog)
    return dog


@router.get("/{dog_id}")
def get_dog(
    dog_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Dog:
    dog = session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_dog(current_user, roles, dog):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dog access denied")
    return dog


@router.patch("/{dog_id}")
def update_dog(
    dog_id: str,
    payload: DogUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Dog:
    dog = session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_dog(current_user, roles, dog):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dog access denied")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(dog, key, value)
    dog.updated_at = utcnow()
    session.add(dog)
    session.commit()
    session.refresh(dog)
    return dog


@router.delete("/{dog_id}")
def delete_dog(
    dog_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    dog = session.get(Dog, dog_id)
    if not dog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dog not found")
    roles = set(list_user_roles(session, current_user.id))
    if not _can_access_dog(current_user, roles, dog):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dog access denied")
    session.delete(dog)
    session.commit()
    return {"message": "Dog deleted"}
