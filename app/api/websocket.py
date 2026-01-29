import json
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState


router = APIRouter()


class WebSocketManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        """Initialize the WebSocket manager."""
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection.

        Args:
            websocket: WebSocket connection to remove
        """
        self.active_connections.discard(websocket)
        print(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Send a message to a specific WebSocket connection.

        Args:
            message: Dictionary to send as JSON
            websocket: Target WebSocket connection
        """
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """
        Broadcast a message to all connected WebSocket clients.

        Args:
            message: Dictionary to send as JSON to all clients
        """
        if not self.active_connections:
            return

        # Create a copy of connections to iterate safely
        connections = list(self.active_connections)
        disconnected = []

        for connection in connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_json(message)
                else:
                    disconnected.append(connection)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    def get_connection_count(self) -> int:
        """
        Get the number of active WebSocket connections.

        Returns:
            Number of active connections
        """
        return len(self.active_connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time DNS test results.

    Clients connect here to receive:
    - Real-time test results
    - Status updates
    - Configuration information
    """
    await ws_manager.connect(websocket)

    try:
        # Send welcome message with connection info
        await ws_manager.send_personal_message(
            {
                "type": "connection",
                "message": "Connected to DNS Test System",
                "active_connections": ws_manager.get_connection_count()
            },
            websocket
        )

        # Send initial configuration
        from ..main import get_config, get_test_engine

        config = get_config()
        if config:
            await ws_manager.send_personal_message(
                {
                    "type": "config",
                    "config": {
                        "domains": config.domains,
                        "dns_servers": [server.model_dump() for server in config.dns_servers],
                        "interval_seconds": config.testing.interval_seconds,
                        "timeout_seconds": config.testing.timeout_seconds
                    }
                },
                websocket
            )

        # Send recent results if available
        engine = get_test_engine()
        if engine:
            recent_results = engine.get_latest_results(limit=10)
            if recent_results:
                await ws_manager.send_personal_message(
                    {
                        "type": "history",
                        "results": recent_results
                    },
                    websocket
                )

        # Keep connection alive and listen for messages
        while True:
            # Receive messages from client (for future features like pause/resume)
            data = await websocket.receive_text()

            # Echo back for now (can be extended for commands)
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await ws_manager.send_personal_message(
                        {"type": "pong", "timestamp": message.get("timestamp")},
                        websocket
                    )
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
