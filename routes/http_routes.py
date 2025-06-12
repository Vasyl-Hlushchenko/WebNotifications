from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from connection_manager import manager
from config import HTML_PATH
from signal_handlers import redis_pubsub

router = APIRouter()


@router.get("/")
async def get():
    return FileResponse(HTML_PATH, media_type="text/html")


@router.get("/connections")
async def get_active_connections():
    count = await redis_pubsub.get_connection_count()
    return {"active_connections": count}


@router.post("/broadcast")
async def broadcast_message(request: Request):
    data = await request.json()
    message = data.get("message")
    if not message:
        return {"error": "No message provided"}
    await redis_pubsub.publish(message)
    return {"status": "Message broadcasted"}
