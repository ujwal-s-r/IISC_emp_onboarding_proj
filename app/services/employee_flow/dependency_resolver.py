"""
dependency_resolver.py
======================
Phase 10 — Step A: Sequence skill gaps into a topologically ordered DAG.

Pipeline:
  1. Query Neo4j for known skill relationships (REQUIRES / BUILDS_ON edges).
  2. Feed the gap list + graph adjacency data to gpt-oss-20b (thinking ON).
     The LLM reasons through prerequisite ordering and outputs a clean JSON DAG.
  3. Emit Redis events so the frontend can show "Building your learning plan..."
     progress during the LLM call.

Output schema:
  {
    "stages": [
      {"stage": 1, "skills": ["Python", "Statistics"], "rationale": "..."},
      {"stage": 2, "skills": ["PySpark", "Docker"],    "rationale": "..."},
      {"stage": 3, "skills": ["Kubernetes", "Kafka"],  "rationale": "..."}
    ],
    "dependency_edges": [
      {"from": "Python", "to": "PySpark",     "type": "PREREQUISITE"},
      {"from": "Docker",  "to": "Kubernetes", "type": "PREREQUISITE"}
    ]
  }
"""

import json
import re
from typing import Dict, List, Optional

from app.clients.graph_client import graph_client
from app.clients.nvidia_llm_client import dependency_llm_client
from app.clients.redis_client import redis_client
from app.utils.logger import logger

# ── Cypher: pull direct prerequisite / builds-on edges for a skill ─────────
_CYPHER_DEPS = """
MATCH (s:Skill)-[r:REQUIRES|BUILDS_ON|LEADS_TO]->(dep:Skill)
WHERE s.name IN $skill_names
RETURN s.name AS source, dep.name AS target, type(r) AS rel_type
LIMIT 100
"""

# ── Few-shot prompt ────────────────────────────────────────────────────────────
_DEPENDENCY_PROMPT = """You are an expert learning-path architect with deep knowledge of technology skill prerequisites.

Given a list of SKILL GAPS (skills the employee needs to improve) and an ADJACENCY LIST (known dependency edges from our knowledge graph), your job is to:
1. Determine the correct learning ORDER — which skills must be learned first (prerequisites) before others can be tackled.
2. Group skills into STAGES (1 = foundational, higher = advanced).
3. Add any OBVIOUS prerequisite edges that the knowledge graph may have missed, based on your expert knowledge.
4. Output ONLY a valid JSON object — no markdown, no explanation outside the JSON.

RULES:
- A skill can only appear in ONE stage.
- A skill in stage N can depend on skills in stages 1..N-1 only.
- Skills with NO dependencies go in stage 1.
- If two skills are independent, they can share the same stage.
- "rationale" must be one concise sentence per stage.

---
EXAMPLE 1

Input gaps: ["Kubernetes", "Python", "Docker", "Statistics", "Machine Learning"]
Input edges: [{{"from": "Docker", "to": "Kubernetes"}}, {{"from": "Python", "to": "Machine Learning"}}, {{"from": "Statistics", "to": "Machine Learning"}}]

Output:
{{
  "stages": [
    {{"stage": 1, "skills": ["Python", "Statistics", "Docker"], "rationale": "No prerequisites — all are standalone foundational skills."}},
    {{"stage": 2, "skills": ["Machine Learning", "Kubernetes"], "rationale": "Machine Learning requires Python & Statistics; Kubernetes requires Docker."}}
  ],
  "dependency_edges": [
    {{"from": "Python",     "to": "Machine Learning", "type": "PREREQUISITE"}},
    {{"from": "Statistics", "to": "Machine Learning", "type": "PREREQUISITE"}},
    {{"from": "Docker",     "to": "Kubernetes",        "type": "PREREQUISITE"}}
  ]
}}

---
EXAMPLE 2

Input gaps: ["Apache Kafka", "Distributed Systems", "PySpark", "Python", "SQL"]
Input edges: [{{"from": "Python", "to": "PySpark"}}, {{"from": "Distributed Systems", "to": "Apache Kafka"}}]

Output:
{{
  "stages": [
    {{"stage": 1, "skills": ["Python", "SQL"], "rationale": "Foundational languages with no cross-dependencies among the gaps."}},
    {{"stage": 2, "skills": ["PySpark", "Distributed Systems"], "rationale": "PySpark builds on Python; Distributed Systems is a conceptual prerequisite for Kafka."}},
    {{"stage": 3, "skills": ["Apache Kafka"], "rationale": "Requires both Distributed Systems understanding and PySpark/streaming context."}}
  ],
  "dependency_edges": [
    {{"from": "Python",               "to": "PySpark",        "type": "PREREQUISITE"}},
    {{"from": "Distributed Systems",  "to": "Apache Kafka",   "type": "PREREQUISITE"}},
    {{"from": "PySpark",              "to": "Apache Kafka",   "type": "BUILDS_ON"}}
  ]
}}

---
NOW YOUR TURN

Input gaps: {gaps_json}
Input edges (from knowledge graph): {edges_json}

Think carefully about the dependencies. Consider ALL standard technology prerequisites even if they are not listed in the edges above.
Output ONLY the JSON object:"""


