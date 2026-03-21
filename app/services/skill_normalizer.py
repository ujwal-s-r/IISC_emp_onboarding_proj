"""
LLM-Based Skill Normalizer
===========================
Implements the advanced 2-stage skill normalization pipeline:

Stage 1 — Vector Retrieval:
  - Embed the raw LLM skill name.
  - Query Qdrant for the top-3 closest O*NET matches.
  - Show these as candidates to the LLM judge.

Stage 2 — LLM Disambiguation:
  - Ask LLM: "Which of these 3 is the best match? Or none?"
  - If LLM picks one → use that O*NET canonical node.
  - If LLM says none → ask LLM to produce a clean canonical name,
    then create a new node in Neo4j AND Qdrant, so future lookups work.

Redis Events are published at every decision point so the frontend
and judge can see the full reasoning chain.
"""

import re
import uuid
from typing import Dict, List, Optional, Any

from qdrant_client.http import models as qdrant_models

from app.clients.nvidia_llm_client import nvidia_llm_client
from app.clients.embedding_client import embedding_client
from app.clients.vector_client import vector_client
from app.clients.graph_client import graph_client
from app.clients.redis_client import redis_client
from app.config import settings
from app.utils.logger import logger


ONET_COLLECTION       = "onet_skills"
NORMALIZATION_TOP_K   = 3
SCORE_CUTOFF          = 0.50   # Min score for candidates to even reach the LLM

# ── Prompts ───────────────────────────────────────────────────────────────────

JUDGE_PROMPT = """\
You are a technical skill taxonomy expert.

A hiring system extracted the skill "{raw_name}" from a Job Description.
We queried an O*NET skill database and found these top {k} candidates:

{candidates}

Task: Pick the SINGLE BEST match for "{raw_name}" from the candidates above.
Rules:
- Reply with ONLY the candidate number (1, 2, or 3).
- If NONE of the candidates are a reasonable match, reply with: NONE
- Do NOT explain. Do NOT add any other text.
"""

CANONICALIZE_PROMPT = """\
You are a technical skill taxonomy expert.

The skill "{raw_name}" was NOT found in the O*NET database.

Task: Produce a clean, canonical skill name for this skill (e.g., "Apache PySpark", "Docker Containerization", "REST API Design").
Rules:
- Reply with ONLY the canonical name. No quotes, no punctuation, no explanation.
- Use Title Case.
- Be specific but concise (2-5 words max).
"""


def _normalize_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _make_cid(name: str) -> str:
    return f"TECH_{_normalize_key(name)}"


def _add_to_qdrant(cid: str, name: str, vector: list):
    """Upsert a newly coined canonical node to Qdrant so future lookups hit it."""
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, cid))
    vector_client.client.upsert(
        collection_name=ONET_COLLECTION,
        points=[qdrant_models.PointStruct(
            id=point_id,
            vector=vector,
            payload={"canonical_id": cid, "name": name, "type": "tech", "source": "llm_derived"},
        )],
    )
    logger.info(f"[Normalizer] New node upserted in Qdrant: {cid}")


def _add_to_neo4j(cid: str, name: str):
    """Merge a newly coined canonical Technology node into Neo4j."""
    with graph_client.driver.session(database=settings.NEO4J_DATABASE) as session:
        session.run(
            """
            MERGE (t:Technology {canonical_id: $cid})
            SET t.name = $name, t.source = 'llm_derived'
            """,
            cid=cid, name=name,
        )
    logger.info(f"[Normalizer] New node merged in Neo4j: {cid}")


def _fetch_onet_level(cid: str) -> Optional[float]:
    """Query Neo4j for the average importance level of a skill."""
    try:
        with graph_client.driver.session(database=settings.NEO4J_DATABASE) as session:
            rec = session.run(
                "MATCH ()-[r:REQUIRES_SKILL]->(sk {canonical_id: $cid}) RETURN avg(r.level) AS avg_level",
                cid=cid,
            ).single()
            if rec and rec["avg_level"] is not None:
                return round(rec["avg_level"], 2)
    except Exception as e:
        logger.warning(f"[Normalizer] Neo4j level fetch failed for {cid}: {e}")
    return None


