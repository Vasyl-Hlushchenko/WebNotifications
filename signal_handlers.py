import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI

from config import MAX_WAIT_SECONDS, SHUTDOWN_INTERVAL_SECONDS, PERIODIC_NOTIFICATIONS_SECONDS
from connection_manager import manager
from redis_db.redis_pubsub import RedisPubSub

logging.basicConfig(level=logging.INFO)

shutdown_event = asyncio.Event()

redis_pubsub = RedisPubSub(manager, shutdown_event)


async def graceful_shutdown() -> None:
    wait_time: int = 0
    while wait_time < MAX_WAIT_SECONDS:
        connection_count: int = await redis_pubsub.get_connection_count()
        if connection_count == 0:
            logging.info("All WebSocket clients disconnected. Shutting down.")
            return
        remaining: int = MAX_WAIT_SECONDS - wait_time
        logging.info(f"Waiting for {connection_count} connection(s). Time left: {remaining // 60} min {remaining % 60} sec")
        await asyncio.sleep(SHUTDOWN_INTERVAL_SECONDS)
        wait_time += SHUTDOWN_INTERVAL_SECONDS

    connections: int = await redis_pubsub.get_connection_count()
    logging.warning(f"Timeout reached. Forcing shutdown with {connections} active connection(s).")
    await redis_pubsub.clear_all_connections()
    

async def shutdown_watcher() -> None:
    await shutdown_event.wait()
    logging.info("Shutdown signal received. Starting graceful shutdown...")
    await graceful_shutdown()
    logging.info("Graceful shutdown completed.")
    await redis_pubsub.close()
    os._exit(0)
    
    
async def publish_shutdown() -> None:
    locked: bool = await redis_pubsub.redis.setnx("shutdown_lock", "1")
    if locked:
        await redis_pubsub.redis.expire("shutdown_lock", MAX_WAIT_SECONDS)
        logging.info("Publishing shutdown signal via Redis...")
        await redis_pubsub.publish("shutdown", "start")
        shutdown_event.set()
    else:
        logging.info("Shutdown signal already published by another worker.")
        

def windows_signal_handler(signum: int, frame: object) -> None:
    logging.info(f"Signal received: {signum}, publishing shutdown immediately.")
    asyncio.get_event_loop().create_task(publish_shutdown())


@asynccontextmanager
async def lifespan(app: FastAPI):
    signal.signal(signal.SIGINT, windows_signal_handler)
    signal.signal(signal.SIGTERM, windows_signal_handler)
    logging.info("Windows signal handlers installed.")

    await redis_pubsub.connect()

    asyncio.create_task(redis_pubsub.listen())
    asyncio.create_task(send_periodic_notifications())
    asyncio.create_task(redis_pubsub.listen_for_shutdown())
    asyncio.create_task(shutdown_watcher())

    yield

    await redis_pubsub.close()
    logging.info("Uvicorn shutdown event triggered.")

     
async def send_periodic_notifications() -> None:
    while True:
        await asyncio.sleep(PERIODIC_NOTIFICATIONS_SECONDS)
        await manager.broadcast(f"Periodic notification: every {PERIODIC_NOTIFICATIONS_SECONDS} seconds")
