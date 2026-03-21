"""
Employer Flow Orchestrator
==========================
Orchestrates the full employer analysis pipeline with fine-grained Redis events
emitted at every decision point for real-time frontend visibility:

  Phase 1 — jd_extraction:  Parse PDFs → LLM skill extraction
  Phase 2 — normalization:   O*NET skill normalization (see skill_normalizer.py)
  Phase 3 — team_context:   LLM team relevance tiering
  Phase 4 — mastery:        2D Mastery Matrix computation
  Phase 5 — db:             SQLite persistence

All events are published to Redis channel: channel:{role_id}
See docs/employer_redis.md for the full JSON event schema.
"""
import json
import re
from typing import List, Dict, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_creator import agent_creator
from app.services.pdf_service import pdf_service
from app.services.skill_normalizer import normalize_skills
from app.clients.redis_client import redis_client
from app.clients.nvidia_llm_client import orchestrator_llm_client, ORCHESTRATOR_MODEL
from app.models.domain import Role, TargetSkill, TeamRelevanceSignal
from app.utils.logger import logger

# ── Model identifier ────────────────────────────────────────────────────────
ORCHESTRATOR_MODEL_TAG = ORCHESTRATOR_MODEL

# ── Prompts ─────────────────────────────────────────────────────────────────

JD_EXTRACTION_PROMPT = """
You are an expert HR and Technical Skills Analyst. Your task is to extract required skills from the following Job Description (JD).
For each skill, you must identify:
1. Canonical Skill Name (e.g., 'Apache PySpark' instead of 'Spark').
2. Required JD Level: 'junior', 'mid', 'senior', or 'lead'.
3. Knowledge Category: 'framework', 'language', 'platform', or 'concept'.
4. Brief Reasoning: Why this level and category were assigned based on the text.

Output MUST be a valid JSON array of objects with the following keys exactly:
"skill_name", "jd_level", "category", "reasoning".

Job Description:
{jd_text}
"""

TEAM_CONTEXT_PROMPT = """
You are analyzing internal team documentation for a new hire.
Your goal is to find which of the provided 'skills' are actually mentioned in the team context, and determine their recency/importance.

For each skill provided in the list that is found in the text, determine:
1. Recency Category: "current_project", "past_project", or "general". (If currently critical, use current_project).
2. Reasoning: A brief explanation based on the text of why you assigned this recency.

Output MUST be a valid JSON array of objects with keys: "skill_name", "recency_category", "reasoning".
If a skill is NOT found, omit it from the array.

Target Skills to look for:
{skills_list}

Team Context Document:
{team_text}
"""

# ── Constants: 2D Mastery Matrix ─────────────────────────────────────────────

MASTERY_MATRIX = {
    "intern": {"T1": 0.35, "T2": 0.20, "T3": 0.10, "T4": 0.10},
    "junior": {"T1": 0.50, "T2": 0.35, "T3": 0.20, "T4": 0.20},
    "mid":    {"T1": 0.70, "T2": 0.55, "T3": 0.35, "T4": 0.35},
    "senior": {"T1": 0.85, "T2": 0.70, "T3": 0.50, "T4": 0.50},
    "lead":   {"T1": 0.95, "T2": 0.80, "T3": 0.60, "T4": 0.60},
}

