import uuid
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from connection_manager import manager
from signal_handlers import redis_pubsub

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    client_id: str = str(uuid.uuid4())
    await manager.connect(websocket, client_id)
    await manager.send_personal_message("🟢 Connected to server", websocket)
    try:
        while True:
            data: str = await websocket.receive_text()
            await redis_pubsub.publish(
                redis_pubsub.channel,
                json.dumps({
                    "sender_id": client_id,
                    "message": f"New message: {data}",
                })
            )
            await manager.send_personal_message(f"You said: {data}", websocket)
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
