"""
Employee Flow Orchestrator
==========================
Orchestrates the employee onboarding analysis pipeline (Phases 6–11).
Publishes events to the Redis channel:{role_id} shared with the employer flow.

Phases:
  Phase 6  — resume_extraction : PDF parse (async, non-blocking) + LLM skill extraction
  Phase 7  — normalization     : O*NET skill normalization
  Phase 8  — mastery           : LLM depth assessment (gpt-oss-20b + thinking)
  Phase 9  — gap               : Pure-math gap & priority scoring
  Phase 10 — path              : Dependency resolution (Graph+LLM) + NSGA-II course selection
  Phase 11 — journey           : Final LLM narration + visualization tree JSON

Async design note:
  PDF extraction runs in a thread-pool executor so it never blocks the event loop.
  DB saves are fire-and-forget (asyncio.ensure_future) so the LLM starts immediately.
"""
import json
import re
import asyncio
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update as sql_update, select as sql_select, delete as sql_delete

from app.services.pdf_service import pdf_service
from app.services.skill_normalizer import normalize_skills
from app.services.employee_flow.dependency_resolver import resolve_dependencies
from app.services.employee_flow.path_generator import generate_paths
from app.services.employee_flow.journey_narrator import narrate_journey
from app.clients.redis_client import redis_client
from app.clients.nvidia_llm_client import (
    resume_llm_client, mastery_llm_client,
    RESUME_MODEL, MASTERY_MODEL,
)
from app.models.domain import (
    Employee, TargetSkill, TeamRelevanceSignal, EmployeeMastery, Role,
)
from app.utils.logger import logger

# ── Mastery depth-level → deterministic score ─────────────────────────────────
DEPTH_SCORE_MAP = {
    "expert":       0.90,
    "advanced":     0.70,
    "intermediate": 0.50,
    "basic":        0.25,
    "surface":      0.10,
}

# ── Tier weights for gap priority scoring ────────────────────────────────────
TIER_WEIGHTS = {"T1": 1.0, "T2": 0.7, "T3": 0.4, "T4": 0.1}

