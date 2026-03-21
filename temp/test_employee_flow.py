import asyncio
import httpx
import websockets
import json
import os

API_BASE = "http://127.0.0.1:8000/api/v1"
WS_BASE = "ws://127.0.0.1:8000/ws"

async def tail_websocket(role_id: str, stop_phase: str):
    uri = f"{WS_BASE}/employer/setup/{role_id}"
    print(f"[*] Connecting to WS: {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print("[*] WS Connected. Listening for events...")
            while True:
                data = await websocket.recv()
                event = json.loads(data)
                
                phase = event.get('phase')
                etype = event.get('type')
                step = event.get('step')
                
                if etype != "stream_chunk":
                    print(f"\n[WS Event] {phase} | {etype} | {step}")
                    print(f"   Message: {event.get('message')}")
                else:
                    chunk_text = event.get('data', {}).get('text', '')
                    print(chunk_text, end="", flush=True)

                if phase == stop_phase and etype in ("complete", "error"):
                    print("\n[*] Reached stop condition.")
                    break
    except Exception as e:
        print(f"\n[!] WS Error: {e}")

async def run_test():
    async with httpx.AsyncClient(timeout=None) as client:
        # Step 1: Create Role
        print("====== 1. CREATING ROLE ======")
        files = {
            "jd_file": ("jd.pdf", open("temp/jd.pdf", "rb"), "application/pdf"),
            "team_context_file": ("team.pdf", open("temp/team.pdf", "rb"), "application/pdf")
        }
        data = {
            "title": "Data Engineer",
            "seniority": "senior"
        }
        res = await client.post(f"{API_BASE}/employer/setup-role", data=data, files=files)
        res.raise_for_status()
        role_data = res.json()
        role_id = role_data["id"]
        print(f"[*] Role created: {role_id}")
        
        # Step 2: Listen to WS for employer flow to finish
        print("====== 2. WAITING FOR EMPLOYER FLOW ======")
        await tail_websocket(role_id, stop_phase="db")
        
        # Step 3: Onboard Employee
        print("\n====== 3. ONBOARDING EMPLOYEE ======")
        emp_files = {
            "resume_file": ("resume.pdf", open("temp/resume.pdf", "rb"), "application/pdf")
        }
        emp_data = {
            "role_id": role_id
        }
        res2 = await client.post(f"{API_BASE}/employee/onboard-path", data=emp_data, files=emp_files)
        res2.raise_for_status()
        emp_data = res2.json()
        emp_id = emp_data["id"]
        print(f"[*] Employee created: {emp_id}")
        
        # Step 4: Listen to WS for employee flow to finish
        print("====== 4. WAITING FOR EMPLOYEE FLOW ======")
        # Note: the employee also emits phase="db", type="complete"
        await tail_websocket(role_id, stop_phase="db")
        
        print("\n[*] ALL TESTS FINISHED.")

if __name__ == "__main__":
    asyncio.run(run_test())
