import asyncio
import httpx
import websockets
import json

API_BASE = "http://127.0.0.1:8000/api/v1"
WS_BASE = "ws://127.0.0.1:8000/ws"
# Using the previously fully-processed role from your DB
ROLE_ID = "role_25f8f4a6"

async def tail_websocket():
    uri = f"{WS_BASE}/employer/setup/{ROLE_ID}"
    print(f"\n[*] Connecting to WS: {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print("[*] WS Connected. Listening for employee events...")
            while True:
                data = await websocket.recv()
                event = json.loads(data)
                
                phase = event.get('phase')
                etype = event.get('type')
                step = event.get('step')
                
                if etype != "stream_chunk":
                    print(f"\n\n[WS Event] {phase} | {etype} | {step}")
                    print(f"   Message: {event.get('message')}")
                    if data := event.get('data'):
                        if 'skills' in data:
                            print(f"   Parsed Skills: {json.dumps(data['skills'], indent=2)}")
                        if 'coined_name' in data:
                            print(f"   Coined: {data['coined_name']}")
                        if 'matched_name' in data:
                            print(f"   Matched: {data['matched_name']} ({data.get('source')})")
                else:
                    chunk_text = event.get('data', {}).get('text', '')
                    print(chunk_text, end="", flush=True)

                if phase == "db" and etype in ("complete", "error"):
                    print("\n[*] Reached stop condition.")
                    break
    except Exception as e:
        print(f"\n[!] WS Error: {e}")

async def run_test():
    async with httpx.AsyncClient(timeout=None) as client:
        print("\n====== 1. ONBOARDING EMPLOYEE (RESUME ONLY) ======")
        emp_files = {
            "resume_file": ("resume.pdf", open("temp/resume.pdf", "rb"), "application/pdf")
        }
        emp_data = {
            "role_id": ROLE_ID
        }
        res2 = await client.post(f"{API_BASE}/employee/onboard-path", data=emp_data, files=emp_files)
        res2.raise_for_status()
        emp_data = res2.json()
        print(f"[*] Employee created: {emp_data['id']}")
        
        print("\n====== 2. AWAITING EMPLOYEE STREAM ======")
        await tail_websocket()

if __name__ == "__main__":
    asyncio.run(run_test())