# ─────────────────────────────────────────────────────────────────────────────
# RESUME EXTRACTION PROMPT  (qwen/qwen3.5-122b-a10b — thinking ON)
# The model streams reasoning_content (discarded) + content (JSON array).
# _clean_json() extracts the last JSON array from content, handling any CoT leak.
# ─────────────────────────────────────────────────────────────────────────────
RESUME_EXTRACTION_PROMPT = """
You are an experienced Technical Recruiter and Senior Engineering Lead performing a first-pass resume screen.
Your goal is to build a complete skills evidence dossier — not a keyword list.

# YOUR MINDSET — Think like an engineer, not a keyword scanner:
  - You care about WHAT the candidate BUILT and HOW, not just the tool names.
  - "Optimised Spark jobs reducing runtime by 60%" tells you more than "Proficient in Apache Spark".
  - Capture the actual verb + object + context: what did they DO WITH this skill?
  - Read EVERY section: Work Experience, Projects, Education, Certifications, Publications.
    Do NOT stop at the Skills section — that is often the least informative part.

# EXTRACTION RULES:
  1. Extract a MINIMUM of 15 skills, ideally 18-22. Do not stop early.
  2. Include skills from ALL resume sections — the richest context is usually in
     job bullets and project descriptions, not the skills list.
  3. For each skill, write a 'context_depth' capturing the STRONGEST and MOST SPECIFIC
     evidence from the resume. Use numbers, scale, and outcome when available.
  4. If a skill only appears in the skills/technologies section with NO supporting
     project or experience context, write: "Surface mention — listed in skills section only"
  5. Use the canonical industry name:
       PySpark (not "spark for python"), PostgreSQL (not "postgres"), Scikit-learn (not "sklearn"),
       LangChain (not "langchain framework"), FastAPI (not "fast api"), Neo4j (not "neo4j graph db")
  6. Do NOT combine multiple distinct skills into one entry.
       CORRECT:  {"skill_name": "Docker", ...}, {"skill_name": "Kubernetes", ...}
       WRONG:    {"skill_name": "Docker/Kubernetes", ...}
  7. Exclude: soft skills, methodology labels (Agile/Scrum), and non-engineering tools
     (Jira, Confluence, MS Word, PowerPoint).

# HOW TO WRITE context_depth:
  Strong evidence (led/architected/owns + measurable outcome):
    → "Architected PySpark ETL on Databricks reducing job runtime from 4h to 45min across 10TB datasets"
  Moderate evidence (built/implemented in a real project):
    → "Built REST APIs serving 500+ daily active users with JWT auth and rate limiting"
  Weak evidence (mentioned but no depth):
    → "Used within team deployments during internship; no independent project evidence"
  No project context (skills section only):
    → "Surface mention — listed in skills section only"

# WORKED EXAMPLES:

Resume bullet: "Led migration of legacy monolith to microservices using FastAPI and
Kubernetes; reduced deployment time from 2 hours to 8 minutes via GitOps CI/CD."

Correct extraction:
  [
    {"skill_name": "FastAPI",    "context_depth": "Led microservices migration from legacy monolith; built production APIs driving 94% reduction in deployment lead time."},
    {"skill_name": "Kubernetes", "context_depth": "Orchestrated microservices deployment with GitOps; reduced deployment cycle from 2h to 8min in production."},
    {"skill_name": "CI/CD",      "context_depth": "Implemented GitOps pipeline that cut deployment time from 2 hours to 8 minutes across the engineering org."}
  ]

Resume skills section: "Technologies: Python, SQL, Tableau"  (no further project context)

Correct extraction:
  [
    {"skill_name": "Python",  "context_depth": "Surface mention — listed in skills section only"},
    {"skill_name": "SQL",     "context_depth": "Surface mention — listed in skills section only"},
    {"skill_name": "Tableau", "context_depth": "Surface mention — listed in skills section only"}
  ]

Return ONLY a JSON array inside a ```json block — no additional text, no explanation:
```json
[
  {"skill_name": "<canonical skill name>", "context_depth": "<specific evidence from resume>"}
]
```

Resume Text:
{resume_text}
"""

