"""
AdaptIQ — Employee Onboarding Flow: Complete End-to-End Test
============================================================
Tests the full 11-phase employee pipeline by:
  1. POST /api/v1/employer/setup-role → creates a role (or uses env ROLE_ID to skip)
  2. Wait for employer flow to finish (WebSocket drain)
  3. POST /api/v1/employee/onboard-path → uploads resume PDF
  4. Subscribe to WebSocket and capture ALL events in sequence
  5. Pretty-print every event with phase / type / step
  6. Highlight Phase 10 course retrieval (sprint/balanced/quality per skill)
  7. Highlight Phase 11 journey tree and narratives
  8. Validate that all expected phases fire in the correct order

Usage:
  # Full run (creates new role + employee):
  python temp/test_employee_e2e.py

  # Skip employer flow — reuse existing role:
  ROLE_ID=<uuid> python temp/test_employee_e2e.py

Required files:
  temp/resume.pdf   — resume PDF to upload
  temp/jd.pdf       — job description PDF (only needed for fresh role creation)
  temp/team.pdf     — team context PDF   (only needed for fresh role creation)

Server must be running:
  $env:PYTHONPATH = "<project_root>"
  python -m uvicorn app.main:app --port 8000 --reload
"""

import asyncio
import json
import os
import sys
import textwrap
import time
from collections import defaultdict
from pathlib import Path

import httpx
import websockets

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000/api/v1")
WS_BASE  = os.getenv("WS_BASE",  "ws://127.0.0.1:8000/ws")

TEMP_DIR   = Path(__file__).parent
RESUME_PDF = TEMP_DIR / "resume.pdf"
JD_PDF     = TEMP_DIR / "jd.pdf"
TEAM_PDF   = TEMP_DIR / "team.pdf"

# Set ROLE_ID in env to skip employer flow and reuse an existing role
EXISTING_ROLE_ID = os.getenv("ROLE_ID", "")

# ── Terminal colours ──────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

DIM   = lambda t: _c("90", t)
GREEN = lambda t: _c("92", t)
CYAN  = lambda t: _c("96", t)
BLUE  = lambda t: _c("94", t)
YEL   = lambda t: _c("93", t)
RED   = lambda t: _c("91", t)
BOLD  = lambda t: _c("1",  t)
MAG   = lambda t: _c("95", t)

# ── Phase colour map ──────────────────────────────────────────────────────────
PHASE_COLOR = {
    "resume_extraction": CYAN,
    "normalization":      GREEN,
    "mastery":            YEL,
    "gap":                MAG,
    "path":               BLUE,
    "journey":            lambda t: _c("38;5;208", t),   # orange
    "db":                 lambda t: _c("92", t),
}

