"""
path_generator.py
=================
Phase 10 — Step B: For each ordered gap stage, retrieve candidate courses from
Qdrant, run NSGA-II (4-objective Pareto optimisation), and package the three
representative learning paths: Sprint, Balanced, Quality.

NSGA-II Objectives (all minimised, all normalised to [0, 1]):
  f1 = 1 - cosine_similarity       → maximise relevance
  f2 = duration_score / 4          → minimise time-to-complete
  f3 = 1 - popularity_norm         → maximise course quality / trust
  f4 = |course_level - req_level| / 2  → minimise difficulty mismatch

No hard constraints — all four objectives are soft, weighed by the Pareto front.

Output per gap (in each stage):
  {
    "sprint":   { ...course payload + scores },
    "balanced": { ...course payload + scores },
    "quality":  { ...course payload + scores },
  }

Full path output (3 complete paths, one per track):
  Each path = ordered list of stages, each stage = one chosen course per gap.
"""

import math
from typing import Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.config import settings
from app.clients.nvidia_llm_client import nvidia_embedding_client
from app.clients.redis_client import redis_client
from app.utils.logger import logger

COLLECTION_NAME = "courses_listed"
TOP_K_CANDIDATES = 30          # Candidates per gap fed into NSGA-II
NSGA_GENERATIONS = 40          # Number of NSGA-II iterations
POPULATION_SIZE  = 30          # Equals TOP_K (we optimise over the candidate set)

# ── Module-level Qdrant singleton ──────────────────────────────────────────
# check_compatibility=False suppresses the 'Failed to obtain server version'
# UserWarning that fires when the client cannot reach the server on init.
# Connection errors (including bad URLs / IDNA failures) are caught per-skill
# in generate_paths() so a misconfigured URL degrades gracefully instead of
# crashing the entire orchestrator.
_qdrant_courses = QdrantClient(
    url=settings.QDRANT_COURSES_URL,
    api_key=settings.QDRANT_COURSES_API_KEY,
    check_compatibility=False,
)
logger.info(f"[PathGenerator] Qdrant courses client → {settings.QDRANT_COURSES_URL}")


# ── Level mapping: derive required level from target_mastery ─────────────────
def _mastery_to_level(target_mastery: float) -> int:
    if target_mastery >= 0.70:
        return 3   # Advanced
    if target_mastery >= 0.40:
        return 2   # Intermediate
    return 1       # Beginner


# ── Objective function ────────────────────────────────────────────────────────
def _objectives(
    cosine_sim: float,
    duration_score: int,
    popularity_norm: float,
    level_score: int,
    required_level: int,
) -> Tuple[float, float, float, float]:
    """
    Returns (f1, f2, f3, f4) — all in [0, 1], all to be minimised.
    """
    f1 = 1.0 - max(0.0, min(1.0, cosine_sim))        # relevance
    f2 = (duration_score - 1) / 3.0                   # speed (1→0, 4→1)
    f3 = 1.0 - max(0.0, min(1.0, popularity_norm))    # quality / trust
    f4 = abs(level_score - required_level) / 2.0      # difficulty match (max diff=2)
    return f1, f2, f3, f4


# ── NSGA-II core ──────────────────────────────────────────────────────────────
def _dominates(a: Tuple, b: Tuple) -> bool:
    """Return True if solution a dominates solution b (a ≤ b on all, a < b on at least one)."""
    return all(ai <= bi for ai, bi in zip(a, b)) and any(ai < bi for ai, bi in zip(a, b))


def _pareto_front(solutions: List[Dict]) -> List[Dict]:
    """Extract the Pareto-non-dominated front from a list of solutions (each has 'objectives')."""
    front = []
    for s in solutions:
        dominated = False
        for other in solutions:
            if other is s:
                continue
            if _dominates(other["objectives"], s["objectives"]):
                dominated = True
                break
        if not dominated:
            front.append(s)
    return front


def _crowding_distance(front: List[Dict]) -> List[Dict]:
    """Assign crowding distance to each solution in a Pareto front."""
    n = len(front)
    if n <= 2:
        for s in front:
            s["crowding"] = float("inf")
        return front

    for s in front:
        s["crowding"] = 0.0

    n_obj = len(front[0]["objectives"])
    for i in range(n_obj):
        front.sort(key=lambda s: s["objectives"][i])
        f_min = front[0]["objectives"][i]
        f_max = front[-1]["objectives"][i]
        front[0]["crowding"]  = float("inf")
        front[-1]["crowding"] = float("inf")
        rng = f_max - f_min if f_max != f_min else 1e-9
        for j in range(1, n - 1):
            front[j]["crowding"] += (
                front[j + 1]["objectives"][i] - front[j - 1]["objectives"][i]
            ) / rng

    return front