# ─────────────────────────────────────────────────────────────────────────────
# MASTERY SCORING PROMPT  (gpt-oss-20b + thinking ON)
# ─────────────────────────────────────────────────────────────────────────────
MASTERY_SCORING_PROMPT = """
You are a Senior Technical Hiring Manager conducting a rigorous skills assessment.
Your job is to evaluate PRACTICAL DEPTH — not what the candidate claims to know,
but what the resume EVIDENCE proves they can actually DO in a production setting.

Core philosophy: A candidate who "worked with Kubernetes" but only ran kubectl get pods
is NOT the same as one who designed multi-cluster failover. Depth is everything.

# SCORING RUBRIC — Use EXACTLY these level names and score values:

  expert       → 0.90
    Signals: Led the design or architecture; owned it end-to-end; measurable production
    outcomes (latency, throughput, cost, scale numbers); mentored or drove org-wide adoption.
    Test: Could this person interview others on this skill?

  advanced     → 0.70
    Signals: Built and shipped independently in non-trivial production; handled edge
    cases, failures, and optimisation; went beyond tutorials into real trade-offs.
    Test: Would a senior engineer trust them to own a component using this skill?

  intermediate → 0.50
    Signals: Applied in real project work with moderate complexity; genuine understanding,
    not copy-paste; may have had guidance but contributed meaningfully.
    Test: Can they debug a non-obvious issue and explain their approach?

  basic        → 0.25
    Signals: Used shallowly — peripheral role, simple scripts, following tutorials,
    or completing a course project; no independent problem-solving evidence.
    Test: Would they need significant ramp-up before contributing independently?

  surface      → 0.10
    Signals: Keyword only — listed in a skills section with no usage, or mentioned
    in passing with zero context. No demonstrated use whatsoever.

# MANDATORY DOWNGRADE RULES (apply before final score):
  - "Familiar with", "exposure to", "basic knowledge of" → cap at basic (0.25)
  - "Completed a course / certification" with no project evidence → surface (0.10)
  - Listed in skills section with NO project/experience context → surface (0.10)
  - "Assisted" or "helped" with no ownership language → downgrade one level

# UPGRADE SIGNALS (raise one level if 2+ are present):
  - Hard metrics: specific numbers, percentages, throughput/latency figures
  - Ownership: "led", "designed", "architected", "owned", "built from scratch"
  - Failure/debugging/optimisation evidence
  - Cross-team or external-facing impact

# SCORED EXAMPLES:

Example 1 — Expert (0.90):
  Input:  {"skill_name": "Apache Kafka", "context_depth": "Designed and operated a
           multi-region Kafka cluster processing 15M events/day; implemented custom
           consumer-lag alerting that cut P99 latency by 40%."}
  Output: {"skill_name": "Apache Kafka", "depth_level": "expert", "current_mastery": 0.90,
           "reasoning": "Owned multi-region cluster design with measurable latency impact — architectural leadership with hard metrics."}

Example 2 — Advanced (0.70):
  Input:  {"skill_name": "FastAPI", "context_depth": "Built a production REST API with
           OAuth2 JWT auth, async background task queues, and custom exception handlers;
           deployed to AWS Lambda behind API Gateway."}
  Output: {"skill_name": "FastAPI", "depth_level": "advanced", "current_mastery": 0.70,
           "reasoning": "Independently built and shipped a production API with non-trivial auth, async patterns, and cloud deployment."}

Example 3 — Intermediate (0.50):
  Input:  {"skill_name": "PostgreSQL", "context_depth": "Wrote window functions and CTEs
           for analytics dashboards; used EXPLAIN ANALYZE to optimise slow queries for
           500+ internal stakeholders."}
  Output: {"skill_name": "PostgreSQL", "depth_level": "intermediate", "current_mastery": 0.50,
           "reasoning": "Real query optimisation with non-trivial SQL, but no evidence of schema ownership or DBA-level responsibilities."}

Example 4 — Basic (0.25):
  Input:  {"skill_name": "Docker", "context_depth": "Containerised the app and wrote
           Dockerfiles for team deployments during a university project."}
  Output: {"skill_name": "Docker", "depth_level": "basic", "current_mastery": 0.25,
           "reasoning": "Used in a guided academic context without production orchestration or multi-container evidence."}

Example 5 — Surface (0.10):
  Input:  {"skill_name": "Kubernetes", "context_depth": "Surface mention — listed in skills section only."}
  Output: {"skill_name": "Kubernetes", "depth_level": "surface", "current_mastery": 0.10,
           "reasoning": "Keyword-only listing with zero usage context."}

Example 6 — Downgrade applied:
  Input:  {"skill_name": "Apache Spark", "context_depth": "Familiar with PySpark;
           completed Databricks training badge."}
  Output: {"skill_name": "Apache Spark", "depth_level": "basic", "current_mastery": 0.25,
           "reasoning": "Self-described familiarity capped by downgrade rule; training badge with no production project evidence."}

Return ONLY a JSON array — no markdown fences, no preamble, no trailing text:
[
  {{
    "skill_name": "<exact name from input>",
    "depth_level": "expert|advanced|intermediate|basic|surface",
    "current_mastery": <float — EXACT score from rubric: 0.90 / 0.70 / 0.50 / 0.25 / 0.10>,
    "reasoning": "<1 sentence citing the specific evidence that determined the level>"
  }}
]

Skills to assess (JSON array):
{skills_with_context}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean_json(raw: str) -> str:
    """
    Extract a JSON array from an LLM response.
    Handles: clean JSON, markdown-fenced JSON, and JSON embedded in a
    reasoning trace (where the array may appear after a long CoT block).
    """
    if not raw or raw.strip().upper() == "NONE":
        return "[]"

    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        pass

    # Find the LAST JSON array — handles CoT prefix before the answer
    matches = list(re.finditer(r"\[\s*\{.*?\}\s*\]", cleaned, re.DOTALL))
    if matches:
        return matches[-1].group(0)

    return "[]"


async def _pub(
    role_id: str, phase: str, event_type: str, step: str,
    message: str, data: dict = None, model: str = None,
):
    await redis_client.publish_event(
        role_id=role_id, phase=phase, event_type=event_type,
        step=step, message=message, model=model, data=data or {},
    )


async def _db_save(db: AsyncSession, **values):
    """Fire-and-forget DB update — never blocks the main pipeline."""
    try:
        employee_id = values.pop("_employee_id")
        await db.execute(
            sql_update(Employee).where(Employee.id == employee_id).values(**values)
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"[Employee Orchestrator] Background DB save failed: {e}")


async def _save_mastery_to_db(db: AsyncSession, employee_id: str, mastery_skills: List[Dict]):
    """Persist mastery scores to EmployeeMastery (replaces existing rows)."""
    try:
        await db.execute(
            sql_delete(EmployeeMastery).where(EmployeeMastery.employee_id == employee_id)
        )
        for ss in mastery_skills:
            db.add(EmployeeMastery(
                employee_id=employee_id,
                skill_name=ss.get("skill_name", ""),
                canonical_id=ss.get("canonical_id"),
                current_mastery=ss.get("current_mastery", 0.0),
                assessment_reasoning=ss.get("reasoning", ""),
            ))
        await db.commit()
        logger.info(
            f"[Employee Orchestrator] Saved {len(mastery_skills)} mastery scores for {employee_id}"
        )
    except Exception as e:
        logger.warning(f"[Employee Orchestrator] Mastery DB save failed: {e}")


async def _fetch_target_skills(db: AsyncSession, role_id: str) -> List[Dict]:
    """Fetch the role's required skills + tier info from DB."""
    try:
        ts_result  = await db.execute(sql_select(TargetSkill).where(TargetSkill.role_id == role_id))
        sig_result = await db.execute(
            sql_select(TeamRelevanceSignal).where(TeamRelevanceSignal.role_id == role_id)
        )
        tier_map = {
            sig.skill_name.lower(): sig.assigned_tier
            for sig in sig_result.scalars().all()
        }
        return [
            {
                "skill_name":     r.skill_name,
                "canonical_id":   r.canonical_id,
                "target_mastery": r.target_mastery,
                "tier":           tier_map.get(r.skill_name.lower(), "T4"),
            }
            for r in ts_result.scalars().all()
        ]
    except Exception as e:
        logger.warning(f"[Employee Orchestrator] Target skill fetch failed: {e}")
        return []


