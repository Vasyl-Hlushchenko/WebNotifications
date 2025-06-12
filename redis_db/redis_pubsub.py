import logging
import json
from redis.asyncio import Redis

from config import REDIS_URL, REDIS_CONNECTIONS_KEY, REDIS_CHANNEL


class RedisPubSub:
    def __init__(self, manager, shutdown_event, redis_url=REDIS_URL, channel=REDIS_CHANNEL):
        self.manager = manager
        self.redis_url = redis_url
        self.channel = channel
        self.redis = None
        self.pub = None
        self.sub = None
        self.listen_task = None
        self.shutdown_event = shutdown_event

    async def connect(self):
        self.redis = Redis.from_url(self.redis_url)
        self.pub = self.redis
        self.sub = self.redis.pubsub()
        await self.sub.subscribe(self.channel)
        logging.info(f"Connected to Redis channel '{self.channel}'")

    async def publish(self, channel: str, message: str):
        await self.redis.publish(channel, message.encode())

    async def close(self):
        if self.sub:
            await self.sub.unsubscribe(self.channel)
            await self.sub.close()
        if self.redis:
            await self.redis.close()
        logging.info("Redis connection closed.")
        
    async def add_connection(self, client_id: str):
        await self.redis.sadd(REDIS_CONNECTIONS_KEY, client_id)

    async def remove_connection(self, client_id: str):
        await self.redis.srem(REDIS_CONNECTIONS_KEY, client_id)
        
    async def clear_all_connections(self):
        await self.redis.delete(REDIS_CONNECTIONS_KEY)
        logging.info(f"Cleared all WebSocket connection IDs from Redis set '{REDIS_CONNECTIONS_KEY}'")

    async def get_connection_count(self) -> int:
        return await self.redis.scard(REDIS_CONNECTIONS_KEY)
    
    async def publish_shutdown_signal(self):
        await self.redis.publish("shutdown", "start")

    async def listen_for_shutdown(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("shutdown")

        async for message in pubsub.listen():
            if message["type"] == "message" and message["data"] == b"start":
                logging.info("Received shutdown signal via Redis.")
                self.shutdown_event.set()
                break
            
    async def listen(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.channel)
        logging.info(f"[broadcast] Subscribed to Redis channel '{self.channel}'")

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=False)
            if message and message["type"] == "subscribe":
                break

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode()

            try:
                parsed = json.loads(data)
                message_text = parsed.get("message", "")
                sender_id = parsed.get("sender_id")
            except json.JSONDecodeError:
                logging.warning("[broadcast] Non-JSON message received.")
                message_text = data
                sender_id = None

            await self.manager.broadcast(message_text, sender_id)
