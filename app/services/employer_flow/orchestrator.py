"""
Employer Flow Orchestrator
==========================
Orchestrates the full employer analysis pipeline:
  1. Parse PDFs
  2. LLM → raw skills from JD
  3. Skill Normalization via O*NET backbone (Qdrant -> Neo4j)
  4. Team Context analysis
  5. 2D Mastery Matrix computation
  6. Persist all metrics to SQLite (async)
"""
import json
import re
from typing import List, Dict, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_creator import agent_creator
from app.services.pdf_service import pdf_service
from app.api.routers.websocket import manager
from app.clients.vector_client import vector_client
from app.clients.graph_client import graph_client
from app.clients.embedding_client import embedding_client
from app.models.domain import Role, TargetSkill, TeamRelevanceSignal
from app.utils.logger import logger

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

Output MUST be a valid JSON array of objects with keys: "skill_name", "recency_category".
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


# ── Step 3: Normalize skills via O*NET backbone ───────────────────────────────

def normalize_skills(raw_skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Embeds each skill name and searches Qdrant for the closest O*NET entry.
    Falls back to the raw LLM name if no confident match is found.
    """
    normalized: List[Dict[str, Any]] = []

    for skill in raw_skills:
        raw_name = skill["skill_name"]
        result = dict(skill)
        result["canonical_id"] = None
        result["onet_level"]   = None
        result["matched_name"] = raw_name

        try:
            vec  = embedding_client.embed_query(raw_name)
            hits = vector_client.client.search(
                collection_name=ONET_COLLECTION,
                query_vector=vec,
                limit=1,
                score_threshold=NORMALIZATION_THRESHOLD,
            )

            if hits:
                top     = hits[0]
                payload = top.payload or {}
                cid     = payload.get("canonical_id")
                mname   = payload.get("name", raw_name)

                result["canonical_id"] = cid
                result["matched_name"] = mname
                logger.info(f"'{raw_name}' -> '{mname}' [{cid}] (score={top.score:.3f})")

                # Enrich with O*NET Level from Neo4j (sync driver call – fine in background)
                if cid:
                    with graph_client.driver.session() as session:
                        rec = session.run(
                            """
                            MATCH ()-[r:REQUIRES_SKILL]->(sk {canonical_id: $cid})
                            RETURN avg(r.level) AS avg_level
                            """,
                            cid=cid,
                        ).single()
                        if rec and rec["avg_level"] is not None:
                            result["onet_level"] = round(rec["avg_level"], 2)
            else:
                logger.info(f"No O*NET match for '{raw_name}' – keeping raw name.")

        except Exception as e:
            logger.warning(f"Normalization error for '{raw_name}': {e}")

        normalized.append(result)

    return normalized


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

    # ── 1: Parse PDFs ────────────────────────────────────────────────────────
    await manager.broadcast_to_session(role_id, {
        "step": "pdf_processing", "status": "in_progress",
        "message": "Parsing PDFs…"
    })
    jd_text   = pdf_service.extract_text(jd_bytes)
    team_text = pdf_service.extract_text(team_bytes) if team_bytes else ""

    # ── 2: LLM Extraction (JD) ───────────────────────────────────────────────
    await manager.broadcast_to_session(role_id, {
        "step": "jd_extraction", "status": "in_progress",
        "message": "Extracting skill requirements from JD…"
    })
    llm         = agent_creator.get_llm()
    jd_resp     = await llm.ainvoke(JD_EXTRACTION_PROMPT.format(jd_text=jd_text))
    skills_json = json.loads(_clean_json(jd_resp.content))
    logger.info(f"LLM extracted {len(skills_json)} raw skills.")

    # ── 3: Normalize via O*NET ───────────────────────────────────────────────
    await manager.broadcast_to_session(role_id, {
        "step": "normalization", "status": "in_progress",
        "message": f"Normalizing {len(skills_json)} skills against O*NET backbone…"
    })
    normalized_skills = normalize_skills(skills_json)
    matched = sum(1 for s in normalized_skills if s.get("canonical_id"))
    logger.info(f"Normalization done. {matched}/{len(normalized_skills)} matched to O*NET.")

    # ── 4: Team Context Analysis ─────────────────────────────────────────────
    await manager.broadcast_to_session(role_id, {
        "step": "team_analysis", "status": "in_progress",
        "message": "Analyzing Team Context for skill relevance…"
    })
    canonical_names = [s.get("matched_name") or s["skill_name"] for s in normalized_skills]
    team_signals: List[Dict] = []

    if team_text.strip():
        team_resp    = await llm.ainvoke(TEAM_CONTEXT_PROMPT.format(
            skills_list=", ".join(canonical_names), team_text=team_text
        ))
        team_signals = json.loads(_clean_json(team_resp.content))

    signal_map = {sig["skill_name"].lower(): sig["recency_category"] for sig in team_signals}

    # ── 5: 2D Mastery Matrix ─────────────────────────────────────────────────
    await manager.broadcast_to_session(role_id, {
        "step": "mastery_computation", "status": "in_progress",
        "message": "Computing target masteries via 2D matrix…"
    })
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
            "skill_name":   skill.get("matched_name") or skill["skill_name"],
            "canonical_id": skill.get("canonical_id"),
            "onet_level":   skill.get("onet_level"),
            "category":     skill.get("category"),
            "tier":         tier,
            "team_recency": recency,
            "target_mastery": target,
            "reasoning":    skill.get("reasoning"),
        })

    # ── 6: Persist to SQLite ─────────────────────────────────────────────────
    if db is not None:
        await manager.broadcast_to_session(role_id, {
            "step": "db_persistence", "status": "in_progress",
            "message": "Saving skill metrics to database…"
        })
        try:
            from sqlalchemy import update as sql_update
            # Update role fields
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
        except Exception as e:
            logger.error(f"DB persistence failed for role {role_id}: {e}")
            await db.rollback()
            await manager.broadcast_to_session(role_id, {
                "step": "db_persistence", "status": "failed",
                "message": f"DB save failed: {e}"
            })

    # ── Complete ──────────────────────────────────────────────────────────────
    await manager.broadcast_to_session(role_id, {
        "step": "completed", "status": "completed",
        "message": "Employer Flow complete.",
        "data": {"skills": final_skills}
    })
    return final_skills
