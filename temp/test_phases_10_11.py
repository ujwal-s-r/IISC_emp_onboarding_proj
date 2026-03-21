"""
test_phases_10_11.py
====================
End-to-end test for Phase 10 (Dependency Resolution + NSGA-II Path Generation)
and Phase 11 (Journey Narration + Visualization Tree).

Mock strategy:
  - redis_client.publish_event  → patched to a no-op logger (Redis not required)
  - graph_client / Neo4j        → graceful fallback already built in (will log a warning)
  - Qdrant Instance 2           → REAL call to 'courses_listed' collection
  - Nvidia embedding + gpt-oss  → REAL calls

Run from project root:
  python -m temp.test_phases_10_11
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# ── Patch Redis BEFORE importing any app module that instantiates the client ──
import unittest.mock as mock

async def _noop_publish(self, role_id="", phase="?", event_type="", step="?", message="", model=None, data=None):
    print(f"  [REDIS EVENT] {phase}/{step} → {message}")

# Patch the publish_event method on the class so the singleton picks it up
from app.clients import redis_client as redis_module
redis_module.RedisClient.publish_event = _noop_publish  # type: ignore

# ── Now import app modules ────────────────────────────────────────────────────
from app.services.employee_flow.dependency_resolver import resolve_dependencies
from app.services.employee_flow.path_generator      import generate_paths
from app.services.employee_flow.journey_narrator    import narrate_journey

# ── Mock gap records (Phase 9 output format) ──────────────────────────────────
# Simulates a Data Analyst employee with 4 critical/moderate gaps
MOCK_ROLE_ID    = "test-role-data-analyst-001"
MOCK_ROLE_TITLE = "Senior Data Analyst"

MOCK_GAP_RECORDS = [
    {
        "skill_name":       "Python Programming",
        "onet_element_id":  "2.C.3.a",
        "is_coined":        False,
        "gap_category":     "critical",
        "current_mastery":  0.20,
        "target_mastery":   0.85,
        "gap_score":        0.65,
        "current_label":    "Basic",
        "target_label":     "Expert",
        "evidence_count":   1,
    },
    {
        "skill_name":       "SQL",
        "onet_element_id":  "2.C.3.b",
        "is_coined":        False,
        "gap_category":     "critical",
        "current_mastery":  0.25,
        "target_mastery":   0.80,
        "gap_score":        0.55,
        "current_label":    "Basic",
        "target_label":     "Advanced",
        "evidence_count":   1,
    },
    {
        "skill_name":       "Machine Learning",
        "onet_element_id":  "2.C.3.c",
        "is_coined":        False,
        "gap_category":     "moderate",
        "current_mastery":  0.30,
        "target_mastery":   0.70,
        "gap_score":        0.40,
        "current_label":    "Basic",
        "target_label":     "Proficient",
        "evidence_count":   2,
    },
    {
        "skill_name":       "Data Visualization",
        "onet_element_id":  "2.C.3.d",
        "is_coined":        True,
        "gap_category":     "moderate",
        "current_mastery":  0.35,
        "target_mastery":   0.65,
        "gap_score":        0.30,
        "current_label":    "Basic",
        "target_label":     "Proficient",
        "evidence_count":   2,
    },
    # This one should be ignored (minor gap — not critical/moderate)
    {
        "skill_name":       "Excel",
        "onet_element_id":  "2.C.3.e",
        "is_coined":        False,
        "gap_category":     "minor",
        "current_mastery":  0.70,
        "target_mastery":   0.80,
        "gap_score":        0.10,
        "current_label":    "Proficient",
        "target_label":     "Advanced",
        "evidence_count":   3,
    },
]


def _print_section(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _print_dag(dag: dict):
    stages = dag.get("stages", [])
    edges  = dag.get("dependency_edges", [])
    print(f"  Stages  : {len(stages)}")
    print(f"  Edges   : {len(edges)}")
    for s in stages:
        print(f"  Stage {s['stage']}: {s['skills']}")
        print(f"           → {s.get('rationale', '')}")
    if edges:
        print()
        print("  Dependency edges:")
        for e in edges:
            print(f"    {e.get('from')} → {e.get('to')}  [{e.get('type', '')}]")


def _print_path_sample(label: str, path: list):
    print(f"\n  [{label}]")
    for entry in path:
        course = entry.get("course") or {}
        title  = course.get("title", "— no course found —")
        dur    = course.get("duration_label", "?")
        sim    = course.get("cosine_sim", 0.0)
        rating = course.get("rate", 0.0)
        print(f"    Stage {entry['stage']} | {entry['skill']:<25} → {title[:45]:<45}  ({dur}, sim={sim:.3f}, ⭐{rating})")


def _print_tree_summary(journey: dict):
    tree = journey.get("tree", {})
    root = tree.get("root", {})
    children = root.get("children", [])
    print(f"  Tree root    : {root.get('label', '?')}")
    print(f"  Main branches: {len(children)}")
    for ch in children:
        twigs = ch.get("children", [])
        co    = ch.get("course_options", {})
        print(f"    [{ch.get('severity','?').upper()}] {ch.get('label','?')} (stage {ch.get('stage',0)}, gap={ch.get('gap',0):.2f})")
        print(f"      Twigs    : {[t['label'] for t in twigs] or 'none'}")
        print(f"      Sprint   : {co.get('sprint',{}).get('title','—')[:50]}")
        print(f"      Balanced : {co.get('balanced',{}).get('title','—')[:50]}")
        print(f"      Quality  : {co.get('quality',{}).get('title','—')[:50]}")


async def main():
    # ══════════════════════════════════════════════════════════════════════════
    _print_section("PHASE 10A — Dependency Resolution (Neo4j + gpt-oss-20b)")
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n  Input gaps : {[g['skill_name'] for g in MOCK_GAP_RECORDS if g['gap_category'] in ('critical','moderate')]}")
    print(f"  Role ID    : {MOCK_ROLE_ID}")
    print()

    dag = await resolve_dependencies(
        gap_records=MOCK_GAP_RECORDS,
        role_id=MOCK_ROLE_ID,
    )

    _print_section("DAG Result")
    _print_dag(dag)

    # ══════════════════════════════════════════════════════════════════════════
    _print_section("PHASE 10B — NSGA-II Course Selection (Qdrant Instance 2)")
    # ══════════════════════════════════════════════════════════════════════════
    print()
    path_result = await generate_paths(
        dag=dag,
        role_id=MOCK_ROLE_ID,
    )

    _print_section("Path Generation Result")
    gap_options = path_result.get("gap_options", {})
    print(f"  Skills processed: {len(gap_options)}")
    print()

    # Show Pareto picks per skill
    for skill, opts in gap_options.items():
        print(f"  {skill}:")
        for track in ("sprint", "balanced", "quality"):
            c = opts.get(track) or {}
            title = c.get("title", "—")[:45]
            print(f"    {track:<8}: {title:<45}  f1={c.get('obj_f1_relevance',0):.3f} f2={c.get('obj_f2_speed',0):.3f} f3={c.get('obj_f3_quality',0):.3f} f4={c.get('obj_f4_level_match',0):.3f}")
        print()

    # Full path views
    _print_path_sample("SPRINT PATH",   path_result["sprint_path"])
    _print_path_sample("BALANCED PATH", path_result["balanced_path"])
    _print_path_sample("QUALITY PATH",  path_result["quality_path"])

    # Stats
    sprint_stats   = path_result.get("sprint_stats",   {"total_weeks": 0})
    balanced_stats = path_result.get("balanced_stats", {"total_weeks": 0})
    quality_stats  = path_result.get("quality_stats",  {"total_weeks": 0})
    print()
    print(f"  Path durations:  Sprint={sprint_stats.get('total_weeks',0)} wk"
          f"  |  Balanced={balanced_stats.get('total_weeks',0)} wk"
          f"  |  Quality={quality_stats.get('total_weeks',0)} wk")
    print(f"  Coverage scores: Sprint={sprint_stats.get('coverage_score',0):.3f}"
          f"  |  Balanced={balanced_stats.get('coverage_score',0):.3f}"
          f"  |  Quality={quality_stats.get('coverage_score',0):.3f}")

    # ══════════════════════════════════════════════════════════════════════════
    _print_section("PHASE 11 — Journey Narration (gpt-oss-20b thinking)")
    # ══════════════════════════════════════════════════════════════════════════
    print()

    journey = await narrate_journey(
        role_title=MOCK_ROLE_TITLE,
        path_result=path_result,
        role_id=MOCK_ROLE_ID,
    )

    _print_section("Journey Result")

    # Validation
    val = journey.get("validation", {})
    print(f"  Validation:")
    print(f"    Sprint OK   : {val.get('sprint_ok')}")
    print(f"    Balanced OK : {val.get('balanced_ok')}")
    print(f"    Quality OK  : {val.get('quality_ok')}")
    print(f"    Notes       : {val.get('notes','')}")

    # Narratives
    narr = journey.get("narratives", {})
    print()
    print("  Narratives:")
    print(f"    [Sprint]   {narr.get('sprint','')}")
    print(f"    [Balanced] {narr.get('balanced','')}")
    print(f"    [Quality]  {narr.get('quality','')}")

    # Tree summary
    _print_section("Visualization Tree")
    _print_tree_summary(journey)

    # Path summaries from LLM
    psumm = journey.get("path_summaries", {})
    print()
    print("  Path summaries (from LLM):")
    for track in ("sprint", "balanced", "quality"):
        ps = psumm.get(track, {})
        print(f"    {track:<8}: {ps.get('total_weeks',0)} weeks  |  coverage={ps.get('coverage_score',0):.3f}  |  {ps.get('label','')}")

    # ══════════════════════════════════════════════════════════════════════════
    _print_section("FULL JOURNEY JSON (tree structure only)")
    # ══════════════════════════════════════════════════════════════════════════
    tree_json = json.dumps(journey.get("tree", {}), indent=2, ensure_ascii=False)
    # Print first 120 lines max to avoid flooding the console
    lines = tree_json.splitlines()
    if len(lines) > 120:
        print("\n".join(lines[:120]))
        print(f"  ... ({len(lines) - 120} more lines — full tree available in journey dict)")
    else:
        print(tree_json)

    print()
    print("=" * 70)
    print("  ALL PHASES 10-11 COMPLETE ✓")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
