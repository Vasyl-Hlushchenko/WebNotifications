from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST

from config import HTML_PATH
from signal_handlers import redis_pubsub

router = APIRouter()


@router.get("/", response_class=FileResponse)
async def get() -> FileResponse:
    return FileResponse(HTML_PATH, media_type="text/html")


@router.get("/connections")
async def get_active_connections() -> dict[str, int]:
    count = await redis_pubsub.get_connection_count()
    return {"active_connections": count}


@router.post("/broadcast", response_model=None)
async def broadcast_message(request: Request) -> JSONResponse:
    data = await request.json()
    message = data.get("message")
    if not message:
        return JSONResponse(
            content={"error": "No message provided"},
            status_code=HTTP_400_BAD_REQUEST
        )
    await redis_pubsub.publish(redis_pubsub.channel, message)
    return {"status": "Message broadcasted"}
