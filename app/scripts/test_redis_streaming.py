"""
Debug: Test real-time LLM streaming to Redis.
We want to publish partial chunks as they arrive from the Nvidia API,
so the frontend can render the reasoning/content in real-time.
"""
import asyncio
import sys
import os
import json
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import redis.asyncio as aioredis
from app.config import settings

TEST_ROLE_ID = "stream-test-001"

async def mock_subscriber():
    """Listens to the Redis channel and prints stream chunks as they arrive."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"channel:{TEST_ROLE_ID}")
    print(f"\n📡 Subscribed to channel:{TEST_ROLE_ID}")
    
    received_chunks = 0
    start_time = None
    
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        event = json.loads(message["data"])
        
        if event["type"] == "stream_chunk":
            if start_time is None:
                start_time = time.time()
                print("⏳ First chunk received. Streaming...\n")
            
            chunk_type = event["data"].get("chunk_type") # 'reasoning' or 'content'
            text = event["data"].get("text", "")
            
            # Print without newline to see the stream effect
            if chunk_type == "reasoning":
                print(f"\033[90m{text}\033[0m", end="", flush=True) # gray for reasoning
            else:
                print(f"\033[92m{text}\033[0m", end="", flush=True) # green for content
                
            received_chunks += 1
            
        elif event["type"] == "stream_end":
            dt = time.time() - start_time if start_time else 0
            print(f"\n\n🛑 Stream ended. {received_chunks} chunks in {dt:.2f}s")
            await pubsub.unsubscribe()
            break


async def stream_test():
    """Calls the Nvidia API and publishes chunks to Redis."""
    from openai import AsyncOpenAI
    from app.clients.redis_client import redis_client

    await asyncio.sleep(0.5) # Let subscriber connect
    
    client = AsyncOpenAI(
        api_key=settings.NVIDIA_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1",
    )
    
    prompt = "Explain quantum computing in exactly 3 short sentences. Show your reasoning first."
    print(f"\n🚀 Starting streaming API call...")
    
    completion = await client.chat.completions.create(
        model="stepfun-ai/step-3.5-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1000,
        stream=True,
    )
    
    # We will publish to Redis for every chunk
    async for chunk in completion:
        if not getattr(chunk, "choices", None):
            continue
            
        delta = chunk.choices[0].delta
        
        # Is it reasoning or content?
        reasoning = getattr(delta, "reasoning_content", None)
        content = getattr(delta, "content", None)
        
        if reasoning:
            await redis_client.publish_event(
                role_id=TEST_ROLE_ID,
                phase="test",
                event_type="stream_chunk",
                step="llm_streaming",
                message="",
                data={"chunk_type": "reasoning", "text": reasoning}
            )
            
        if content:
            await redis_client.publish_event(
                role_id=TEST_ROLE_ID,
                phase="test",
                event_type="stream_chunk",
                step="llm_streaming",
                message="",
                data={"chunk_type": "content", "text": content}
            )
            
    # Send a finish event
    await redis_client.publish_event(
        role_id=TEST_ROLE_ID,
        phase="test",
        event_type="stream_end",
        step="llm_streaming",
        message="Stream complete"
    )

async def main():
    await asyncio.gather(
        mock_subscriber(),
        stream_test()
    )

if __name__ == "__main__":
    asyncio.run(main())