def _query_graph_edges(skill_names: List[str]) -> List[Dict]:
    """Query Neo4j for relationships between the given skill names."""
    edges = []
    try:
        with graph_client.driver.session(database="neo4j") as session:
            result = session.run(_CYPHER_DEPS, skill_names=skill_names)
            for record in result:
                edges.append({
                    "from":     record["source"],
                    "to":       record["target"],
                    "rel_type": record["rel_type"],
                })
        logger.info(f"[DependencyResolver] Graph returned {len(edges)} edges for {len(skill_names)} skills.")
    except Exception as e:
        logger.warning(f"[DependencyResolver] Neo4j query failed (continuing without graph data): {e}")
    return edges


def _parse_dag(raw: str) -> Optional[Dict]:
    """Extract and parse the JSON DAG from the LLM response."""
    # Strip markdown fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        dag = json.loads(raw)
        if "stages" in dag and "dependency_edges" in dag:
            return dag
    except json.JSONDecodeError:
        pass
    # Try extracting the first {...} block
    match = re.search(r"\{[\s\S]+\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


async def resolve_dependencies(
    gap_records: List[Dict],
    role_id: str,
) -> Dict:
    """
    Main entry point.
    gap_records: output of compute_gap_analysis() — list of dicts with
                 keys: skill_name, gap_category, target_mastery, current_mastery, etc.
    Returns a DAG dict with keys: stages, dependency_edges.
    On failure, returns a trivial single-stage fallback.
    """
    # Only act on critical + moderate gaps (minor/met don't need path planning)
    actionable = [
        g for g in gap_records
        if g.get("gap_category") in ("critical", "moderate")
    ]
    skill_names = [g["skill_name"] for g in actionable]

    if not skill_names:
        logger.info("[DependencyResolver] No actionable gaps — returning empty DAG.")
        return {"stages": [], "dependency_edges": []}

    # ── Event: start ────────────────────────────────────────────────────────
    await redis_client.publish_event(
        role_id=role_id,
        phase="dependency",
        event_type="start",
        step="dep_resolution_start",
        message=f"Resolving learning order for {len(skill_names)} skills",
        data={"skills": skill_names},
    )

    # ── Step A: Graph query ─────────────────────────────────────────────────
    graph_edges = _query_graph_edges(skill_names)
    await redis_client.publish_event(
        role_id=role_id,
        phase="dependency",
        event_type="log",
        step="graph_query_done",
        message=f"Knowledge graph returned {len(graph_edges)} dependency edges",
        data={"edges": graph_edges},
    )

    # ── Step B: LLM topological sort ────────────────────────────────────────
    prompt = _DEPENDENCY_PROMPT.format(
        gaps_json=json.dumps(skill_names, ensure_ascii=False),
        edges_json=json.dumps(
            [{"from": e["from"], "to": e["to"]} for e in graph_edges],
            ensure_ascii=False,
        ),
    )

    logger.info("[DependencyResolver] Calling gpt-oss-20b (thinking) for DAG generation...")
    reasoning, content = await dependency_llm_client.stream(
        prompt=prompt,
        temperature=0.0,
        max_tokens=8000,
        role_id=role_id,
        phase="dependency",
        step_name="dep_llm_stream",
    )

    dag = _parse_dag(content)
    if not dag:
        # Fallback: all gaps in one stage, no edges
        logger.warning("[DependencyResolver] LLM parse failed — using single-stage fallback.")
        dag = {
            "stages": [{"stage": 1, "skills": skill_names, "rationale": "Ordering could not be determined — all gaps treated equally."}],
            "dependency_edges": [],
        }

    # Annotate each stage skill with its gap metadata (for path_generator)
    skill_meta = {g["skill_name"]: g for g in actionable}
    for stage in dag["stages"]:
        stage["skill_details"] = [
            skill_meta.get(s, {"skill_name": s}) for s in stage["skills"]
        ]

    # ── Event: result ────────────────────────────────────────────────────────
    total_stages = len(dag["stages"])
    await redis_client.publish_event(
        role_id=role_id,
        phase="dependency",
        event_type="result",
        step="dep_resolution_done",
        message=f"Learning order resolved: {total_stages} stage(s) across {len(skill_names)} skills",
        data={
            "stages":           total_stages,
            "skills_per_stage": {s["stage"]: s["skills"] for s in dag["stages"]},
            "edges":            len(dag["dependency_edges"]),
        },
    )

    return dag