def _run_nsga2(candidates: List[Dict], required_level: int) -> List[Dict]:
    """
    Run NSGA-II over the candidate course list.
    Each candidate must have keys: cosine_sim, duration_score, popularity_norm, level_score.
    Returns the Pareto front sorted by crowding distance (desc).
    """
    # Build solution objects
    solutions = []
    for c in candidates:
        obj = _objectives(
            cosine_sim=c.get("cosine_sim", 0.5),
            duration_score=c.get("duration_score", 2),
            popularity_norm=c.get("popularity_norm", 0.5),
            level_score=c.get("level_score", 1),
            required_level=required_level,
        )
        solutions.append({**c, "objectives": obj, "crowding": 0.0})

    # NSGA-II with a fixed population (the entire candidate set)
    # Since we have ≤30 candidates, the "algorithm" is: compute Pareto + crowding.
    # We iterate NSGA_GENERATIONS times to allow virtual tournament selection
    # on the objectives (rank-based secondary sort simulates selection pressure).
    for _ in range(NSGA_GENERATIONS):
        front    = _pareto_front(solutions)
        front    = _crowding_distance(front)
        # Non-front members: sort by sum of objectives (proxy for fitness)
        non_front = [s for s in solutions if s not in front]
        non_front.sort(key=lambda s: sum(s["objectives"]))
        solutions = front + non_front

    # Final Pareto front + crowding distance
    final_front = _pareto_front(solutions)
    final_front = _crowding_distance(final_front)
    final_front.sort(key=lambda s: -s["crowding"])  # highest crowding first (most spread)
    return final_front


def _pick_three(pareto_front: List[Dict]) -> Dict:
    """
    From the Pareto front pick three representative courses:
      sprint   — lowest f2 (fastest)
      quality  — lowest f1 (most relevant)
      balanced — lowest sum(f1+f2+f3+f4) — closest to origin
    """
    if not pareto_front:
        return {"sprint": None, "balanced": None, "quality": None}

    sprint   = min(pareto_front, key=lambda s: s["objectives"][1])        # f2
    quality  = min(pareto_front, key=lambda s: s["objectives"][0])        # f1
    balanced = min(pareto_front, key=lambda s: sum(s["objectives"]))      # all

    return {
        "sprint":   _format_pick(sprint,   "sprint"),
        "balanced": _format_pick(balanced, "balanced"),
        "quality":  _format_pick(quality,  "quality"),
    }


def _format_pick(solution: Dict, track: str) -> Dict:
    obj = solution["objectives"]
    return {
        "track":            track,
        "title":            solution.get("title", ""),
        "institution":      solution.get("institution", ""),
        "subject":          solution.get("subject", ""),
        "learning_product": solution.get("learning_product", ""),
        "level":            solution.get("level", ""),
        "level_score":      solution.get("level_score", 1),
        "duration_label":   solution.get("duration_label", ""),
        "duration_score":   solution.get("duration_score", 2),
        "duration_weeks":   solution.get("duration_weeks", 2.5),
        "rate":             solution.get("rate", 0.0),
        "reviews":          solution.get("reviews", 0),
        "popularity_norm":  solution.get("popularity_norm", 0.0),
        "skills":           solution.get("skills", []),
        "cosine_sim":       round(solution.get("cosine_sim", 0.0), 4),
        "obj_f1_relevance": round(obj[0], 4),
        "obj_f2_speed":     round(obj[1], 4),
        "obj_f3_quality":   round(obj[2], 4),
        "obj_f4_level_match": round(obj[3], 4),
        "pareto_score":     round(sum(obj), 4),
    }


# ── Qdrant vector search ──────────────────────────────────────────────────────
def _search_courses(
    qdrant: QdrantClient,
    query_vector: List[float],
    top_k: int = TOP_K_CANDIDATES,
) -> List[Dict]:
    """
    Search the `courses` collection.
    Returns a flat list of payload dicts enriched with cosine_sim.
    """
    response = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
        score_threshold=0.30,   # Ignore very low-relevance courses
    )
    candidates = []
    for r in response.points:
        pay = r.payload or {}
        candidates.append({
            **pay,
            "cosine_sim": round(float(r.score), 4),
        })
    return candidates