async def normalize_skill(raw_name: str, role_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Normalize a single skill name using the full LLM + Qdrant pipeline.
    Emits fine-grained Redis events at every decision point if role_id is given.
    """
    result = {
        "raw_name":    raw_name,
        "matched_name": raw_name,
        "canonical_id": None,
        "onet_level":   None,
        "source":       "no_match",
        "llm_reasoning": None,
    }

    async def _pub(event_type, step, message, data=None):
        """Helper to only publish to Redis if we have a role_id."""
        if role_id:
            await redis_client.publish_event(
                role_id=role_id,
                phase="normalization",
                event_type=event_type,
                step=step,
                message=message,
                model="openai/gpt-oss-20b",
                data=data or {}
            )

    try:
        # ── Stage 1: Embed + Retrieve top-3 from Qdrant ───────────────────────
        await _pub("log", "qdrant_query", f"Querying Qdrant for '{raw_name}'", {
            "raw_skill": raw_name
        })

        vec = embedding_client.embed_query(raw_name)
        hits = vector_client.client.query_points(
            collection_name=ONET_COLLECTION,
            query=vec,
            limit=NORMALIZATION_TOP_K,
            score_threshold=SCORE_CUTOFF,
        ).points

        if not hits:
            logger.info(f"[Normalizer] No Qdrant candidates for '{raw_name}'. LLM will coin a name.")
            await _pub("log", "qdrant_no_match", f"No O*NET candidates found for '{raw_name}'. LLM will coin a name.", {
                "raw_skill": raw_name
            })
        else:
            # Build candidate list for logging
            top_candidates = [
                {
                    "rank": i + 1,
                    "name": h.payload.get("name", "?"),
                    "canonical_id": h.payload.get("canonical_id", "?"),
                    "score": round(h.score, 3)
                }
                for i, h in enumerate(hits)
            ]

            candidate_lines = "\n".join(
                f"{c['rank']}. {c['name']} (canonical_id: {c['canonical_id']}, score: {c['score']:.3f})"
                for c in top_candidates
            )

            # Publish Qdrant results
            await _pub("log", "qdrant_results", f"Qdrant returned {len(hits)} candidates for '{raw_name}'", {
                "raw_skill": raw_name,
                "top_candidates": top_candidates
            })

            logger.info(f"[Normalizer] Sending {len(hits)} candidates for '{raw_name}' to LLM judge:\n{candidate_lines}")

            # ── Stage 2A: LLM Judge ─────────────────────────────────────────
            prompt = JUDGE_PROMPT.format(
                raw_name=raw_name,
                k=len(hits),
                candidates=candidate_lines,
            )
            llm_reply = await nvidia_llm_client.complete(prompt, max_tokens=500)
            logger.info(f"[Normalizer] LLM judge raw reply for '{raw_name}':\n{llm_reply}")

            # Flexible parsing: look for the first 1, 2, or 3, or "NONE"
            match_none = re.search(r"\bNONE\b", llm_reply, re.IGNORECASE)
            match_num  = re.search(r"\b([123])\b", llm_reply)

            if match_num and not match_none:
                chosen_idx = int(match_num.group(1)) - 1
                if chosen_idx < len(hits):
                    chosen = hits[chosen_idx]
                    payload = chosen.payload or {}
                    cid   = payload.get("canonical_id")
                    mname = payload.get("name", raw_name)
                    result.update({
                        "matched_name":  mname,
                        "canonical_id":  cid,
                        "onet_level":    _fetch_onet_level(cid) if cid else None,
                        "source":        "onet_match",
                        "llm_reasoning": llm_reply,
                    })
                    logger.info(f"[Normalizer] '{raw_name}' matched to candidate {chosen_idx+1}: '{mname}'")

                    await _pub("decision", "llm_judge", f"LLM resolved '{raw_name}' → '{mname}'", {
                        "raw_skill":        raw_name,
                        "llm_raw_reply":    llm_reply,
                        "chosen_candidate": chosen_idx + 1,
                        "matched_name":     mname,
                        "canonical_id":     cid,
                        "source":           "onet_match"
                    })
                    return result

            if match_none:
                logger.info(f"[Normalizer] LLM judge decided NONE for '{raw_name}'.")
                await _pub("log", "llm_judge_none", f"LLM decided no O*NET match for '{raw_name}'", {
                    "raw_skill":     raw_name,
                    "llm_raw_reply": llm_reply,
                })

        # ── Stage 2B: LLM coins a new canonical name ──────────────────────────
        canon_prompt = CANONICALIZE_PROMPT.format(raw_name=raw_name)
        coined_name  = await nvidia_llm_client.complete(canon_prompt, max_tokens=20)
        coined_name  = coined_name.strip().strip('"').strip("'")

        # Guard: don't coin "NONE" or empty names
        if not coined_name or coined_name.upper() == "NONE":
            logger.warning(f"[Normalizer] LLM failed to coin a valid name for '{raw_name}'. Skipping DB creation.")
            return result

        new_cid = _make_cid(coined_name)
        logger.info(f"[Normalizer] LLM coined new canonical: '{coined_name}' [{new_cid}]")

        # Embed and add to both DBs
        coined_vec = embedding_client.embed_documents([coined_name])[0]
        _add_to_qdrant(new_cid, coined_name, coined_vec)
        _add_to_neo4j(new_cid, coined_name)

        result.update({
            "matched_name":  coined_name,
            "canonical_id":  new_cid,
            "onet_level":    None,
            "source":        "llm_new",
            "llm_reasoning": coined_name,
        })

        await _pub("decision", "llm_coined", f"New skill coined: '{coined_name}'", {
            "raw_skill":     raw_name,
            "llm_raw_reply": coined_name,
            "coined_name":   coined_name,
            "canonical_id":  new_cid,
            "source":        "llm_new"
        })

    except Exception as e:
        logger.error(f"[Normalizer] Error normalizing '{raw_name}': {e}")

    return result


async def normalize_skills(raw_skills: List[Dict[str, Any]], role_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Normalize a batch of skills extracted by the JD LLM.
    Each item must have at least a 'skill_name' key.
    Returns the same list enriched with normalization fields.
    """
    normalized = []
    for skill in raw_skills:
        norm = await normalize_skill(skill["skill_name"], role_id=role_id)
        enriched = {**skill, **norm}
        normalized.append(enriched)
    return normalized
