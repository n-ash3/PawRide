import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.database import engine
from app.models import DriverLocationUpdate, Ride, Role, User
from app.realtime import realtime_manager
from app.security import decode_token
from app.services import assert_ride_access, list_user_roles

router = APIRouter(tags=["realtime"])


def _websocket_user(token: str) -> User | None:
    try:
        payload = decode_token(token)
    except Exception:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    with Session(engine) as session:
        return session.get(User, user_id)


@router.websocket("/ws/rides/{ride_id}")
async def ride_channel(websocket: WebSocket, ride_id: str, token: str = Query(default="")) -> None:
    user = _websocket_user(token)
    if not user:
        await websocket.close(code=4401)
        return

    with Session(engine) as session:
        ride = session.get(Ride, ride_id)
        if not ride:
            await websocket.close(code=4404)
            return
        try:
            assert_ride_access(session, ride, user)
        except Exception:
            await websocket.close(code=4403)
            return

    await realtime_manager.connect_ride(ride_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"event": "pong"})
            else:
                await websocket.send_json({"event": "ack", "message": message})
    except WebSocketDisconnect:
        realtime_manager.disconnect_ride(ride_id, websocket)


@router.websocket("/ws/drivers/{driver_user_id}/location")
async def driver_location_channel(
    websocket: WebSocket,
    driver_user_id: str,
    token: str = Query(default=""),
) -> None:
    user = _websocket_user(token)
    if not user:
        await websocket.close(code=4401)
        return
    with Session(engine) as session:
        roles = set(list_user_roles(session, user.id))
        if user.id != driver_user_id and Role.ADMIN not in roles:
            await websocket.close(code=4403)
            return
    await realtime_manager.connect_driver(driver_user_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "message": "Invalid JSON payload"})
                continue
            latitude = payload.get("latitude")
            longitude = payload.get("longitude")
            heading = payload.get("heading")
            speed_kph = payload.get("speed_kph")
            ride_id = payload.get("ride_id")
            if latitude is None or longitude is None:
                await websocket.send_json({"event": "error", "message": "latitude and longitude are required"})
                continue
            with Session(engine) as session:
                location = DriverLocationUpdate(
                    driver_user_id=driver_user_id,
                    ride_id=ride_id,
                    latitude=latitude,
                    longitude=longitude,
                    heading=heading,
                    speed_kph=speed_kph,
                )
                session.add(location)
                session.commit()
            event = {
                "event": "driver_location_updated",
                "driver_user_id": driver_user_id,
                "ride_id": ride_id,
                "latitude": latitude,
                "longitude": longitude,
                "heading": heading,
                "speed_kph": speed_kph,
            }
            await realtime_manager.broadcast_driver(driver_user_id, event)
            if ride_id:
                await realtime_manager.broadcast_ride(ride_id, event)
    except WebSocketDisconnect:
        realtime_manager.disconnect_driver(driver_user_id, websocket)
