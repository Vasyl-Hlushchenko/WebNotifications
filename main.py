import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from signal_handlers import lifespan
from routes.http_routes import router as http_router
from routes.websocket_routes import router as websocket_router

logging.basicConfig(level=logging.INFO)


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


app.include_router(http_router)
app.include_router(websocket_router)
