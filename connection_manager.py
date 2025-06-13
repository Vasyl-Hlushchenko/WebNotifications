import logging
from fastapi import WebSocket

logging.basicConfig(level=logging.INFO)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        self.active_connections[client_id] = websocket
        from signal_handlers import redis_pubsub
        await redis_pubsub.add_connection(client_id)

    async def disconnect(self, client_id: str) -> None:
        from signal_handlers import redis_pubsub
        await redis_pubsub.remove_connection(client_id)
        self.active_connections.pop(client_id, None)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str, sender_id: str = None) -> None:
        disconnected_clients: list[str] = []
        for client_id, connection in self.active_connections.items():
            try:
                if sender_id and client_id == sender_id:
                    continue
                await connection.send_text(message)
            except Exception as e:
                logging.warning(f"Broadcast failed to client '{client_id}': {e}")
                disconnected_clients.append(client_id)

        for client_id in disconnected_clients:
            await self.disconnect(client_id)

manager = ConnectionManager()
