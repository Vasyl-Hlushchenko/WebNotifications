import logging
import json
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from asyncio import Event

from config import REDIS_URL, REDIS_CONNECTIONS_KEY, REDIS_CHANNEL, MESSAGE_TYPE
from connection_manager import ConnectionManager


class RedisPubSub:
    def __init__(
        self,
        manager: ConnectionManager,
        shutdown_event: Event,
        redis_url: str = REDIS_URL,
        channel: str = REDIS_CHANNEL
    ):
        self.manager = manager
        self.redis_url = redis_url
        self.channel = channel
        self.redis: Redis | None = None
        self.pub: Redis | None = None
        self.sub: PubSub | None = None
        self.shutdown_event = shutdown_event

    async def connect(self) -> None:
        self.redis = Redis.from_url(self.redis_url)
        self.pub = self.redis
        self.sub = self.redis.pubsub()
        await self.sub.subscribe(self.channel)
        logging.info(f"Connected to Redis channel '{self.channel}'")

    async def publish(self, channel: str, message: str) -> None:
        await self.redis.publish(channel, message.encode())

    async def close(self) -> None:
        if self.sub:
            await self.sub.unsubscribe(self.channel)
            await self.sub.close()
        if self.redis:
            await self.redis.close()
        logging.info("Redis connection closed.")
        
    async def add_connection(self, client_id: str) -> None:
        await self.redis.sadd(REDIS_CONNECTIONS_KEY, client_id)

    async def remove_connection(self, client_id: str) -> None:
        await self.redis.srem(REDIS_CONNECTIONS_KEY, client_id)
        
    async def clear_all_connections(self) -> None:
        await self.redis.delete(REDIS_CONNECTIONS_KEY)
        logging.info(f"Cleared all WebSocket connection IDs from Redis set '{REDIS_CONNECTIONS_KEY}'")

    async def get_connection_count(self) -> int:
        return await self.redis.scard(REDIS_CONNECTIONS_KEY)

    async def listen_for_shutdown(self) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("shutdown")

        async for message in pubsub.listen():
            if message["type"] == MESSAGE_TYPE and message["data"] == b"start":
                logging.info("Received shutdown signal via Redis.")
                self.shutdown_event.set()
                break
            
    async def listen(self) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.channel)
        logging.info(f"[broadcast] Subscribed to Redis channel '{self.channel}'")

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=False)
            if message and message["type"] == "subscribe":
                break

        async for message in pubsub.listen():
            if message["type"] != MESSAGE_TYPE:
                continue

            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode()

            try:
                parsed = json.loads(data)
                message_text = parsed.get(MESSAGE_TYPE, "")
                sender_id = parsed.get("sender_id")
            except json.JSONDecodeError:
                logging.warning("[broadcast] Non-JSON message received.")
                message_text = data
                sender_id = None

            await self.manager.broadcast(message_text, sender_id)