# ── Public entry point ────────────────────────────────────────────────────────
async def generate_paths(
    dag: Dict,
    role_id: str,
) -> Dict:
    """
    Main entry point called from orchestrator.py Phase 10.

    dag: output of dependency_resolver.resolve_dependencies()
         Must have keys: stages (list), dependency_edges (list)

    Returns:
    {
      "sprint_path":   [{"stage": 1, "skill": ..., "course": {...}}, ...],
      "balanced_path": [...],
      "quality_path":  [...],
      "gap_options":   {skill_name: {"sprint": ..., "balanced": ..., "quality": ...}},
      "dependency_edges": [...],
    }
    """
    stages = dag.get("stages", [])
    if not stages:
        logger.warning("[PathGenerator] DAG has no stages — skipping path generation.")
        return {"sprint_path": [], "balanced_path": [], "quality_path": [], "gap_options": {}, "dependency_edges": []}

    await redis_client.publish_event(
        role_id=role_id,
        phase="path",
        event_type="start",
        step="nsga_start",
        message=f"Starting NSGA-II course selection across {len(stages)} stage(s)",
        data={"total_stages": len(stages), "algorithm": "NSGA-II 4-objective Pareto"},
    )

    gap_options: Dict[str, Dict] = {}

    for stage in stages:
        stage_num    = stage["stage"]
        skill_details = stage.get("skill_details", [])

        for skill_info in skill_details:
            skill_name      = skill_info.get("skill_name", "")
            target_mastery  = float(skill_info.get("target_mastery", 0.5))
            gap_category    = skill_info.get("gap_category", "moderate")
            required_level  = _mastery_to_level(target_mastery)

            logger.info(f"[PathGenerator] Stage {stage_num} | skill='{skill_name}' | target_level={required_level}")

            # Embed the gap query
            try:
                query_vec = nvidia_embedding_client.embed_query(skill_name)
            except Exception as e:
                logger.warning(f"[PathGenerator] Embedding failed for '{skill_name}': {e}")
                gap_options[skill_name] = {"sprint": None, "balanced": None, "quality": None}
                continue

            # Search Qdrant
            try:
                candidates = _search_courses(_qdrant_courses, query_vec)
            except Exception as e:
                logger.warning(f"[PathGenerator] Qdrant search failed for '{skill_name}': {e}")
                await redis_client.publish_event(
                    role_id=role_id, phase="path", event_type="log",
                    step="nsga_gap_done",
                    message=f"Course search failed for '{skill_name}' — skipping",
                    data={"skill": skill_name, "error": str(e)},
                )
                gap_options[skill_name] = {"sprint": None, "balanced": None, "quality": None}
                continue

            if not candidates:
                logger.warning(f"[PathGenerator] No candidates found for '{skill_name}'")
                gap_options[skill_name] = {"sprint": None, "balanced": None, "quality": None}
                continue

            # Run NSGA-II
            pareto_front = _run_nsga2(candidates, required_level)
            options      = _pick_three(pareto_front)
            gap_options[skill_name] = options

            await redis_client.publish_event(
                role_id=role_id,
                phase="path",
                event_type="progress",
                step="nsga_gap_done",
                message=f"Stage {stage_num}: courses selected for '{skill_name}'",
                data={
                    "stage":          stage_num,
                    "skill":          skill_name,
                    "gap_category":   gap_category,
                    "required_level": required_level,
                    "candidates":     len(candidates),
                    "pareto_front":   len(pareto_front),
                    "sprint_title":   options["sprint"]["title"]   if options["sprint"]   else None,
                    "balanced_title": options["balanced"]["title"] if options["balanced"] else None,
                    "quality_title":  options["quality"]["title"]  if options["quality"]  else None,
                },
            )

    # ── Assemble the 3 full paths ─────────────────────────────────────────────
    sprint_path   = []
    balanced_path = []
    quality_path  = []

    for stage in stages:
        for skill_info in stage.get("skill_details", []):
            skill_name  = skill_info.get("skill_name", "")
            options     = gap_options.get(skill_name, {})
            base_entry  = {
                "stage":        stage["stage"],
                "skill":        skill_name,
                "gap_category": skill_info.get("gap_category", "moderate"),
                "target_mastery": skill_info.get("target_mastery", 0.5),
                "current_mastery": skill_info.get("current_mastery", 0.0),
            }
            sprint_path.append({  **base_entry, "course": options.get("sprint")   })
            balanced_path.append({**base_entry, "course": options.get("balanced") })
            quality_path.append({ **base_entry, "course": options.get("quality")  })

    # Path summary stats
    def _path_stats(path):
        weeks = sum(
            (e["course"]["duration_weeks"] if e["course"] else 0)
            for e in path
        )
        sims  = [e["course"]["cosine_sim"] for e in path if e["course"]]
        coverage = round(sum(sims) / len(sims), 3) if sims else 0.0
        return {"total_weeks": round(weeks, 1), "coverage_score": coverage}

    sprint_stats   = _path_stats(sprint_path)
    balanced_stats = _path_stats(balanced_path)
    quality_stats  = _path_stats(quality_path)

    await redis_client.publish_event(
        role_id=role_id,
        phase="path",
        event_type="result",
        step="paths_ready",
        message="All 3 learning paths generated",
        data={
            "sprint":   sprint_stats,
            "balanced": balanced_stats,
            "quality":  quality_stats,
            "total_skills_planned": len(gap_options),
        },
    )

    return {
        "sprint_path":       sprint_path,
        "balanced_path":     balanced_path,
        "quality_path":      quality_path,
        "sprint_stats":      sprint_stats,
        "balanced_stats":    balanced_stats,
        "quality_stats":     quality_stats,
        "gap_options":       gap_options,
        "dependency_edges":  dag.get("dependency_edges", []),
    }
