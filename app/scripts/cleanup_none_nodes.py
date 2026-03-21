"""
Cleanup Script — Purge Bad Canonical Nodes.
==========================================
Removes two categories of accidental nodes created during LLM normalizer testing:

  Category 1: Simple NONE variants (TECH_none, TECH_NONE, TECH_None)
  Category 2: Garbage nodes where canonical_id starts with 'TECH_we_need_to_produce'
              These were created when gpt-oss-20b (thinking=OFF) leaked its CoT
              reasoning into content, turning the entire prompt echo into a skill name.

Actions per category:
  • Delete matching nodes from Neo4j.
  • Scroll Qdrant 'onet_skills' and delete all matching points by payload filter.
"""

import uuid
from qdrant_client.http import models as qdrant_models
from app.clients.graph_client import graph_client
from app.clients.vector_client import vector_client
from app.config import settings
from app.utils.logger import logger

ONET_COLLECTION = "onet_skills"

# ── Category 1: simple NONE variants ─────────────────────────────────────────
NONE_VARIANTS = ["TECH_none", "TECH_NONE", "TECH_None"]

# ── Category 2: garbage prefix produced by CoT leakage ───────────────────────
GARBAGE_PREFIX = "TECH_we_need_to_produce"


def cleanup_neo4j():
    """Delete all bad canonical nodes from Neo4j."""
    print("\n[Neo4j] Cleaning up bad canonical nodes...")
    try:
        with graph_client.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Category 1: exact match variants
            for cid in NONE_VARIANTS:
                res = session.run(
                    "MATCH (t {canonical_id: $cid}) DETACH DELETE t RETURN count(t) AS n",
                    cid=cid,
                ).single()
                n = res["n"] if res else 0
                if n:
                    print(f"  Deleted {n} node(s) with canonical_id='{cid}'")

            # Category 2: prefix match (STARTS WITH)
            res = session.run(
                "MATCH (t) WHERE t.canonical_id STARTS WITH $prefix "
                "DETACH DELETE t RETURN count(t) AS n",
                prefix=GARBAGE_PREFIX,
            ).single()
            n = res["n"] if res else 0
            print(f"  Deleted {n} garbage node(s) with prefix '{GARBAGE_PREFIX}...'")
    except Exception as e:
        print(f"  Neo4j error: {e}")


def cleanup_qdrant():
    """Delete all bad points from Qdrant using payload scroll + delete."""
    print("\n[Qdrant] Cleaning up bad canonical nodes...")
    deleted_total = 0

    # Category 1: delete by known UUID5 point IDs
    for variant in NONE_VARIANTS:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, variant))
        try:
            vector_client.client.delete(
                collection_name=ONET_COLLECTION,
                points_selector=[point_id],
            )
            print(f"  Deleted Qdrant point {point_id} ({variant})")
            deleted_total += 1
        except Exception as e:
            print(f"  Point {variant} not found or already deleted: {e}")

    # Category 2: scroll ALL points and delete those whose canonical_id contains garbage prefix
    # (MatchText requires a Qdrant text index; we scroll without filter instead)
    offset = None
    garbage_ids = []
    scanned = 0
    while True:
        batch, next_offset = vector_client.client.scroll(
            collection_name=ONET_COLLECTION,
            limit=250,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        scanned += len(batch)
        for point in batch:
            cid = (point.payload or {}).get("canonical_id", "")
            if "we_need_to_produce" in cid or "we_need_to_produce" in cid.lower():
                print(f"  Found garbage: id={point.id}  cid={cid[:70]}")
                garbage_ids.append(point.id)

        if not next_offset:
            break
        offset = next_offset

    print(f"  Scanned {scanned} Qdrant points. Found {len(garbage_ids)} garbage points.")

    if garbage_ids:
        vector_client.client.delete(
            collection_name=ONET_COLLECTION,
            points_selector=garbage_ids,
        )
        print(f"  Deleted {len(garbage_ids)} garbage point(s) from Qdrant.")
        deleted_total += len(garbage_ids)
    else:
        print("  No garbage points found with 'we_need_to_produce' in canonical_id.")

    print(f"[Qdrant] Total deleted: {deleted_total}")


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("Comprehensive DB Cleanup — Bad Canonical Nodes")
    print("=" * 55)
    cleanup_neo4j()
    cleanup_qdrant()
    print("\n" + "=" * 55)
    print("Cleanup complete.")
    print("=" * 55)

