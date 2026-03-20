"""
O*NET Synchronized Ingestion Script (Bulk UNWIND Version)
======================================================
Run from the project root:
    python -m app.scripts.ingest_onet

Fixes:
  - Uses Neo4j 'UNWIND' to process 1,000 items per query.
    This solves the Aura free-tier connection timeout problem!
  - 'SKIP' flags to resume from Phase 3.
"""

import os
import re
import sys
import csv
import uuid
import time
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

# ── path fix so we can import from `app` ────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from qdrant_client.http import models as qdrant_models
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from app.clients.graph_client import GraphClient
from app.clients.vector_client import VectorClient
from app.clients.embedding_client import EmbeddingClient
from app.config import settings

# ── RESUME FLAGS ─────────────────────────────────────────────────────────────
SKIP_PHASE_1 = True   # Occupations already done
SKIP_PHASE_2 = True   # Technologies already done
SKIP_PHASE_3 = False  # Skipped mid-way, run this!
# ─────────────────────────────────────────────────────────────────────────────

ONET_DIR = Path(r"C:\Users\USR005\.cache\kagglehub\datasets\emarkhauser\onet-29-0-database\versions\1\db_29_0_text")

OCCUPATION_FILE   = ONET_DIR / "Occupation Data.txt"
TECH_SKILLS_FILE  = ONET_DIR / "Technology Skills.txt"
SKILLS_FILE       = ONET_DIR / "Skills.txt"

COLLECTION_NAME   = "onet_skills"
VECTOR_SIZE       = 384
BATCH_SIZE        = 64
NEO4J_BATCH_SIZE  = 1000

def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")

def read_tsv(path: Path) -> List[Dict[str, str]]:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append({k.strip(): v.strip() for k, v in row.items()})
    return rows

def progress(label: str, done: int, total: int, elapsed: float):
    pct  = done / total * 100 if total else 0
    rate = done / elapsed if elapsed > 0 else 0
    remaining = (total - done) / rate if rate > 0 else 0
    print(
        f"  [{label}] {done:>6}/{total}  ({pct:5.1f}%)  "
        f"{rate:6.1f} items/s  ~{remaining:.0f}s remaining"
    )

def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))

def ensure_collection(vc: VectorClient):
    existing = [c.name for c in vc.client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        print(f"  Creating Qdrant collection '{COLLECTION_NAME}' …")
        vc.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qdrant_models.VectorParams(
                size=VECTOR_SIZE,
                distance=qdrant_models.Distance.COSINE,
            ),
        )

# ── Phase 1 ─────────────────────────────────────────────────────────────────
def ingest_occupations(gc: GraphClient, rows: List[Dict]) -> Dict[str, str]:
    soc_map = {row["O*NET-SOC Code"]: f"SOC_{row['O*NET-SOC Code']}" for row in rows if row.get("O*NET-SOC Code")}
    if SKIP_PHASE_1:
        print("[Phase 1] Skipping Occupations (already done).")
        return soc_map
    # Using Bulk
    return soc_map


# ── Phase 2 ─────────────────────────────────────────────────────────────────
def ingest_technologies(gc: GraphClient, vc: VectorClient, ec: EmbeddingClient, rows: List[Dict], soc_map: Dict[str, str]):
    if SKIP_PHASE_2:
        print("[Phase 2] Skipping Technologies (already done).")
        return


