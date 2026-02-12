from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class RealtimeManager:
    def __init__(self) -> None:
        self._ride_channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._driver_channels: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect_ride(self, ride_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._ride_channels[ride_id].add(websocket)

    def disconnect_ride(self, ride_id: str, websocket: WebSocket) -> None:
        self._ride_channels[ride_id].discard(websocket)
        if not self._ride_channels[ride_id]:
            self._ride_channels.pop(ride_id, None)

    async def connect_driver(self, driver_user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._driver_channels[driver_user_id].add(websocket)

    def disconnect_driver(self, driver_user_id: str, websocket: WebSocket) -> None:
        self._driver_channels[driver_user_id].discard(websocket)
        if not self._driver_channels[driver_user_id]:
            self._driver_channels.pop(driver_user_id, None)

    async def broadcast_ride(self, ride_id: str, event: dict[str, Any]) -> None:
        dead_sockets: list[WebSocket] = []
        for socket in self._ride_channels.get(ride_id, set()):
            try:
                await socket.send_json(event)
            except Exception:
                dead_sockets.append(socket)
        for socket in dead_sockets:
            self.disconnect_ride(ride_id, socket)

    async def broadcast_driver(self, driver_user_id: str, event: dict[str, Any]) -> None:
        dead_sockets: list[WebSocket] = []
        for socket in self._driver_channels.get(driver_user_id, set()):
            try:
                await socket.send_json(event)
            except Exception:
                dead_sockets.append(socket)
        for socket in dead_sockets:
            self.disconnect_driver(driver_user_id, socket)


realtime_manager = RealtimeManager()
