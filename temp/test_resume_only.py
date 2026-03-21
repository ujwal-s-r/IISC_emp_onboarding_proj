"""
End-to-end test: Employer setup → Employee resume onboarding.

Steps:
  1. POST /employer/setup-role  (jd.pdf + team.pdf) → get role_id
  2. Stream employer WS until db/complete
  3. POST /employee/onboard-path (role_id + resume.pdf) → get employee_id
  4. Stream employee WS (channel:{role_id}) until db/complete
"""
import asyncio
import sys
import httpx
import websockets
import json

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_BASE = "http://127.0.0.1:8000/api/v1"
WS_BASE  = "ws://127.0.0.1:8000/ws"


async def stream_ws(uri: str, label: str):
    """Connect to a WS endpoint and print events until db/complete or db/error."""
    print(f"\n[*] Connecting to WS: {uri}")
    try:
        async with websockets.connect(uri) as ws:
            print(f"[*] WS Connected — {label}")
            while True:
                raw = await ws.recv()
                event = json.loads(raw)

                phase = event.get("phase", "")
                etype = event.get("type", "")
                step  = event.get("step", "")

                if etype == "stream_chunk":
                    text = event.get("data", {}).get("text", "")
                    print(text, end="", flush=True)
                else:
                    print(f"\n[{label}] {phase} | {etype} | {step}")
                    print(f"   {event.get('message', '')}")
                    d = event.get("data")
                    if d:
                        if "skills" in d:
                            print(f"   Skills: {json.dumps(d['skills'], indent=2)}")
                        if "coined_name" in d:
                            print(f"   Coined: {d['coined_name']}")
                        if "matched_name" in d:
                            print(f"   Matched: {d['matched_name']} ({d.get('source')})")

                if phase == "db" and etype in ("complete", "error"):
                    print(f"\n[*] {label} — terminal event reached.")
                    break
    except Exception as e:
        print(f"\n[!] WS Error ({label}): {e}")


async def run_test():
    async with httpx.AsyncClient(timeout=None) as client:

        # ── Step 1: Create a role via the employer flow ──────────────
        print("\n" + "=" * 60)
        print("  STEP 1 — EMPLOYER: Setup Role (jd.pdf + team.pdf)")
        print("=" * 60)
        with open("temp/jd.pdf", "rb") as jd, open("temp/team.pdf", "rb") as team:
            resp = await client.post(
                f"{API_BASE}/employer/setup-role",
                data={"title": "E2E Test Role", "seniority": "senior"},
                files={
                    "jd_file": ("jd.pdf", jd, "application/pdf"),
                    "team_context_file": ("team.pdf", team, "application/pdf"),
                },
            )
        resp.raise_for_status()
        role = resp.json()
        role_id = role["id"]
        print(f"[*] Role created: {role_id}  (HTTP {resp.status_code})")

        # ── Step 2: Wait for employer pipeline to finish ─────────────
        await stream_ws(f"{WS_BASE}/employer/setup/{role_id}", "EMPLOYER")

        # ── Step 3: Onboard employee with resume ─────────────────────
        print("\n" + "=" * 60)
        print("  STEP 3 — EMPLOYEE: Onboard with resume.pdf")
        print("=" * 60)
        with open("temp/resume.pdf", "rb") as resume:
            resp2 = await client.post(
                f"{API_BASE}/employee/onboard-path",
                data={"role_id": role_id},
                files={"resume_file": ("resume.pdf", resume, "application/pdf")},
            )
        resp2.raise_for_status()
        emp = resp2.json()
        print(f"[*] Employee created: {emp['id']}  (HTTP {resp2.status_code})")

        # ── Step 4: Stream employee events ───────────────────────────
        # Employee orchestrator publishes to channel:{role_id}
        await stream_ws(f"{WS_BASE}/employer/setup/{role_id}", "EMPLOYEE")

    print("\n✅ Full E2E test complete.")


if __name__ == "__main__":
    asyncio.run(run_test())
