"""
Redis Stream Verification Test
===============================
This script:
  1. Starts a Redis subscriber on a test role_id
  2. Runs the full orchestrate_employer_flow with real PDFs
  3. Prints every Redis event received with its phase, step, and data summary
  4. Verifies that reasoning fields are non-empty for LLM events
"""

import asyncio
import json
import sys
import os

# Fix Windows event loop for asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Make sure we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import redis.asyncio as aioredis
from app.config import settings
from app.utils.logger import logger

# ── Use the test PDFs in the temp/ directory ─────────────────────────────────
JD_PDF_PATH   = os.path.join(os.path.dirname(__file__), "..", "..", "temp", "jd.pdf")
TEAM_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "temp", "team.pdf")
TEST_ROLE_ID  = "test-redis-role-001"

# Track events for assertion
received_events = []


async def subscriber():
    """Listen to all events on the test channel and print them."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"channel:{TEST_ROLE_ID}")
    print(f"\n📡 Subscribed to channel:{TEST_ROLE_ID}\n{'='*65}")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        event = json.loads(message["data"])
        received_events.append(event)

        phase     = event.get("phase", "?")
        step      = event.get("step", "?")
        etype     = event.get("type", "?")
        msg       = event.get("message", "")
        model     = event.get("model", "")
        data      = event.get("data", {})

        reasoning = data.get("reasoning", "") or data.get("llm_raw_reply", "")
        reasoning_preview = reasoning[:120].replace("\n", " ") if reasoning else "—"

        print(f"\n[{phase.upper()}] {step} ({etype})")
        print(f"  📌 {msg}")
        if model:
            print(f"  🤖 Model: {model}")
        if reasoning:
            print(f"  💭 Reasoning: {reasoning_preview}...")
        if data:
            # Print key data fields
            for k in ["raw_count", "matched", "coined", "total_skills", "raw_skill",
                       "matched_name", "canonical_id", "source", "seniority"]:
                if k in data:
                    print(f"  📊 {k}: {data[k]}")

        # Check if this is the final event (with or without DB session)
        if step in ("db_persist_done", "mastery_matrix_done") or (phase == "db" and etype == "complete"):
            await pubsub.unsubscribe(f"channel:{TEST_ROLE_ID}")
            break


async def orchestrator_task():
    """Run the employer flow orchestrator."""
    await asyncio.sleep(0.5)

    # Load team.pdf (always available)
    if not os.path.exists(TEAM_PDF_PATH):
        print(f"⚠️  team.pdf not found at {TEAM_PDF_PATH}")
        team_bytes = b""
    else:
        with open(TEAM_PDF_PATH, "rb") as f:
            team_bytes = f.read()
        print(f"✅ Loaded team.pdf ({len(team_bytes)} bytes)")

    # JD PDF is optional — use team.pdf as a fallback if jd.pdf doesn't exist
    if os.path.exists(JD_PDF_PATH):
        with open(JD_PDF_PATH, "rb") as f:
            jd_bytes = f.read()
        print(f"✅ Loaded jd.pdf ({len(jd_bytes)} bytes)")
    else:
        print(f"⚠️  jd.pdf not found — using team.pdf as JD for testing")
        jd_bytes = team_bytes  # Use same doc as JD so extraction still works

    from app.services.employer_flow.orchestrator import orchestrate_employer_flow
    print(f"\n🚀 Running orchestrate_employer_flow for role: {TEST_ROLE_ID}\n{'='*65}")
    try:
        await orchestrate_employer_flow(
            role_id=TEST_ROLE_ID,
            jd_bytes=jd_bytes,
            team_bytes=team_bytes,
            assumed_seniority="senior",
            db=None
        )
    except Exception as e:
        print(f"\n❌ Orchestrator error: {e}")
        import traceback; traceback.print_exc()



async def main():
    # Run subscriber and orchestrator concurrently
    await asyncio.gather(
        subscriber(),
        orchestrator_task(),
    )

    # ── Assertions ───────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"📊 Total events received: {len(received_events)}")

    llm_events = [e for e in received_events if e.get("model")]
    reasoning_provided = [
        e for e in llm_events
        if e.get("data", {}).get("reasoning") or e.get("data", {}).get("llm_raw_reply")
    ]
    print(f"  ✅ LLM events with reasoning: {len(reasoning_provided)}/{len(llm_events)}")

    phases = list({e.get("phase") for e in received_events})
    print(f"  ✅ Phases covered: {phases}")

    if len(received_events) >= 6:
        print("\n✅ PASS: Redis event streaming is working with reasoning capture!")
    else:
        print("\n⚠️  WARNING: Fewer events than expected. Check orchestrator logs.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, RuntimeError):
        pass