async def _fetch_role(db: AsyncSession, role_id: str):
    """Fetch the Role ORM object for the given role_id."""
    try:
        result = await db.execute(sql_select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.warning(f"[Employee Orchestrator] Role fetch failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 8 — Mastery Scoring
# ─────────────────────────────────────────────────────────────────────────────

async def compute_mastery_scores(
    normalized_skills: List[Dict],
    role_id: str,
) -> List[Dict]:
    """
    LLM batch-scores current mastery for every normalized employee skill.
    Uses gpt-oss-20b with thinking ON — reasoning trace in reasoning_content,
    final JSON array in content (separate token budgets, no truncation risk).
    Returns list of dicts: skill_name, canonical_id, depth_level, current_mastery, reasoning.
    """
    if not normalized_skills:
        return []

    skills_payload = [
        {
            "skill_name":    s.get("matched_name") or s.get("skill_name") or s.get("raw_name", "unknown"),
            "canonical_id":  s.get("canonical_id"),
            "context_depth": s.get("context_depth") or "Surface mention — listed in skills section only",
        }
        for s in normalized_skills
    ]

    await _pub(
        role_id, "mastery", "start", "mastery_scoring_start",
        f"Scoring current mastery for {len(skills_payload)} skills via LLM",
        model=MASTERY_MODEL,
        data={
            "formula": {
                "description": "current_mastery = depth_score(context_depth_evidence)",
                "depth_scale": DEPTH_SCORE_MAP,
                "note": "LLM classifies evidence; score is deterministic from that level",
            }
        },
    )

    prompt = MASTERY_SCORING_PROMPT.replace(
        "{skills_with_context}", json.dumps(skills_payload, indent=2)
    )

    reasoning, scored_skills_raw = await mastery_llm_client.stream(
        prompt,
        temperature=0.1,
        max_tokens=24576,   # 24k — thinking trace + content use separate budgets
        role_id=role_id,
        phase="mastery",
        step_name="mastery_scoring_streaming",
    )

    try:
        scored_skills = json.loads(_clean_json(scored_skills_raw))
    except Exception as e:
        logger.error(f"[Employee Orchestrator] Failed to parse mastery JSON: {e}")
        scored_skills = [
            {
                "skill_name":     s["skill_name"],
                "depth_level":    "surface",
                "current_mastery": 0.10,
                "reasoning":      "Parse error — defaulted to surface",
            }
            for s in skills_payload
        ]

    # Merge canonical_id and clamp scores
    canonical_map = {s["skill_name"].lower(): s.get("canonical_id") for s in skills_payload}
    for ss in scored_skills:
        ss["canonical_id"]    = canonical_map.get(ss.get("skill_name", "").lower())
        ss["current_mastery"] = round(
            max(0.0, min(1.0, float(ss.get("current_mastery", 0.10)))), 2
        )

    for ss in scored_skills:
        await _pub(
            role_id, "mastery", "log", "skill_mastery_computed",
            f"Mastery '{ss['skill_name']}': {ss['current_mastery']:.2f} ({ss.get('depth_level', '?')})",
            data={
                "skill_name":      ss["skill_name"],
                "canonical_id":    ss.get("canonical_id"),
                "depth_level":     ss.get("depth_level"),
                "current_mastery": ss.get("current_mastery"),
                "reasoning":       ss.get("reasoning"),
            },
        )

    await _pub(
        role_id, "mastery", "result", "mastery_scoring_done",
        f"Current mastery computed for {len(scored_skills)} skills",
        model=MASTERY_MODEL,
        data={
            "reasoning_summary": reasoning[:600] if reasoning else "",
            "skills": scored_skills,
        },
    )

    logger.info(f"[Employee Orchestrator] Mastery scoring done — {len(scored_skills)} skills.")
    return scored_skills


# ─────────────────────────────────────────────────────────────────────────────
# Phase 9 — Gap Analysis (pure math, no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def compute_gap_analysis(
    mastery_skills: List[Dict],
    target_skills: List[Dict],
) -> List[Dict]:
    """
    gap            = max(0, target_mastery - current_mastery)
    priority_score = tier_weight × gap
    gap_category   : critical (≥0.50), moderate (0.25-0.49), minor (0.05-0.24), met (<0.05)
    Returns records sorted by priority_score descending.
    """
    if not target_skills:
        return []

    mastery_by_id   = {s.get("canonical_id", ""): s for s in mastery_skills if s.get("canonical_id")}
    mastery_by_name = {s.get("skill_name", "").lower(): s for s in mastery_skills}

    gap_records: List[Dict] = []
    for ts in target_skills:
        skill_name     = ts.get("skill_name", "")
        canonical_id   = ts.get("canonical_id")
        target_mastery = float(ts.get("target_mastery", 0.5))
        tier           = ts.get("tier", "T4")

        emp = mastery_by_id.get(canonical_id) or mastery_by_name.get(skill_name.lower())
        current_mastery = float(emp.get("current_mastery", 0.0)) if emp else 0.0

        gap            = round(max(0.0, target_mastery - current_mastery), 3)
        tier_weight    = TIER_WEIGHTS.get(tier, 0.1)
        priority_score = round(tier_weight * gap, 3)

        if gap >= 0.50:
            gap_category = "critical"
        elif gap >= 0.25:
            gap_category = "moderate"
        elif gap >= 0.05:
            gap_category = "minor"
        else:
            gap_category = "met"

        gap_records.append({
            "skill_name":           skill_name,
            "canonical_id":         canonical_id,
            "tier":                 tier,
            "target_mastery":       round(target_mastery, 2),
            "current_mastery":      round(current_mastery, 2),
            "gap":                  gap,
            "gap_category":         gap_category,
            "tier_weight":          tier_weight,
            "priority_score":       priority_score,
            "assessment_reasoning": emp.get("reasoning", "Not found in resume") if emp else "Skill absent from resume",
        })

    gap_records.sort(key=lambda x: x["priority_score"], reverse=True)
    return gap_records


async def run_gap_analysis(
    mastery_skills: List[Dict],
    target_skills: List[Dict],
    role_id: str,
) -> List[Dict]:
    """Phase 9: emits Redis events and runs compute_gap_analysis."""
    FORMULA = {
        "description":            "gap = max(0, target_mastery - current_mastery)",
        "priority_score_formula": "priority_score = tier_weight × gap",
        "tier_weights":           TIER_WEIGHTS,
        "depth_scale":            DEPTH_SCORE_MAP,
        "gap_categories": {
            "critical": "gap ≥ 0.50 — urgent training required",
            "moderate": "gap 0.25–0.49 — targeted upskilling recommended",
            "minor":    "gap 0.05–0.24 — small refinement needed",
            "met":      "gap < 0.05 — employee meets or exceeds target",
        },
    }

    await _pub(
        role_id, "gap", "start", "gap_analysis_start",
        f"Starting gap analysis: {len(mastery_skills)} employee skills vs {len(target_skills)} role targets",
        data={"formula": FORMULA},
    )

    gap_records = compute_gap_analysis(mastery_skills, target_skills)

    for g in gap_records:
        await _pub(
            role_id, "gap", "log", "skill_gap_computed",
            f"Gap '{g['skill_name']}': {g['gap']:.3f} ({g['gap_category']})  priority={g['priority_score']:.3f}",
            data=g,
        )

    critical = sum(1 for g in gap_records if g["gap_category"] == "critical")
    moderate = sum(1 for g in gap_records if g["gap_category"] == "moderate")
    minor    = sum(1 for g in gap_records if g["gap_category"] == "minor")
    met      = sum(1 for g in gap_records if g["gap_category"] == "met")

    await _pub(
        role_id, "gap", "result", "gap_analysis_done",
        f"Gap analysis complete: {critical} critical, {moderate} moderate, {minor} minor, {met} met",
        data={"ranked_gaps": gap_records, "summary": {
            "critical": critical, "moderate": moderate, "minor": minor, "met": met,
        }},
    )

    logger.info(
        f"[Employee Orchestrator] Gap analysis done — "
        f"{critical} critical, {moderate} moderate, {minor} minor, {met} met."
    )
    return gap_records


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def orchestrate_employee_flow(
    employee_id: str,
    role_id: str,
    resume_bytes: bytes,
    db: AsyncSession,
):
    """
    Full employee analysis pipeline.

    Async design:
      - PDF extraction runs in a thread-pool executor so the event loop is never
        blocked — Redis events keep flowing to the frontend during parsing.
      - Every DB write is fire-and-forget (asyncio.ensure_future) so the LLM
        starts immediately without waiting for persistence to complete.
    """

    # ── Phase 6A: Parse Resume PDF (non-blocking) ────────────────────────────
    await _pub(
        role_id, "resume_extraction", "start", "pdf_parsing",
        "Parsing uploaded Resume PDF — skill extraction will start immediately after",
    )

    loop = asyncio.get_event_loop()
    resume_text: str = await loop.run_in_executor(
        None, pdf_service.extract_text, resume_bytes
    )

    logger.info(f"[Employee Orchestrator] PDF parsed ({len(resume_text)} chars).")

    await _pub(
        role_id, "resume_extraction", "log", "pdf_parsed",
        "Resume PDF parsed successfully",
        data={"resume_char_count": len(resume_text), "resume_preview": resume_text[:200]},
    )

    # DB save fires in background — LLM starts immediately after
    asyncio.ensure_future(
        _db_save(db, _employee_id=employee_id, resume_text=resume_text, status="processing")
    )

    # ── Phase 6B: LLM Skill Extraction ──────────────────────────────────────
    await _pub(
        role_id, "resume_extraction", "log", "llm_extraction_start",
        "Sending Resume to LLM for skill and context extraction",
        model=RESUME_MODEL,
    )

    _, raw_llm_output = await resume_llm_client.stream(
        RESUME_EXTRACTION_PROMPT.replace("{resume_text}", resume_text),
        temperature=0.6,
        max_tokens=16384,
        role_id=role_id,
        phase="resume_extraction",
        step_name="llm_extraction_streaming",
    )

    try:
        skills_json = json.loads(_clean_json(raw_llm_output))
    except Exception as e:
        logger.error(f"[Employee Orchestrator] Failed to parse resume JSON: {e}")
        skills_json = []

    await _pub(
        role_id, "resume_extraction", "result", "llm_extraction_done",
        f"LLM extracted {len(skills_json)} raw skills from Resume",
        model=RESUME_MODEL,
        data={"raw_count": len(skills_json), "skills": skills_json},
    )

    asyncio.ensure_future(
        _db_save(db, _employee_id=employee_id, career_timeline=skills_json)
    )

    # ── Phase 7: O*NET Normalisation ─────────────────────────────────────────
    await _pub(
        role_id, "normalization", "start", "normalization_start",
        f"Starting O*NET normalization for {len(skills_json)} employee skills",
    )

    normalized_skills = await normalize_skills(skills_json, role_id=role_id)

    matched = sum(1 for s in normalized_skills if s.get("source") == "onet_match")
    coined  = sum(1 for s in normalized_skills if s.get("source") == "llm_new")

    await _pub(
        role_id, "normalization", "complete", "normalization_done",
        f"{matched}/{len(normalized_skills)} skills matched to O*NET. {coined} coined.",
        data={"matched": matched, "coined": coined, "total": len(normalized_skills)},
    )

    # ── Phase 8: Mastery Scoring ─────────────────────────────────────────────
    mastery_skills = await compute_mastery_scores(normalized_skills, role_id)

    asyncio.ensure_future(_save_mastery_to_db(db, employee_id, mastery_skills))

    # ── Phase 9: Gap Analysis ────────────────────────────────────────────────
    target_skills = await _fetch_target_skills(db, role_id)
    gap_records   = await run_gap_analysis(mastery_skills, target_skills, role_id)

    # ── Phase 10: Dependency Resolution + NSGA-II Path Generation ───────────
    role_obj   = await _fetch_role(db, role_id)
    role_title = role_obj.title if role_obj else "Target Role"

    dag = await resolve_dependencies(gap_records, role_id)
    path_result = await generate_paths(dag, role_id)

    # ── Phase 11: Journey Narration + Visualization Tree ─────────────────────
    journey = await narrate_journey(role_title, path_result, role_id)

    # Persist journey data (fire-and-forget so UI gets the event immediately)
    asyncio.ensure_future(
        _db_save(db, _employee_id=employee_id, learning_journey=journey, status="completed")
    )

    await _pub(
        role_id, "db", "complete", "employee_persist_done",
        "Employee analysis complete",
        data={
            "total_skills":  len(normalized_skills),
            "mastery_count": len(mastery_skills),
            "gap_summary": {
                "critical": sum(1 for g in gap_records if g["gap_category"] == "critical"),
                "moderate": sum(1 for g in gap_records if g["gap_category"] == "moderate"),
                "minor":    sum(1 for g in gap_records if g["gap_category"] == "minor"),
                "met":      sum(1 for g in gap_records if g["gap_category"] == "met"),
            },
            "learning_paths": {
                "sprint_weeks":   path_result.get("sprint_stats",   {}).get("total_weeks"),
                "balanced_weeks": path_result.get("balanced_stats", {}).get("total_weeks"),
                "quality_weeks":  path_result.get("quality_stats",  {}).get("total_weeks"),
            },
        },
    )

    return {"normalized_skills": normalized_skills, "journey": journey}

