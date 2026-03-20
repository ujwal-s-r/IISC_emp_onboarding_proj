"""
Standalone test for the LLM-based Skill Normalizer.

Run from project root:
    venv\\Scripts\\python.exe -m app.scripts.test_normalizer

Tests the full pipeline:
  1. Embed raw skill name
  2. Query Qdrant top-3
  3. LLM judge picks the best candidate OR
  4. LLM coins a new canonical name → auto-creates node in Qdrant + Neo4j
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.skill_normalizer import normalize_skill


# ── Test samples – a range of easy/hard/unknown skills ──────────────────────
TEST_SKILLS = [
    "PySpark",                      # Should match TECH_ node easily
    "ReactJS",                      # Should match a Technology node
    "Managing stakeholders",        # Soft skill – may not match exactly, LLM should coin
    "Kubernetes",                    # Should match clearly
    "Temporal Reasoning Architecture",  # Totally novel – LLM should coin a new node
    "Excel",                        # Ambiguous – LLM should clarify (Microsoft Excel?)
    "Python",                        # Classic match
]


async def main():
    print("="*65)
    print("  LLM Skill Normalizer — Test Run")
    print("="*65 + "\n")

    for raw in TEST_SKILLS:
        print(f"  ▶ Input:  '{raw}'")
        result = await normalize_skill(raw)
        source   = result["source"]
        name     = result["matched_name"]
        cid      = result["canonical_id"]
        level    = result["onet_level"]

        icon = "✅" if source == "onet_match" else "🆕" if source == "llm_new" else "❌"
        print(f"    {icon} Matched: '{name}'")
        print(f"       Source:       {source}")
        print(f"       Canonical ID: {cid}")
        print(f"       O*NET Level:  {level}")
        print()

    print("="*65)
    print("  Test complete.")


if __name__ == "__main__":
    import platform
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            pass  # Suppress known Windows httpx asyncio cleanup noise
        else:
            raise
