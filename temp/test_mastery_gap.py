"""
Mock Test — Phase 8 (Mastery Scoring) + Phase 9 (Gap Analysis)
==============================================================
Uses realistic hardcoded mock data.
Does NOT require: DB, real resume PDF, or Phase 6/7 to have run.

Run:
  cd <project_root>
  python temp/test_mastery_gap.py
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.employee_flow.orchestrator import (
    compute_mastery_scores,
    compute_gap_analysis,
    run_gap_analysis,
    DEPTH_SCORE_MAP,
    TIER_WEIGHTS,
)

# ─────────────────────────────────────────────────────────────────────────────
# MOCK DATA — normalized employee skills (output of Phase 7 normalization)
# The 'context_depth' field is what the resume LLM extracted per skill.
# ─────────────────────────────────────────────────────────────────────────────
MOCK_NORMALIZED_SKILLS = [
    {
        "matched_name":  "Python",
        "canonical_id":  "TECH_python",
        "context_depth": "Led development of 12 production microservices using FastAPI and Python, processing 2M requests per day with 99.9% uptime.",
    },
    {
        "matched_name":  "Apache Spark",
        "canonical_id":  "TECH_apache_spark",
        "context_depth": "Architected and optimised PySpark ETL pipelines on Databricks, reducing job runtime from 4 h to 45 min on 10 TB datasets.",
    },
    {
        "matched_name":  "Docker",
        "canonical_id":  "TECH_docker",
        "context_depth": "Containerised applications and wrote Dockerfiles for team deployments.",
    },
    {
        "matched_name":  "Kubernetes",
        "canonical_id":  "TECH_kubernetes",
        "context_depth": "Surface mention in project tech-stack list.",
    },
    {
        "matched_name":  "SQL",
        "canonical_id":  "TECH_sql",
        "context_depth": "Wrote complex SQL queries with window functions, CTEs and query plan analysis for reporting dashboards serving 500+ stakeholders.",
    },
    {
        "matched_name":  "Machine Learning",
        "canonical_id":  "TECH_machine_learning",
        "context_depth": "Completed an online course in machine learning fundamentals (Coursera).",
    },
    {
        "matched_name":  "FastAPI",
        "canonical_id":  "TECH_fastapi",
        "context_depth": "Built REST APIs with FastAPI, including JWT auth, background tasks, and OpenAPI docs.",
    },
    {
        "matched_name":  "Redis",
        "canonical_id":  "TECH_redis",
        "context_depth": "Used Redis as a message broker for real-time event streaming in an internal notification system.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# MOCK DATA — role target skills (output of Employer Flow Phases 1-4)
# Reflects what the role requires at each tier.
# ─────────────────────────────────────────────────────────────────────────────
MOCK_TARGET_SKILLS = [
    {"skill_name": "Python",           "canonical_id": "TECH_python",           "target_mastery": 0.85, "tier": "T1"},
    {"skill_name": "Apache Spark",     "canonical_id": "TECH_apache_spark",     "target_mastery": 0.85, "tier": "T1"},
    {"skill_name": "Apache Kafka",     "canonical_id": "TECH_kafka",            "target_mastery": 0.70, "tier": "T1"},  # absent from resume
    {"skill_name": "Docker",           "canonical_id": "TECH_docker",           "target_mastery": 0.70, "tier": "T2"},
    {"skill_name": "Kubernetes",       "canonical_id": "TECH_kubernetes",       "target_mastery": 0.70, "tier": "T2"},
    {"skill_name": "Machine Learning", "canonical_id": "TECH_machine_learning", "target_mastery": 0.50, "tier": "T3"},
    {"skill_name": "FastAPI",          "canonical_id": "TECH_fastapi",          "target_mastery": 0.70, "tier": "T2"},
    {"skill_name": "SQL",              "canonical_id": "TECH_sql",              "target_mastery": 0.70, "tier": "T2"},
]

ROLE_ID = "mock-role-senior-de-001"

SEP = "═" * 72


async def main():
    print(SEP)
    print("  PHASE 8 — Current Mastery Scoring (LLM: openai/gpt-oss-20b + thinking ON)")
    print(SEP)
    print("\nDepth scale used:")
    for level, score in DEPTH_SCORE_MAP.items():
        print(f"  {level:<14} → {score:.2f}")
    print()

    mastery_skills = await compute_mastery_scores(MOCK_NORMALIZED_SKILLS, ROLE_ID)

    print("\n" + "─" * 72)
    print(f"  Scored {len(mastery_skills)} skills:")
    print("─" * 72)
    print(f"  {'Skill':<24} {'Depth Level':<14} {'Score':>6}   Reasoning")
    print("─" * 72)
    for s in mastery_skills:
        reasoning_short = (s.get("reasoning") or "")[:55]
        print(
            f"  {s['skill_name']:<24} "
            f"{s.get('depth_level', '?'):<14} "
            f"{s.get('current_mastery', 0.0):>6.2f}   {reasoning_short}"
        )

    print()
    print(SEP)
    print("  PHASE 9 — Gap Analysis (pure math, no LLM)")
    print(SEP)
    print("\nFormula:")
    print("  gap            = max(0, target_mastery - current_mastery)")
    print("  priority_score = tier_weight × gap")
    print(f"  tier_weights   = {TIER_WEIGHTS}")
    print()

    # Run the full async version (includes Redis event publishing)
    gap_records = await run_gap_analysis(mastery_skills, MOCK_TARGET_SKILLS, ROLE_ID)

    print("─" * 72)
    print(f"  {'Skill':<24} {'Tier':<5} {'Target':>7} {'Current':>8} {'Gap':>6}  {'Category':<10} {'Priority':>9}")
    print("─" * 72)
    for g in gap_records:
        print(
            f"  {g['skill_name']:<24} {g['tier']:<5} "
            f"{g['target_mastery']:>7.2f} {g['current_mastery']:>8.2f} "
            f"{g['gap']:>6.3f}  {g['gap_category']:<10} {g['priority_score']:>9.3f}"
        )

    print("─" * 72)
    critical = [g for g in gap_records if g["gap_category"] == "critical"]
    moderate = [g for g in gap_records if g["gap_category"] == "moderate"]
    minor    = [g for g in gap_records if g["gap_category"] == "minor"]
    met      = [g for g in gap_records if g["gap_category"] == "met"]

    print(
        f"\n  Summary → critical: {len(critical)}  moderate: {len(moderate)}  "
        f"minor: {len(minor)}  met: {len(met)}"
    )
    print()
    print("  Top 3 priority gaps:")
    for g in gap_records[:3]:
        print(
            f"    [{g['gap_category'].upper():<8}] {g['skill_name']} "
            f"(gap={g['gap']:.3f}, priority={g['priority_score']:.3f}) "
            f"— {g['assessment_reasoning'][:60]}"
        )

    print()
    print(SEP)
    print("  FULL GAP JSON OUTPUT")
    print(SEP)
    print(json.dumps(gap_records, indent=2))

    print()
    print("✓  Test complete.")


if __name__ == "__main__":
    asyncio.run(main())
