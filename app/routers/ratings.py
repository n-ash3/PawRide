from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user
from app.models import DriverProfile, Rating, Ride, RideStatus, Role
from app.schemas import RatingCreateRequest
from app.services import list_user_roles

router = APIRouter(prefix="/ratings", tags=["ratings"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rating(
    payload: RatingCreateRequest,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> Rating:
    ride = session.get(Ride, payload.ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.status != RideStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride must be completed before rating")
    participants = {ride.dog_parent_user_id}
    if ride.driver_user_id:
        participants.add(ride.driver_user_id)
    roles = set(list_user_roles(session, current_user.id))
    if current_user.id not in participants and Role.ADMIN not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to rate this ride")
    if payload.to_user_id not in participants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating target is not a ride participant")
    if payload.to_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot rate yourself")

    existing = session.exec(
        select(Rating).where(
            Rating.ride_id == payload.ride_id,
            Rating.from_user_id == current_user.id,
            Rating.to_user_id == payload.to_user_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already rated this user for this ride")

    rating = Rating(
        ride_id=payload.ride_id,
        from_user_id=current_user.id,
        to_user_id=payload.to_user_id,
        score=payload.score,
        dog_comfort_score=payload.dog_comfort_score,
        comment=payload.comment,
        tags_csv=",".join(payload.tags) if payload.tags else None,
    )
    session.add(rating)
    session.commit()
    session.refresh(rating)

    driver_profile = session.exec(select(DriverProfile).where(DriverProfile.user_id == payload.to_user_id)).first()
    if driver_profile:
        ratings = session.exec(select(Rating).where(Rating.to_user_id == payload.to_user_id)).all()
        driver_profile.rating = round(sum(item.score for item in ratings) / max(1, len(ratings)), 2)
        session.add(driver_profile)
        session.commit()

    return rating


@router.get("/ride/{ride_id}")
def ride_ratings(
    ride_id: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[Rating]:
    ride = session.get(Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    roles = set(list_user_roles(session, current_user.id))
    if (
        ride.dog_parent_user_id != current_user.id
        and ride.driver_user_id != current_user.id
        and Role.ADMIN not in roles
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return session.exec(select(Rating).where(Rating.ride_id == ride_id)).all()


@router.get("/me/received")
def my_received_ratings(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
) -> list[Rating]:
    return session.exec(
        select(Rating).where(Rating.to_user_id == current_user.id).order_by(Rating.created_at.desc()).limit(limit)
    ).all()
