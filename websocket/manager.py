# ABOUTME: WebSocket connection manager for real-time updates
# ABOUTME: Handles client connections, rooms, and broadcasting simulation events

from fastapi import WebSocket
from typing import Dict, List, Set
import json
import asyncio
from dataclasses import asdict

from simulations.base import SimulationEvent


class ConnectionManager:
    """
    Manages WebSocket connections for real-time simulation updates.

    Features:
    - Per-simulation rooms for targeted broadcasting
    - Per-tenant isolation
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        # Active connections by room (simulation_run_id)
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Tenant associations
        self.connection_tenants: Dict[WebSocket, int] = {}

    async def connect(self, websocket: WebSocket, room: str, tenant_id: int):
        """Accept connection and add to room"""
        await websocket.accept()

        if room not in self.active_connections:
            self.active_connections[room] = []

        self.active_connections[room].append(websocket)
        self.connection_tenants[websocket] = tenant_id

    def disconnect(self, websocket: WebSocket, room: str):
        """Remove connection from room"""
        if room in self.active_connections:
            if websocket in self.active_connections[room]:
                self.active_connections[room].remove(websocket)

            # Clean up empty rooms
            if not self.active_connections[room]:
                del self.active_connections[room]

        if websocket in self.connection_tenants:
            del self.connection_tenants[websocket]

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to a specific connection"""
        await websocket.send_json(message)

    async def broadcast_to_room(self, room: str, message: dict):
        """Broadcast message to all connections in a room"""
        if room not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections[room]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, room)

    async def broadcast_to_tenant(self, tenant_id: int, message: dict):
        """Broadcast message to all connections for a tenant"""
        for room, connections in self.active_connections.items():
            for connection in connections:
                if self.connection_tenants.get(connection) == tenant_id:
                    try:
                        await connection.send_json(message)
                    except Exception:
                        pass

    def get_room_count(self, room: str) -> int:
        """Get number of connections in a room"""
        return len(self.active_connections.get(room, []))

    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()


def create_websocket_callback(room: str, manager: ConnectionManager, loop: asyncio.AbstractEventLoop):
    """
    Create a callback function for simulation events that broadcasts to WebSocket.

    Usage:
        callback = create_websocket_callback(room_id, manager, asyncio.get_event_loop())
        simulation.run(params, callback=callback)
    """
    def callback(event: SimulationEvent):
        message = {
            "event_type": event.event_type.value,
            "time": event.time,
            "data": event.data
        }
        # Schedule the coroutine on the event loop
        asyncio.run_coroutine_threadsafe(
            manager.broadcast_to_room(room, message),
            loop
        )

    return callback
