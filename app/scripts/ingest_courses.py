"""
ingest_courses.py
=================
One-time ingestion script: reads the Kaggle Coursera CSV, computes derived
fields, embeds each course with NvidiaEmbeddingClient, and upserts 3,404
points into a Qdrant collection named `courses`.

Usage (from project root, with venv active):
    python -m app.scripts.ingest_courses

Behaviour:
  - Creates the collection if it does not exist (vector size 1024, cosine).
  - Adds numeric payload indexes for NSGA-II filters.
  - Skips batches that fail embedding (logs warning, continues).
  - Reports progress every 100 courses.
  - Safe to re-run: uses upsert so duplicates are overwritten.
"""

import sys
import os
import uuid
import math
import time
import logging

import numpy as np
import pandas as pd

# ── Make sure project root is on sys.path ─────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from app.config import settings
from app.clients.nvidia_llm_client import nvidia_embedding_client, EMBEDDING_DIM

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ingest_courses")

# ── Constants ─────────────────────────────────────────────────────────────────
COLLECTION_NAME = "courses_listed"
BATCH_SIZE      = 50        # Nvidia API allows up to 96 texts per call
CSV_PATH        = r"C:\Users\USR005\.cache\kagglehub\datasets\yosefxx590\coursera-courses-and-skills-dataset-2025\versions\1\Coursera.csv"

# Ordinal mappings
DURATION_MAP = {
    "Less Than 2 Hours": 1,
    "1 - 4 Weeks":       2,
    "1 - 3 Months":      3,
    "3 - 6 Months":      4,
}
LEVEL_MAP = {
    "Beginner":     1,
    "Intermediate": 2,
    "Mixed":        2,
    "Advanced":     3,
}

# Approximate total learning weeks (midpoint of each bracket) for display
DURATION_WEEKS = {
    "Less Than 2 Hours": 0.125,
    "1 - 4 Weeks":       2.5,
    "1 - 3 Months":      8.0,
    "3 - 6 Months":      20.0,
}


def load_and_transform(csv_path: str) -> pd.DataFrame:
    log.info(f"Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    log.info(f"Loaded {len(df):,} rows | columns: {df.columns.tolist()}")

    # Derived numeric fields
    df["duration_score"]  = df["Duration"].map(DURATION_MAP).fillna(2).astype(int)
    df["level_score"]     = df["Level"].map(LEVEL_MAP).fillna(1).astype(int)
    df["duration_weeks"]  = df["Duration"].map(DURATION_WEEKS).fillna(2.5)
    df["popularity"]      = (df["Rate"] * np.log1p(df["Reviews"])).round(3)

    # Normalise popularity to [0, 1] for consistent objective function scale
    pop_max = df["popularity"].max()
    df["popularity_norm"] = (df["popularity"] / pop_max).round(4)

    # Skills as a clean list (lowercase for keyword matching)
    df["skills_list"] = df["Gained Skills"].apply(
        lambda s: [x.strip() for x in s.split(",") if x.strip()]
    )

    # Unique stable ID per row (deterministic: hash of Title + Institution)
    df["point_id"] = df.apply(
        lambda r: str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{r['Title']}|{r['Institution']}")),
        axis=1,
    )

    log.info("Transformations complete.")
    return df


def build_embedding_text(row: pd.Series) -> str:
    """
    Text passed to NemoRetriever for indexing.
    Skill-heavy so ANN queries on gap skill names match well semantically.
    """
    return (
        f"Course: {row['Title']}. "
        f"Offered by {row['Institution']}. "
        f"Subject: {row['Subject']}. "
        f"Level: {row['Level']}. "
        f"Skills covered: {row['Gained Skills']}."
    )


def ensure_collection(client: QdrantClient) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME in existing:
        log.info(f"Collection '{COLLECTION_NAME}' already exists — will upsert into it.")
        return

    log.info(f"Creating collection '{COLLECTION_NAME}' (dim={EMBEDDING_DIM}, cosine)...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qdrant_models.VectorParams(
            size=EMBEDDING_DIM,
            distance=qdrant_models.Distance.COSINE,
        ),
    )

    # Numeric payload indexes for fast NSGA-II pre-filtering
    for field, schema in [
        ("duration_score",  qdrant_models.PayloadSchemaType.INTEGER),
        ("level_score",     qdrant_models.PayloadSchemaType.INTEGER),
        ("popularity_norm", qdrant_models.PayloadSchemaType.FLOAT),
        ("rate",            qdrant_models.PayloadSchemaType.FLOAT),
    ]:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=schema,
        )

    # Keyword index for subject — allows fast pre-filter before ANN
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="subject",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )

    log.info("Collection and indexes created.")


def ingest(df: pd.DataFrame, client: QdrantClient) -> None:
    total   = len(df)
    upserted = 0
    failed   = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = df.iloc[batch_start : batch_start + BATCH_SIZE]

        texts      = [build_embedding_text(r) for _, r in batch.iterrows()]
        point_ids  = batch["point_id"].tolist()
        payloads   = [
            {
                "title":            r["Title"],
                "institution":      r["Institution"],
                "subject":          r["Subject"],
                "learning_product": r["Learning Product"],
                "level":            r["Level"],
                "level_score":      int(r["level_score"]),
                "duration_label":   r["Duration"],
                "duration_score":   int(r["duration_score"]),
                "duration_weeks":   float(r["duration_weeks"]),
                "rate":             float(r["Rate"]),
                "reviews":          int(r["Reviews"]),
                "popularity":       float(r["popularity"]),
                "popularity_norm":  float(r["popularity_norm"]),
                "skills":           r["skills_list"],    # list[str] — for keyword scoring
            }
            for _, r in batch.iterrows()
        ]

        try:
            vectors = nvidia_embedding_client.embed_passages(texts)
        except Exception as e:
            log.warning(f"Embedding failed for batch {batch_start}-{batch_start+len(batch)}: {e}")
            failed += len(batch)
            time.sleep(2)
            continue

        points = [
            qdrant_models.PointStruct(id=pid, vector=vec, payload=pay)
            for pid, vec, pay in zip(point_ids, vectors, payloads)
        ]

        try:
            client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
            upserted += len(points)
        except Exception as e:
            log.warning(f"Upsert failed for batch starting at {batch_start}: {e}")
            failed += len(batch)
            continue

        if upserted % 100 == 0 or batch_start + BATCH_SIZE >= total:
            pct = upserted / total * 100
            log.info(f"Progress: {upserted:,}/{total:,} ({pct:.1f}%) | failed={failed}")

        # Polite delay — Nvidia API has a generous rate limit but let's be safe
        time.sleep(0.3)

    log.info(f"Ingestion complete. Upserted={upserted:,} | Failed={failed:,}")


def main() -> None:
    df = load_and_transform(CSV_PATH)

    # Use dedicated Instance 2 for course data (separate from O*NET skills on Instance 1)
    client = QdrantClient(
        url=settings.QDRANT_COURSES_URL,
        api_key=settings.QDRANT_COURSES_API_KEY,
    )
    log.info(f"Connected to Qdrant Instance 2: {settings.QDRANT_COURSES_URL}")
    ensure_collection(client)
    ingest(df, client)

    # Final sanity check
    count = client.count(collection_name=COLLECTION_NAME, exact=True).count
    log.info(f"Collection '{COLLECTION_NAME}' now has {count:,} points.")


if __name__ == "__main__":
    main()