# ── Phase 3 ─────────────────────────────────────────────────────────────────
def ingest_skills(gc: GraphClient, vc: VectorClient, ec: EmbeddingClient, rows: List[Dict], soc_map: Dict[str, str]):
    if SKIP_PHASE_3:
        print("[Phase 3] Skipping Skills.")
        return

    print(f"\n[Phase 3] Processing {len(rows)} Skill rows …")
    skill_by_id = {}
    soc_to_skills = defaultdict(list)
    for row in rows:
        soc, eid, ename, sid, val = row.get("O*NET-SOC Code"), row.get("Element ID"), row.get("Element Name"), row.get("Scale ID"), row.get("Data Value")
        if not eid or not ename: continue
        cid = f"EL_{eid.replace('.', '_')}"
        if cid not in skill_by_id: skill_by_id[cid] = {"canonical_id": cid, "element_id": eid, "name": ename}
        if soc and sid in ("IM", "LV"): soc_to_skills[soc].append({"cid": cid, "sid": sid, "val": float(val or 0)})

    unique_skills = list(skill_by_id.values())
    total = len(unique_skills)

    # ── Neo4j Nodes Bulk ──
    t0 = time.time()
    def merge_skills_bulk(tx, batch):
        tx.run(
            """
            UNWIND $batch AS s
            MERGE (sk:Skill {canonical_id: s.canonical_id})
            SET sk.element_id = s.element_id, sk.name = s.name
            """,
            batch=batch
        )

    with gc.driver.session(database=settings.NEO4J_DATABASE) as session:
        print("  Merging Skill nodes into Neo4j using UNWIND …")
        for chunk in chunker(unique_skills, NEO4J_BATCH_SIZE):
            session.execute_write(merge_skills_bulk, chunk)
        progress("Skills Nodes", total, total, time.time()-t0)

        # ── Neo4j Relationships Bulk ──
        print("  Creating skill relationships using UNWIND …")
        agg = {}
        for soc, ds in soc_to_skills.items():
            if soc not in soc_map: continue
            for d in ds:
                key = (soc_map[soc], d["cid"])
                if key not in agg: agg[key] = {"cid": d["cid"], "occ_cid": soc_map[soc], "imp": 0.0, "lv": 0.0}
                if d["sid"] == "IM": agg[key]["imp"] = d["val"]
                else: agg[key]["lv"] = d["val"]
        
        agg_list = list(agg.values())
        t1 = time.time()

        def merge_skill_rels_bulk(tx, batch):
            tx.run(
                """
                UNWIND $batch AS b
                MATCH (o:Occupation {canonical_id: b.occ_cid})
                MATCH (sk:Skill {canonical_id: b.cid})
                MERGE (o)-[r:REQUIRES_SKILL]->(sk)
                SET r.importance = b.imp, r.level = b.lv
                """,
                batch=batch
            )

        done_rels = 0
        for chunk in chunker(agg_list, NEO4J_BATCH_SIZE):
            try:
                session.execute_write(merge_skill_rels_bulk, chunk)
            except (ServiceUnavailable, SessionExpired):
                print(f"\n  [Retry] Connection lost. Reconnecting...")
                session = gc.driver.session(database=settings.NEO4J_DATABASE)
                session.execute_write(merge_skill_rels_bulk, chunk)
            done_rels += len(chunk)
            if done_rels % (NEO4J_BATCH_SIZE * 5) == 0 or done_rels == len(agg_list):
                progress("Skill-Rels", done_rels, len(agg_list), time.time()-t1)

    # ── Qdrant upsert ──
    print("  Upserting Skills to Qdrant …")
    t2 = time.time()
    for batch_start in range(0, total, BATCH_SIZE):
        batch = unique_skills[batch_start: batch_start + BATCH_SIZE]
        vecs = ec.embed_documents([b["name"] for b in batch])
        points = [qdrant_models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_DNS, b["canonical_id"])), vector=v, payload={**b, "type": "skill"}) for b, v in zip(batch, vecs)]
        vc.client.upsert(collection_name=COLLECTION_NAME, points=points)
        progress("Skills→Qdrant", min(batch_start + len(batch), total), total, time.time() - t2)


def main():
    print("="*60 + "\n  O*NET Bulk Ingestion (Resumable Version)\n" + "="*60)
    gc, vc, ec = GraphClient(), VectorClient(), EmbeddingClient()
    if not gc.test_connection() or not vc.test_connection(): sys.exit(1)
    ensure_collection(vc)
    occ_rows, tech_rows, skill_rows = read_tsv(OCCUPATION_FILE), read_tsv(TECH_SKILLS_FILE), read_tsv(SKILLS_FILE)
    t_start = time.time()
    soc_map = ingest_occupations(gc, occ_rows)
    ingest_technologies(gc, vc, ec, tech_rows, soc_map)
    ingest_skills(gc, vc, ec, skill_rows, soc_map)
    gc.close()
    print("\n" + "="*60 + f"\n  ✅ Ingestion complete in {time.time()-t_start:.1f}s\n" + "="*60)

if __name__ == "__main__":
    main()