TIER_RELEVANCE = {"T1": 1.0, "T2": 0.7, "T3": 0.4, "T4": 0.1}
ONET_COLLECTION = "onet_skills"
NORMALIZATION_THRESHOLD = 0.70


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clean_json(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def calculate_tier(recency: str) -> str:
    return {"current_project": "T1", "general": "T2", "past_project": "T3"}.get(recency, "T4")


# ── Convenience publisher ─────────────────────────────────────────────────────

async def _pub(role_id: str, phase: str, event_type: str, step: str, message: str, data: dict = None, model: str = None):
    await redis_client.publish_event(
        role_id=role_id,
        phase=phase,
        event_type=event_type,
        step=step,
        message=message,
        model=model,
        data=data or {}
    )


# ── Step 6: Persist results to SQLite ────────────────────────────────────────

async def persist_metrics(db: AsyncSession, role_id: str, final_skills: List[Dict[str, Any]]) -> None:
    """Upsert TargetSkill and TeamRelevanceSignal rows for this role (async)."""
    from sqlalchemy import delete

    await db.execute(delete(TargetSkill).where(TargetSkill.role_id == role_id))
    await db.execute(delete(TeamRelevanceSignal).where(TeamRelevanceSignal.role_id == role_id))

    for s in final_skills:
        tier    = s.get("tier", "T4")
        recency = s.get("team_recency", "none")
        name    = s.get("matched_name") or s["skill_name"]

        db.add(TargetSkill(
            role_id            = role_id,
            skill_name         = name,
            canonical_id       = s.get("canonical_id"),
            target_mastery     = s["target_mastery"],
            knowledge_category = s.get("category"),
        ))

        if recency != "none":
            db.add(TeamRelevanceSignal(
                role_id            = role_id,
                skill_name         = name,
                recency_category   = recency,
                assigned_tier      = tier,
                computed_relevance = TIER_RELEVANCE.get(tier, 0.1),
            ))

    await db.commit()
    logger.info(f"Persisted {len(final_skills)} skill metrics for role {role_id}.")


# ── Main Orchestrator ─────────────────────────────────────────────────────────

async def orchestrate_employer_flow(
    role_id: str,
    jd_bytes: bytes,
    team_bytes: bytes,
    assumed_seniority: str = "senior",
    db: Optional[AsyncSession] = None,
):
    """Full Employer Flow: extract → normalize → analyze → compute → persist."""

    # ── Phase 1A: Parse PDFs ─────────────────────────────────────────────────
    await _pub(role_id, "jd_extraction", "start", "pdf_parsing",
               "Parsing uploaded PDFs")

    jd_text   = pdf_service.extract_text(jd_bytes)
    team_text = pdf_service.extract_text(team_bytes) if team_bytes else ""

    logger.info(f"[Orchestrator] JD TEXT (first 200):\n{jd_text[:200]}")
    logger.info(f"[Orchestrator] TEAM TEXT (first 200):\n{team_text[:200]}")

    await _pub(role_id, "jd_extraction", "log", "pdf_parsed",
               "PDFs parsed successfully",
               data={
                   "jd_char_count":   len(jd_text),
                   "team_char_count": len(team_text),
                   "jd_preview":      jd_text[:200],
                   "team_preview":    team_text[:200],
               })

    # ── Phase 1B: LLM Skill Extraction ──────────────────────────────────────
    await _pub(role_id, "jd_extraction", "log", "llm_extraction_start",
               "Sending JD to LLM for skill extraction",
               model=ORCHESTRATOR_MODEL_TAG)

    jd_reasoning, raw_llm_output = await orchestrator_llm_client.stream(
        JD_EXTRACTION_PROMPT.format(jd_text=jd_text),
        temperature=1,
        max_tokens=16384,
    )
    logger.info(f"[Orchestrator] JD LLM raw content:\n{raw_llm_output}")
    logger.info(f"[Orchestrator] JD LLM reasoning (first 200):\n{jd_reasoning[:200]}")

    skills_json = json.loads(_clean_json(raw_llm_output))
    logger.info(f"LLM extracted {len(skills_json)} raw skills.")

    await _pub(role_id, "jd_extraction", "result", "llm_extraction_done",
               f"LLM extracted {len(skills_json)} raw skills",
               model=ORCHESTRATOR_MODEL_TAG,
               data={
                   "raw_count": len(skills_json),
                   "reasoning": jd_reasoning[:1000] if jd_reasoning else raw_llm_output[:500],
                   "skills":    skills_json,
               })

    # ── Phase 2: Normalize via O*NET (LLM judge + Qdrant top-3) ─────────────
    await _pub(role_id, "normalization", "start", "normalization_start",
               f"Starting O*NET normalization for {len(skills_json)} skills")

    # Pass role_id through so normalizer can publish per-skill events
    normalized_skills = await normalize_skills(skills_json, role_id=role_id)

    matched = sum(1 for s in normalized_skills if s.get("source") == "onet_match")
    coined  = sum(1 for s in normalized_skills if s.get("source") == "llm_new")
    failed  = sum(1 for s in normalized_skills if s.get("source") == "no_match")

    await _pub(role_id, "normalization", "complete", "normalization_done",
               f"{matched}/{len(normalized_skills)} skills matched to O*NET. {coined} new skill(s) coined.",
               data={
                   "matched":   matched,
                   "coined":    coined,
                   "no_match":  failed,
               })

    logger.info(f"Normalization done. {matched}/{len(normalized_skills)} matched to O*NET.")

    # ── Phase 3: Team Context Analysis ──────────────────────────────────────
    canonical_names = [s.get("matched_name") or s["skill_name"] for s in normalized_skills]
    team_signals: List[Dict] = []

    await _pub(role_id, "team_context", "start", "team_analysis_start",
               "Sending normalized skills + Team Context to LLM",
               model=ORCHESTRATOR_MODEL_TAG)

    if team_text.strip():
        team_reasoning, raw_team_output = await orchestrator_llm_client.stream(
            TEAM_CONTEXT_PROMPT.format(
                skills_list=", ".join(canonical_names), team_text=team_text
            ),
            temperature=1,
            max_tokens=16384,
        )
        logger.info(f"[Orchestrator] Team context content:\n{raw_team_output}")
        logger.info(f"[Orchestrator] Team context reasoning (first 300):\n{team_reasoning[:300]}")

        team_signals = json.loads(_clean_json(raw_team_output))

        await _pub(role_id, "team_context", "result", "team_analysis_done",
                   f"Team Context analysis complete. {len(team_signals)} skills found active in team.",
                   model=ORCHESTRATOR_MODEL_TAG,
                   data={
                       "reasoning": team_reasoning[:1500] if team_reasoning else raw_team_output[:500],
                       "signals":   team_signals,
                   })
    else:
        await _pub(role_id, "team_context", "log", "team_analysis_skipped",
                   "No Team Context document supplied. All skills defaulted to T4.")

    signal_map = {sig["skill_name"].lower(): sig["recency_category"] for sig in team_signals}

    # ── Phase 4: 2D Mastery Matrix ───────────────────────────────────────────
    sen = assumed_seniority.lower()
    if sen not in MASTERY_MATRIX:
        sen = "mid"

    final_skills: List[Dict[str, Any]] = []
    for skill in normalized_skills:
        name_key = (skill.get("matched_name") or skill["skill_name"]).lower()
        recency  = signal_map.get(name_key, "none")
        tier     = calculate_tier(recency)
        target   = MASTERY_MATRIX[sen][tier]

        final_skills.append({
            "skill_name":    skill.get("matched_name") or skill["skill_name"],
            "canonical_id":  skill.get("canonical_id"),
            "onet_level":    skill.get("onet_level"),
            "category":      skill.get("category"),
            "tier":          tier,
            "team_recency":  recency,
            "target_mastery": target,
            "reasoning":     skill.get("reasoning"),
        })

    await _pub(role_id, "mastery", "result", "mastery_matrix_done",
               f"Target mastery computed for all {len(final_skills)} skills",
               data={
                   "seniority": sen,
                   "matrix_axes": {
                       "y_axis": "Seniority Level (intern → lead)",
                       "x_axis": "Team Tier (T1=critical → T4=secondary)"
                   },
                   "matrix_values": MASTERY_MATRIX[sen],
                   "skills": final_skills,
               })

    # ── Phase 5: Persist to SQLite ───────────────────────────────────────────
    if db is not None:
        await _pub(role_id, "db", "log", "db_persist_start",
                   "Saving all skill metrics to SQLite")
        try:
            from sqlalchemy import update as sql_update
            await db.execute(
                sql_update(Role)
                .where(Role.id == role_id)
                .values(jd_text=jd_text, team_context_text=team_text, status="processing")
            )
            await db.commit()
            await persist_metrics(db, role_id, final_skills)
            await db.execute(
                sql_update(Role).where(Role.id == role_id).values(status="completed")
            )
            await db.commit()

            await _pub(role_id, "db", "complete", "db_persist_done",
                       f"Employer Flow complete. {len(final_skills)} skills saved.",
                       data={
                           "total_skills": len(final_skills),
                           "onet_matched": matched,
                           "llm_coined":   coined,
                       })
        except Exception as e:
            logger.error(f"DB persistence failed for role {role_id}: {e}")
            await db.rollback()
            await _pub(role_id, "db", "error", "db_persist_failed",
                       f"DB persistence failed: {e}")

    return final_skills
