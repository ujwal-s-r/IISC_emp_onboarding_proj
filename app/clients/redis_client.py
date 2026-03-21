"""
Redis Client
============
Manages connections to the Redis event bus for Pub/Sub orchestration events.
"""
from typing import Any, Dict
import json
import redis.asyncio as redis
from app.config import settings
from app.utils.logger import logger

class RedisClient:
    def __init__(self):
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info(f"RedisClient initialized targeting {settings.REDIS_URL}")

    async def publish_event(
        self,
        role_id: str,
        phase: str,
        event_type: str,
        step: str,
        message: str,
        model: str = None,
        data: Dict[str, Any] = None
    ):
        """Standardized JSON event publisher."""
        payload = {
            "role_id":   role_id,
            "phase":     phase,
            "type":      event_type,
            "step":      step,
            "message":   message,
            "model":     model,
            "data":      data or {}
        }
        await self.client.publish(f"channel:{role_id}", json.dumps(payload))
        logger.debug(f"[Redis] Published to channel:{role_id} — {phase}/{step}")


# Singleton
redis_client = RedisClient()