# ── Expected phase order for validation ──────────────────────────────────────
EXPECTED_PHASES = [
    "resume_extraction",
    "normalization",
    "mastery",
    "gap",
    "path",
    "journey",
    "db",
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _sep(char: str = "─", width: int = 72) -> str:
    return char * width

def _print_event_header(event: dict):
    phase = event.get("phase", "?")
    etype = event.get("type",  "?")
    step  = event.get("step",  "?")
    msg   = event.get("message", "")
    color = PHASE_COLOR.get(phase, lambda t: t)

    label = color(f"[{phase.upper()}]")
    type_tag = f"({etype})"
    step_tag = BOLD(step)
    print(f"\n{label} {step_tag} {DIM(type_tag)}")
    if msg:
        print(f"  {msg}")

def _print_skill_list(skills: list):
    for s in skills:
        name  = s.get("skill_name") or s.get("skill") or s.get("coined_name") or "?"
        ctx   = s.get("context_depth") or s.get("reasoning") or ""
        score = s.get("current_mastery") or s.get("gap") or s.get("priority_score") or ""
        score_str = f"  [{score:.2f}]" if isinstance(score, float) else ""
        print(f"    {BOLD(name)}{score_str}")
        if ctx:
            wrapped = textwrap.fill(ctx, width=62, initial_indent="      ", subsequent_indent="      ")
            print(DIM(wrapped))

def _print_gap_summary(data: dict):
    summary = data.get("summary", {})
    ranked  = data.get("ranked_gaps", [])
    print(f"  critical={summary.get('critical',0)}  moderate={summary.get('moderate',0)}  "
          f"minor={summary.get('minor',0)}  met={summary.get('met',0)}")
    for g in ranked:
        cat_color = RED if g["gap_category"] == "critical" else YEL
        print(f"    {cat_color(g['gap_category'].upper())} {BOLD(g['skill_name'])}  "
              f"gap={g['gap']:.3f}  priority={g['priority_score']:.3f}")

def _print_nsga_gap(data: dict):
    """Highlight Phase 10 course selection per gap."""
    skill   = data.get("skill", "?")
    stage   = data.get("stage", "?")
    cat     = data.get("gap_category", "?")
    cands   = data.get("candidates", "?")
    pareto  = data.get("pareto_front", "?")
    sprint  = data.get("sprint_title",   "—")
    balanced= data.get("balanced_title", "—")
    quality = data.get("quality_title",  "—")

    cat_c = RED if cat == "critical" else YEL
    print(f"  Stage {stage} │ {BOLD(skill)} {cat_c(f'[{cat}]')}  "
          f"candidates={cands}  pareto_front={pareto}")
    print(f"    {GREEN('Sprint  ')} : {sprint}")
    print(f"    {BLUE('Balanced')} : {balanced}")
    print(f"    {MAG('Quality ')} : {quality}")

def _print_paths_ready(data: dict):
    sprint  = data.get("sprint",  {})
    balanced= data.get("balanced",{})
    quality = data.get("quality", {})
    print(f"  {GREEN('Sprint  ')} : {sprint.get('total_weeks','?')} weeks  coverage={sprint.get('coverage_score','?')}")
    print(f"  {BLUE('Balanced')} : {balanced.get('total_weeks','?')} weeks  coverage={balanced.get('coverage_score','?')}")
    print(f"  {MAG('Quality ')} : {quality.get('total_weeks','?')} weeks  coverage={quality.get('coverage_score','?')}")
    print(f"  total_skills_planned: {data.get('total_skills_planned','?')}")

def _print_journey_ready(data: dict):
    narratives = data.get("narratives", {})
    summaries  = data.get("path_summaries", {})
    validation = data.get("validation", {})

    print(f"  Validation: sprint_ok={validation.get('sprint_ok')}  "
          f"balanced_ok={validation.get('balanced_ok')}  quality_ok={validation.get('quality_ok')}")
    if validation.get("notes"):
        print(f"  Notes: {DIM(validation['notes'])}")

    print()
    for track in ["sprint", "balanced", "quality"]:
        n = narratives.get(track, "")
        s = summaries.get(track, {})
        label = f"  [{track.upper()}]  {s.get('total_weeks','?')} wks"
        print(BOLD(label))
        if n:
            wrapped = textwrap.fill(n, width=66, initial_indent="    ", subsequent_indent="    ")
            print(wrapped)
        print()

    # Print tree root + first level if present
    tree = data.get("tree", {})
    root = tree.get("root", {})
    if root:
        print(f"  Tree root: {BOLD(root.get('label','?'))} [{root.get('type','?')}]")
        for child in root.get("children", [])[:5]:
            sev = child.get("severity", "")
            sev_c = RED if sev == "critical" else YEL if sev == "moderate" else DIM
            print(f"    └─ {sev_c(BOLD(child.get('label','?')))} "
                  f"stage={child.get('stage','?')} gap={child.get('gap','?')}")
            courses = child.get("course_options", {}) or {}
            for track in ["sprint", "balanced", "quality"]:
                c = courses.get(track) or {}
                if c.get("title"):
                    print(f"         {track:8}: {c['title']} ({c.get('weeks','?')} wks)")
            for twig in child.get("children", []):
                print(f"       └─ {DIM(twig.get('label','?'))} (prerequisite)")

# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET LISTENER
# ─────────────────────────────────────────────────────────────────────────────

async def drain_websocket(
    role_id: str,
    ws_path: str,
    stop_on: str = "db/complete",
    label: str = "flow",
    timeout_s: int = 600,
) -> list[dict]:
    """
    Connect to WebSocket, collect all events until stop condition, return them.
    stop_on = "<phase>/<type>" e.g. "db/complete"
    """
    uri = f"{WS_BASE}/{ws_path}/{role_id}"
    print(f"\n{DIM('Connecting to WebSocket:')} {uri}")

    all_events  = []
    stream_buf  = defaultdict(str)   # key=step, accumulates streaming text
    stream_phase = None

    start_t = time.time()

    try:
        async with websockets.connect(uri, open_timeout=20, ping_timeout=60) as ws:
            print(GREEN(f"✓ WebSocket connected — listening for {label} events …\n"))
            print(_sep("═"))

            while True:
                if time.time() - start_t > timeout_s:
                    print(RED(f"\n⚠  Timeout ({timeout_s}s) — ending early."))
                    break

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                except asyncio.TimeoutError:
                    print(RED("\n⚠  recv() timeout — server may have stalled."))
                    break

                event = json.loads(raw)
                all_events.append(event)

                phase = event.get("phase", "?")
                etype = event.get("type",  "?")
                step  = event.get("step",  "?")
                data  = event.get("data",  {})

                # ── Streaming chunks: buffer and print inline ─────────────────
                if etype == "stream_chunk":
                    chunk_type = data.get("chunk_type", "content")
                    text       = data.get("text", "")
                    if chunk_type == "reasoning":
                        print(DIM(text), end="", flush=True)
                        stream_buf[step + "_reasoning"] += text
                    else:
                        print(GREEN(text), end="", flush=True)
                        stream_buf[step + "_content"] += text
                    stream_phase = phase
                    continue

                # ── After a stream block — print newline ─────────────────────
                if etype == "stream_end":
                    r_len = len(stream_buf.get(step + "_reasoning", ""))
                    c_len = len(stream_buf.get(step + "_content",   ""))
                    print(f"\n{DIM(f'  [stream_end] reasoning={r_len}  content={c_len}')}")
                    continue

                # ── All other events ─────────────────────────────────────────
                _print_event_header(event)

                # Phase-specific pretty printing
                if step == "llm_extraction_done":
                    skills = data.get("skills", [])
                    print(f"  Extracted {len(skills)} skills:")
                    _print_skill_list(skills[:8])
                    if len(skills) > 8:
                        print(DIM(f"  … and {len(skills)-8} more"))

                elif step in ("llm_judge", "llm_coined"):
                    raw_s  = data.get("raw_skill", "?")
                    match  = data.get("matched_name") or data.get("coined_name") or "?"
                    canon  = data.get("canonical_id", "?")
                    src    = data.get("source", "?")
                    src_c  = GREEN if src == "onet_match" else MAG
                    print(f"  {raw_s!r:30} → {BOLD(match)!s}  {src_c(f'[{src}]')} {DIM(canon)}")

                elif step == "normalization_done":
                    print(f"  matched={data.get('matched','?')}  "
                          f"coined={data.get('coined','?')}  "
                          f"total={data.get('total','?')}")

                elif step == "skill_mastery_computed":
                    name  = data.get("skill_name", "?")
                    lvl   = data.get("depth_level", "?")
                    score = data.get("current_mastery", 0)
                    rsn   = data.get("reasoning", "")
                    lvl_c = GREEN if lvl == "expert" else BLUE if lvl == "advanced" else YEL
                    print(f"  {BOLD(name):30} {lvl_c(lvl):<14} {score:.2f}")
                    if rsn:
                        print(DIM(f"    {rsn[:100]}"))

                elif step == "mastery_scoring_done":
                    skills = data.get("skills", [])
                    print(f"  Scored {len(skills)} skills:")
                    _print_skill_list(skills[:6])

                elif step == "gap_analysis_done":
                    _print_gap_summary(data)

                elif step == "skill_gap_computed":
                    name  = data.get("skill_name", "?")
                    gap   = data.get("gap", 0)
                    cat   = data.get("gap_category", "?")
                    prio  = data.get("priority_score", 0)
                    cat_c = RED if cat == "critical" else YEL if cat == "moderate" else DIM
                    print(f"  {BOLD(name):30} gap={gap:.3f}  {cat_c(cat)}  prio={prio:.3f}")

                elif step == "nsga_gap_done":
                    _print_nsga_gap(data)

                elif step == "paths_ready":
                    _print_paths_ready(data)

                elif step == "journey_ready":
                    _print_journey_ready(data)

                elif step == "employee_persist_done":
                    gap_s = data.get("gap_summary", {})
                    paths = data.get("learning_paths", {})
                    print(f"  skills={data.get('total_skills','?')}  "
                          f"mastery={data.get('mastery_count','?')}  "
                          f"gaps: {gap_s}")
                    if paths:
                        print(f"  sprint={paths.get('sprint_weeks','?')}w  "
                              f"balanced={paths.get('balanced_weeks','?')}w  "
                              f"quality={paths.get('quality_weeks','?')}w")

                # ── Stop condition ─────────────────────────────────────────
                stop_phase, stop_type = stop_on.split("/")
                if phase == stop_phase and etype == stop_type:
                    print(f"\n{_sep('═')}")
                    print(GREEN(f"✓ Stop condition reached: {stop_on}"))
                    break

                if etype == "error":
                    print(RED(f"\n✗ Server error: {event.get('message','')}"))
                    print(RED(f"  data: {json.dumps(data, indent=2)}"))
                    break

    except websockets.exceptions.ConnectionClosedError as e:
        print(RED(f"\n✗ WebSocket closed unexpectedly: {e}"))
    except Exception as e:
        print(RED(f"\n✗ WebSocket error: {e}"))

    elapsed = time.time() - start_t
    print(f"\n{DIM(f'Total events: {len(all_events)}  Elapsed: {elapsed:.1f}s')}")
    return all_events

# ─────────────────────────────────────────────────────────────────────────────
# PHASE SEQUENCE VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

def validate_event_sequence(events: list[dict]) -> bool:
    """Check that all expected phases fired and in the right order."""
    print(f"\n{_sep('─')}")
    print(BOLD("Event Sequence Validation"))
    print(_sep("─"))

    seen_phases = []
    step_counts: dict[str, int] = defaultdict(int)
    for ev in events:
        phase = ev.get("phase", "?")
        step  = ev.get("step",  "?")
        step_counts[step] += 1
        if phase not in seen_phases:
            seen_phases.append(phase)

    all_ok = True
    for i, expected in enumerate(EXPECTED_PHASES):
        if expected in seen_phases:
            actual_i = seen_phases.index(expected)
            ok = actual_i >= i  # must appear at or after expected position
            icon = GREEN("✓") if ok else RED("✗")
            print(f"  {icon} {expected}")
            if not ok:
                all_ok = False
        else:
            print(f"  {RED('✗')} {expected}  {RED('(MISSING)')}")
            all_ok = False

    print()
    print(BOLD("Event counts (non-stream):"))
    for step, count in sorted(step_counts.items(), key=lambda x: -x[1]):
        if not any(s in step for s in ("streaming", "stream_chunk")):
            print(f"  {step:<45} {count:>4}×")

    # Specific checks
    print()
    nsga_events = [e for e in events if e.get("step") == "nsga_gap_done"]
    journey_ev  = next((e for e in events if e.get("step") == "journey_ready"), None)
    paths_ev    = next((e for e in events if e.get("step") == "paths_ready"), None)

    checks = [
        ("resume extraction fired",   any(e.get("step") == "llm_extraction_done" for e in events)),
        ("normalization fired",        any(e.get("step") == "normalization_done" for e in events)),
        ("mastery scoring fired",      any(e.get("step") == "mastery_scoring_done" for e in events)),
        ("gap analysis fired",         any(e.get("step") == "gap_analysis_done" for e in events)),
        ("NSGA-II events fired",       len(nsga_events) > 0),
        ("paths_ready fired",          paths_ev is not None),
        ("journey_ready fired",        journey_ev is not None),
        ("journey has narratives",     bool(journey_ev and journey_ev.get("data", {}).get("narratives"))),
        ("journey has tree",           bool(journey_ev and journey_ev.get("data", {}).get("tree"))),
        ("persist complete fired",     any(e.get("step") == "employee_persist_done" for e in events)),
    ]

    for desc, result in checks:
        icon = GREEN("✓") if result else RED("✗")
        mark = "" if result else f"  {RED('← FAILED')}"
        print(f"  {icon} {desc}{mark}")
        if not result:
            all_ok = False

    print()
    if all_ok:
        print(GREEN(BOLD("ALL CHECKS PASSED ✓")))
    else:
        print(RED(BOLD("SOME CHECKS FAILED ✗ — see above")))
    return all_ok

# ─────────────────────────────────────────────────────────────────────────────
# COURSE RETRIEVAL SUMMARY (Phase 10)
# ─────────────────────────────────────────────────────────────────────────────

def print_course_retrieval_summary(events: list[dict]):
    nsga_evs = [e for e in events if e.get("step") == "nsga_gap_done"]
    if not nsga_evs:
        print(DIM("  No nsga_gap_done events captured."))
        return

    print(f"\n{_sep('═')}")
    print(BOLD(f"Phase 10 — Course Retrieval Summary   ({len(nsga_evs)} skill gaps)"))
    print(_sep("─"))

    by_stage: dict[int, list] = defaultdict(list)
    for ev in nsga_evs:
        by_stage[ev["data"].get("stage", 0)].append(ev)

    for stage_num in sorted(by_stage.keys()):
        stage_evs = by_stage[stage_num]
        print(f"\n  Stage {stage_num}:")
        for ev in stage_evs:
            d = ev["data"]
            cat_c = RED if d.get("gap_category") == "critical" else YEL
            print(f"    {BOLD(d.get('skill','?'))!s}  {cat_c(d.get('gap_category','?'))}")
            print(f"      Qdrant candidates : {d.get('candidates','?')}  "
                  f"Pareto front : {d.get('pareto_front','?')}")
            print(f"      {GREEN('Sprint  ')} → {d.get('sprint_title','—')}")
            print(f"      {BLUE('Balanced')} → {d.get('balanced_title','—')}")
            print(f"      {MAG('Quality ')} → {d.get('quality_title','—')}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN TEST FLOW
# ─────────────────────────────────────────────────────────────────────────────

async def run_employer_setup() -> str:
    """Create a new role and wait for the employer flow to complete."""
    print(BOLD("\n══════ Step 1: Create Role (Employer Flow) ══════"))

    if not JD_PDF.exists():
        raise FileNotFoundError(f"JD PDF not found: {JD_PDF}")
    if not TEAM_PDF.exists():
        raise FileNotFoundError(f"Team PDF not found: {TEAM_PDF}")

    async with httpx.AsyncClient(timeout=30) as client:
        with open(JD_PDF, "rb") as jd_f, open(TEAM_PDF, "rb") as team_f:
            res = await client.post(
                f"{API_BASE}/employer/setup-role",
                data={"title": "Data Engineer", "seniority": "senior"},
                files={
                    "jd_file":           ("jd.pdf",   jd_f,   "application/pdf"),
                    "team_context_file": ("team.pdf", team_f, "application/pdf"),
                },
            )
    res.raise_for_status()
    role_id = res.json()["id"]
    print(f"  {GREEN('✓')} Role created: {BOLD(role_id)}")

    # Wait for employer flow to complete before starting employee
    await drain_websocket(
        role_id=role_id,
        ws_path="employer/setup",
        stop_on="db/complete",
        label="employer",
        timeout_s=300,
    )

    # Give the background DB writes time to commit before the employee flow queries them
    # The employer orchestrator persists target_skills via asyncio.ensure_future (fire-and-forget)
    # so they may not be committed at the exact moment db/complete fires.
    print(DIM("  Waiting 8s for employer DB writes to commit..."))
    await asyncio.sleep(8)

    return role_id


async def run_employee_flow(role_id: str) -> list[dict]:
    """Upload resume and run the full employee 11-phase pipeline."""
    print(BOLD(f"\n══════ Step 2: Onboard Employee (role_id={role_id}) ══════"))

    if not RESUME_PDF.exists():
        raise FileNotFoundError(f"Resume PDF not found: {RESUME_PDF}")

    async with httpx.AsyncClient(timeout=30) as client:
        with open(RESUME_PDF, "rb") as rf:
            res = await client.post(
                f"{API_BASE}/employee/onboard-path",
                data={"role_id": role_id},
                files={"resume_file": ("resume.pdf", rf, "application/pdf")},
            )
    res.raise_for_status()
    emp_data = res.json()
    employee_id = emp_data.get("id") or emp_data.get("employee_id")
    print(f"  {GREEN('✓')} Employee created: {BOLD(employee_id)}")
    print(f"  {DIM('Starting WebSocket listener …')}")

    events = await drain_websocket(
        role_id=role_id,
        ws_path="employer/setup",   # employee events publish to channel:{role_id}
        stop_on="db/complete",
        label="employee",
        timeout_s=600,
    )
    return events


async def main():
    print(_sep("═", 72))
    print(BOLD("AdaptIQ — Employee Onboarding E2E Test"))
    print(_sep("═", 72))
    print(f"  API   : {API_BASE}")
    print(f"  WS    : {WS_BASE}")
    print(f"  Resume: {RESUME_PDF}")

    # ── Step 1: Employer setup ────────────────────────────────────────────────
    if EXISTING_ROLE_ID:
        role_id = EXISTING_ROLE_ID
        print(f"\n  {YEL('Skipping employer flow — using ROLE_ID=')} {BOLD(role_id)}")
    else:
        try:
            role_id = await run_employer_setup()
        except FileNotFoundError as e:
            print(RED(f"\n✗ {e}"))
            print(DIM("  Set ROLE_ID=<uuid> env var to skip employer setup."))
            return

    # ── Step 2: Employee flow ─────────────────────────────────────────────────
    try:
        events = await run_employee_flow(role_id)
    except httpx.HTTPStatusError as e:
        print(RED(f"\n✗ HTTP error: {e.response.status_code} — {e.response.text}"))
        return
    except FileNotFoundError as e:
        print(RED(f"\n✗ {e}"))
        return

    # ── Phase 10: Course retrieval details ────────────────────────────────────
    print_course_retrieval_summary(events)

    # ── Phase 11: Journey tree ────────────────────────────────────────────────
    journey_ev = next((e for e in events if e.get("step") == "journey_ready"), None)
    if journey_ev:
        print(f"\n{_sep('═')}")
        print(BOLD("Phase 11 — Journey Narration Output"))
        print(_sep("─"))
        _print_journey_ready(journey_ev.get("data", {}))

    # ── Validation report ─────────────────────────────────────────────────────
    ok = validate_event_sequence(events)

    print(f"\n{_sep('═')}")
    if ok:
        print(GREEN(BOLD("E2E TEST PASSED ✓")))
    else:
        print(RED(BOLD("E2E TEST FAILED ✗")))
    print(_sep("═"))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(DIM("\nInterrupted by user."))
