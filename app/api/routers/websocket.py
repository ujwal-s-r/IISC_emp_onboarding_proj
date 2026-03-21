from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import redis.asyncio as aioredis
from app.config import settings
from app.utils.logger import logger

router = APIRouter(prefix="/ws", tags=["WebSockets"])

@router.websocket("/employer/setup/{role_id}")
async def employer_setup_websocket(websocket: WebSocket, role_id: str):
    """
    Subscribes to the Redis channel for the given role_id and streams
    all orchestration events down to the connected frontend client.
    """
    await websocket.accept()
    logger.info(f"Frontend WebSocket connected for role_id: {role_id}")

    redis_conn = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_conn.pubsub()
    channel_name = f"channel:{role_id}"

    try:
        await pubsub.subscribe(channel_name)
        logger.debug(f"Subscribed to Redis {channel_name}")

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            # Proxy the JSON event directly to the frontend
            event_data_str = message["data"]
            await websocket.send_text(event_data_str)

            # Check if this is the final event or an error
            event_dict = json.loads(event_data_str)
            if event_dict.get("type") in ("complete", "error"):
                logger.info(f"Received terminal event '{event_dict.get('type')}' for {role_id}. Closing WS.")
                break

    except WebSocketDisconnect:
        logger.info(f"Frontend WebSocket disconnected for {role_id}")
    except Exception as e:
        logger.error(f"WebSocket Error for {role_id}: {e}")
    finally:
        await pubsub.unsubscribe(channel_name)
        await redis_conn.aclose()
        # Ensure we close our end of the socket if we broke out of the loop normally
        try:
            await websocket.close()
        except:
            pass
