"""
Employee Flow Orchestrator
==========================
Orchestrates the employee onboarding analysis pipeline.
Publishes its events to the same Redis channel as the employer flow (channel:{role_id})
so the UI can remain connected and watch the employee progress.

Phases:
  Phase 6 — resume_extraction: Parse PDF → LLM skill extraction
  Phase 7 — normalization: O*NET skill normalization
  (Further phases like mastery/gap/path will be added in Stage 3/5)
"""
import json
import re
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update as sql_update

from app.services.pdf_service import pdf_service
from app.services.skill_normalizer import normalize_skills
from app.clients.redis_client import redis_client
from app.clients.nvidia_llm_client import orchestrator_llm_client, ORCHESTRATOR_MODEL
from app.models.domain import Employee
from app.utils.logger import logger

RESUME_EXTRACTION_PROMPT = """
You are an expert Technical Skills Extractor. Your task is to extract skill evidence from the following Resume.

For each technical skill the candidate possesses, extract:
1. 'skill_name': The raw skill name (e.g., 'PySpark').
2. 'context_depth': A short phrase detailing exactly HOW they used the skill based on the resume. If no context is provided, return 'Surface mention'.

Return strictly a JSON array inside a ```json block. Do not include any conversational text.
Example:
```json
[
  {"skill_name": "Python", "context_depth": "Built backend APIs using FastAPI"}
]
```

Resume Text:
{resume_text}
"""


def _clean_json(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


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


async def orchestrate_employee_flow(
    employee_id: str,
    role_id: str,
    resume_bytes: bytes,
    db: AsyncSession,
):
    """Stage 2: Extracts resume skills and normalizes them."""
    
    # ── Phase 6A: Parse Resume PDF ───────────────────────────────────────────
    await _pub(role_id, "resume_extraction", "start", "pdf_parsing",
               "Parsing uploaded Resume PDF for employee")

    resume_text = pdf_service.extract_text(resume_bytes)

    logger.info(f"[Employee Orchestrator] RESUME TEXT (first 200):\n{resume_text[:200]}")

    await _pub(role_id, "resume_extraction", "log", "pdf_parsed",
               "Resume PDF parsed successfully",
               data={
                   "resume_char_count": len(resume_text),
                   "resume_preview": resume_text[:200],
               })

    # Save raw resume text quickly to DB
    await db.execute(sql_update(Employee).where(Employee.id == employee_id).values(resume_text=resume_text, status="processing"))
    await db.commit()

    # ── Phase 6B: LLM Skill Extraction ──────────────────────────────────────
    await _pub(role_id, "resume_extraction", "log", "llm_extraction_start",
               "Sending Resume to LLM for skill and context extraction",
               model=ORCHESTRATOR_MODEL)

    resume_reasoning, raw_llm_output = await orchestrator_llm_client.stream(
        RESUME_EXTRACTION_PROMPT.format(resume_text=resume_text),
        temperature=0.3,
        max_tokens=8192,
        role_id=role_id,
        phase="resume_extraction",
        step_name="llm_extraction_streaming"
    )
    
    logger.info(f"[Employee Orchestrator] Resume LLM raw content:\n{raw_llm_output}")

    try:
        skills_json = json.loads(_clean_json(raw_llm_output))
    except Exception as e:
        logger.error(f"Failed to parse resume JSON: {e}")
        skills_json = []

    await _pub(role_id, "resume_extraction", "result", "llm_extraction_done",
               f"LLM extracted {len(skills_json)} raw skills from Resume",
               model=ORCHESTRATOR_MODEL,
               data={
                   "raw_count": len(skills_json),
                   "reasoning": resume_reasoning[:1000] if resume_reasoning else raw_llm_output[:500],
                   "skills": skills_json,
               })

    # Save career timeline (parsed JSON) to DB
    await db.execute(sql_update(Employee).where(Employee.id == employee_id).values(career_timeline=skills_json))
    await db.commit()

    # ── Phase 7: Normalize via O*NET ─────────────────────────────────────────
    # We reuse the exact same normalization pipeline and redis channel (role_id)
    await _pub(role_id, "normalization", "start", "normalization_start",
               f"Starting O*NET normalization for employee's {len(skills_json)} skills")

    normalized_skills = await normalize_skills(skills_json, role_id=role_id)

    matched = sum(1 for s in normalized_skills if s.get("source") == "onet_match")
    coined  = sum(1 for s in normalized_skills if s.get("source") == "llm_new")

    await _pub(role_id, "normalization", "complete", "normalization_done",
               f"{matched}/{len(normalized_skills)} employee skills matched to O*NET. {coined} coined.",
               data={
                   "matched": matched,
                   "coined": coined,
               })

    logger.info(f"Employee Normalization complete. {matched}/{len(normalized_skills)} matched to O*NET.")

    # Finally, mark employee complete (for Stage 2 framework)
    await db.execute(sql_update(Employee).where(Employee.id == employee_id).values(status="completed"))
    await db.commit()

    await _pub(role_id, "db", "complete", "employee_persist_done",
               "Employee resume parsing complete.",
               data={"total_skills": len(normalized_skills)})
    
    return normalized_skills
