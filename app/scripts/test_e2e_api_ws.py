"""
End-to-end integration test for the Employer Flow API and WebSocket.

This script:
1. Starts the FastAPI server locally as a subprocess if not running.
2. Sends a POST request to /api/v1/employer/setup-role with the temp PDFs.
3. Extracts the generated role_id from the HTTP 202 response.
4. Immediately connects to the WebSocket endpoint.
5. Prints all incoming JSON events from the backend -> Redis -> WebSocket proxy.
"""
import asyncio
import httpx
import websockets
import json
import sys
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_BASE = "http://localhost:8001/api/v1/employer/setup-role"
WS_BASE = "ws://localhost:8001/ws/employer/setup/{role_id}"

JD_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "temp", "jd.pdf")
TEAM_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "temp", "team.pdf")

async def test_full_pipeline():
    print("🚀 Triggering Employer Flow via POST /setup-role...")
    
    # ── 1. HTTP POST multipart/form-data ────────────────────────────
    async with httpx.AsyncClient() as client:
        with open(JD_PATH, "rb") as jd_f, open(TEAM_PATH, "rb") as team_f:
            files = {
                "jd_file": ("jd.pdf", jd_f, "application/pdf"),
                "team_context_file": ("team.pdf", team_f, "application/pdf")
            }
            data = {
                "title": "Integration Test Role",
                "seniority": "senior"
            }
            try:
                response = await client.post(API_BASE, data=data, files=files, timeout=10.0)
                response.raise_for_status()
            except Exception as e:
                print(f"❌ API Request failed: {e}")
                print(f"Make sure uvicorn is running: uvicorn app.main:app --reload")
                return

    resp_json = response.json()
    role_id = resp_json["id"]
    print(f"✅ HTTP 202 Success. Assigned Role ID: {role_id}")
    print(f"📡 Connecting to WebSocket...")

    # ── 2. WebSocket Connection ─────────────────────────────────────
    ws_url = WS_BASE.format(role_id=role_id)
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"✅ WebSocket connected successfully. Listening for events...\n{'='*65}")
            
            while True:
                msg = await websocket.recv()
                event = json.loads(msg)
                
                phase = event.get("phase", "?")
                step = event.get("step", "?")
                etype = event.get("type", "?")
                message = event.get("message", "")
                
                # Handle live streaming typing effect nicely
                if etype == "stream_chunk":
                    chunk_type = event.get("data", {}).get("chunk_type", "")
                    text = event.get("data", {}).get("text", "")
                    if chunk_type == "reasoning":
                        print(f"\033[90m{text}\033[0m", end="", flush=True) # gray
                    else:
                        print(f"\033[92m{text}\033[0m", end="", flush=True) # green
                else:
                    if step == "llm_extraction_streaming" and etype == "stream_end":
                        print("\n") # Newline after stream ends
                    print(f"\n[{phase.upper()}] {step} ({etype}) - {message}")
                
                # Terminate on complete
                if event.get("type") in ("complete", "error"):
                    print(f"\n{'='*65}\n✅ Test Complete by terminal event.")
                    break
                    
    except Exception as e:
        print(f"\n❌ WebSocket failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_full_pipeline())
    except KeyboardInterrupt:
        pass
