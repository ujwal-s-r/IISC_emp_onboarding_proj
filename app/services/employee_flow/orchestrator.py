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
import asyncio
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update as sql_update

from app.services.pdf_service import pdf_service
from app.services.skill_normalizer import normalize_skills
from app.clients.redis_client import redis_client
from app.clients.nvidia_llm_client import resume_llm_client, RESUME_MODEL
from app.models.domain import Employee
from app.utils.logger import logger

RESUME_EXTRACTION_PROMPT = """
You are an expert Technical Skills Extractor. Your task is to extract skill evidence from the following Resume.

Focus on the 20-25 most mainstream, industry-recognised technical skills only.
Ignore soft skills, generic concepts, and minor or one-off mentions.

For each skill, extract:
1. 'skill_name': The canonical skill name (e.g., 'PySpark', 'FastAPI', 'Docker').
2. 'context_depth': A short phrase detailing exactly HOW they used the skill. If no context is provided, return 'Surface mention'.

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
    """
    Extract a JSON array from an LLM response.
    Handles: clean JSON, markdown-fenced JSON, and JSON embedded in a
    reasoning trace (where the array may appear after a long CoT block).
    """
    if not raw or raw.strip().upper() == "NONE":
        return "[]"

    # 1. Strip outermost markdown fences
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # 2. Try to parse directly
    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        pass

    # 3. Find the LAST JSON array in the text (handles CoT prefix before answer)
    matches = list(re.finditer(r"\[\s*\{.*?\}\s*\]", cleaned, re.DOTALL))
    if matches:
        return matches[-1].group(0)

    return "[]"


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


async def _db_save(db: AsyncSession, **values):
    """Fire-and-forget helper: run a DB update without blocking the main pipeline."""
    try:
        employee_id = values.pop("_employee_id")
        await db.execute(sql_update(Employee).where(Employee.id == employee_id).values(**values))
        await db.commit()
    except Exception as e:
        logger.warning(f"[Employee Orchestrator] Background DB save failed: {e}")


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

    # ── Fire DB save in background — do NOT await before starting LLM ────────
    # Status update runs concurrently; LLM stream starts immediately.
    asyncio.ensure_future(_db_save(db, _employee_id=employee_id,
                                   resume_text=resume_text, status="processing"))

    # ── Phase 6B: LLM Skill Extraction ──────────────────────────────────────
    await _pub(role_id, "resume_extraction", "log", "llm_extraction_start",
               "Sending Resume to LLM for skill and context extraction",
               model=RESUME_MODEL)

    resume_reasoning, raw_llm_output = await resume_llm_client.stream(
        RESUME_EXTRACTION_PROMPT.replace("{resume_text}", resume_text),
        temperature=0.3,
        max_tokens=16384,
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
               model=RESUME_MODEL,
               data={
                   "raw_count": len(skills_json),
                   "reasoning": resume_reasoning[:1000] if resume_reasoning else raw_llm_output[:500],
                   "skills": skills_json,
               })

    # ── Fire career_timeline DB save in background — normalization starts now ─
    asyncio.ensure_future(_db_save(db, _employee_id=employee_id, career_timeline=skills_json))

    # ── Phase 7: Normalize via O*NET ─────────────────────────────────────────
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

    # ── Final status update — await this one so status is correct at close ────
    await _db_save(db, _employee_id=employee_id, status="completed")

    await _pub(role_id, "db", "complete", "employee_persist_done",
               "Employee resume parsing complete.",
               data={"total_skills": len(normalized_skills)})

    return normalized_skills
