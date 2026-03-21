# AdaptIQ: Project Progress & Roadmap

*Last updated: March 2026 — complete end-to-end employee flow now live.*

This document tracks what has been implemented, the methodologies used, active bugs, and machine-learning milestones.

---

## ✅ Completed — All Phases

### Phase 1: Core Infrastructure
- **FastAPI backend** scaffolded (`app/api`, `app/services`, `app/models`, `app/clients`, `app/utils`).
- **Pydantic settings** (`app/config.py`) — all secrets validated at startup from `.env`.
- **Async SQLite** via `aiosqlite` + SQLAlchemy. Models: `Role`, `TargetSkill`, `TeamRelevanceSignal`, `Employee`, `EmployeeMastery`.
- **Loguru logger** (`app/utils/logger.py`) — structured JSON to stdout + `logs/app.log`.
- **WebSocket manager** (`app/api/routers/websocket.py`) + **Redis Pub/Sub bridge** — backend emits to `channel:{role_id}`, WS proxies to browser in real-time.

### Phase 2: Client Integrations
| Client | Details |
|---|---|
| `nvidia_llm_client.py` | `openai/gpt-oss-20b` + `stepfun-ai/step-3.5-flash` via `integrate.api.nvidia.com`. Parses `reasoning_content` (CoT) and `content` (answer) separately. `complete()` returns **only** `content`. |
| `embedding_client.py` | Local `intfloat/multilingual-e5-small` — 384-dim dense vectors for Qdrant `onet_skills`. |
| `nvidia_embedding_client` (inside nvidia_llm_client.py) | `nvidia/nv-embedqa-e5-v5` — 2048-dim vectors for `courses_listed` Qdrant collection. |
| `vector_client.py` | Qdrant Cloud REST client — upsert, search, delete. |
| `graph_client.py` | Neo4j Aura — Cypher queries for REQUIRES / BUILDS_ON / LEADS_TO edges. |
| `redis_client.py` | `aioredis` Pub/Sub — `publish_event(role_id, phase, type, step, message, data)`. |

### Phase 3: Employer Flow (Setup Role)
`POST /employer/setup-role` — full background pipeline:
1. PDF parse → JD text extraction.
2. LLM skill extraction (step-3.5-flash, streaming, top 15-20 critical skills).
3. O*NET normalization (embed → Qdrant → LLM judge → coin if NONE).
4. Team context analysis (LLM assigns T1-T4 tier to each skill).
5. 2D mastery matrix (seniority × tier → target_mastery 0.0–1.0).
6. SQLite persistence (`Role`, `TargetSkill`, `TeamRelevanceSignal`).
- All steps broadcast over Redis Pub/Sub (see `docs/employer_redis.md`).

### Phase 3.5: Skill Normalization (`app/services/skill_normalizer.py`)
2-stage agentic pipeline — grounding raw LLM skill names to O*NET canonical IDs:
1. **Vector search** — 384-dim embed → Qdrant `onet_skills` top-3 (score ≥ 0.50).
2. **LLM judge** — `gpt-oss-20b` (no thinking) returns candidate index `1`/`2`/`3` or `NONE`.
3. **Auto-coin** — if NONE: LLM coins a clean canonical name → new Qdrant point + Neo4j node.
- **Safety guards**: empty strings and literal `"NONE"` are never stored.
- **Bug fixed (March 2026)**: `complete()` was concatenating `reasoning + "\n" + content`, causing CoT text to bleed into coined skill names. Fixed to return `content.strip()` only.

### Phase 4: Redis Event-Driven Architecture
- All orchestrators use `redis_client.publish_event()`.
- Browser connects via WebSocket; backend proxies events in real-time.
- LLM streaming: text chunks are pushed token-by-token as `stream_chunk` events.

### Phase 5: Employee API Endpoint
`POST /api/v1/employee/onboard-path` — multipart: `role_id` (form) + `resume` (PDF file).
- Returns HTTP 202 with `employee_id` and `role_id` immediately.
- Spawns background orchestration task.

### Phase 6: Resume Extraction (step-3.5-flash)
`app/services/employee_flow/orchestrator.py` — `_run_pipeline()`:
- PDF parsed in thread pool (non-blocking).
- `step-3.5-flash` streams skill extraction JSON in real-time.
- Prompt demands: `skill_name` + `context_depth` (verbatim resume evidence sentence).
- Output: list of `{skill_name, context_depth}` dicts.
- Redis events: `pdf_parsing` → `pdf_parsed` → `llm_extraction_start` → `stream_chunk×N` → `stream_end` → `llm_extraction_done`.

### Phase 7: O*NET Normalization
Runs the same `normalize_skills()` pipeline as the employer flow — each employee skill is grounded to a canonical ID.
- Redis events: `normalization_start` → `qdrant_query` → `qdrant_results` → (`llm_judge` | `llm_coined`) per skill → `normalization_done`.

### Phase 8: Mastery Scoring (`gpt-oss-20b`, thinking ON)
Batch-scores all normalized skills in **one LLM call** using the `context_depth` evidence:
- Evidence classified into: `expert (0.90)` / `advanced (0.70)` / `intermediate (0.50)` / `basic (0.25)` / `surface (0.10)`.
- Mandatory downgrade: "familiar with" → basic; skills-section-only → surface.
- Upgrade signal: hard quantitative metric + ownership → raise one level.
- CoT reasoning streamed live (`chunk_type: reasoning`), final JSON streamed as `content`.
- Redis events: `mastery_scoring_start` → `stream_chunk×N` → `stream_end` → `skill_mastery_computed×N` → `mastery_scoring_done`.

### Phase 9: Gap Analysis (pure math)
No LLM — deterministic:
```
gap = max(0, target_mastery − current_mastery)
priority_score = tier_weight × gap
tier_weights: T1=1.0, T2=0.7, T3=0.4, T4=0.1
category: critical≥0.50 | moderate≥0.25 | minor≥0.05 | met<0.05
```
- Redis events: `gap_analysis_start` → `skill_gap_computed×N` → `gap_analysis_done`.

### Phase 10: Dependency Resolution + NSGA-II Course Selection

**10A — Dependency Resolver** (`app/services/employee_flow/dependency_resolver.py`):
- Queries Neo4j for REQUIRES / BUILDS_ON / LEADS_TO edges between gap skills.
- Sends graph + gap data to `gpt-oss-20b` (thinking ON) to order skills into sequential stages.
- Output: `{"stages": [...], "dependency_edges": [...]}`.
- Redis events: `dependency_start` → `graph_query` → `dependency_streaming×N` → `dependency_ready`.

**10B — Path Generator** (`app/services/employee_flow/path_generator.py`):
- For each gap skill: embeds skill name with `nvidia/nv-embedqa-e5-v5` (2048-dim) → searches `courses_listed` Qdrant collection (top-30, score_threshold=0.30).
- **NSGA-II 4-objective Pareto optimisation** (40 generations, population=30):
  - `f1 = −relevance_score` (Qdrant similarity)
  - `f2 = duration_weeks` (speed — minimize)
  - `f3 = −(quality_score × popularity)` (Pareto quality)
  - `f4 = |difficulty_level − required_level|` (difficulty fit)
- `_pick_three()` selects Sprint (best f2), Balanced (geometric centre), Quality (best f3).
- Redis events: `nsga_start` → `nsga_gap_done×N` → `paths_ready`.

### Phase 11: Journey Narration (`gpt-oss-20b`, thinking ON)
`app/services/employee_flow/journey_narrator.py`:
- Validates path coherence across all tracks.
- Writes HR-readable narrative paragraphs for Sprint / Balanced / Quality.
- Builds the visualization tree JSON (`root → main_branch → twig`) for the frontend bubble-tree renderer.
- Redis events: `narrator_start` → `narrator_llm_stream×N` → `narrator_llm_stream (end)` → `journey_ready`.

### Phase DB: Persistence
- Employee mastery + journey stored in SQLite via `asyncio.ensure_future` (fire-and-forget background write).
- Redis event: `employee_persist_done`.

---

## 🤖 Machine Learning Pipeline (`machine_learning/`)

| Notebook | Status | Output |
|---|---|---|
| `01_data_exploration.ipynb` | ✅ Done | O*NET skill taxonomy profiled; key fields identified. |
| `02_data_preparation.ipynb` | ✅ Done | `resume_evidence.jsonl` + `jd_requirements.jsonl` (~2 000 training pairs each) in `machine_learning/data/nb2_outputs/`. |
| `03_synthetic_pair_generation.ipynb` | 🔜 Next | Use LLM to augment to ~20 000 skill context pairs. |
| `04_model_training.ipynb` | 🔜 Pending | Fine-tune a 384-dim sentence-transformer on the synthetic pairs (Kaggle GPU). |

---

## 🐛 Bugs Fixed

| Date | File | Bug | Fix |
|---|---|---|---|
| March 2026 | `app/clients/nvidia_llm_client.py` | `complete()` returned `reasoning + "\n" + content` — entire CoT thinking trace was stored as the coined skill name | Now returns `content.strip() if content else "NONE"` only |
| March 2026 | Qdrant `onet_skills` | 3 broken points (`TECH_none`, `TECH_NONE`, `TECH_None`) created before the fix | Deleted via `app/scripts/cleanup_none_nodes.py` |

---

## 🔜 Remaining Work

| Priority | Item |
|---|---|
| High | Run `cleanup_none_nodes.py` with regex pattern to purge any `TECH_we_need_to_produce...` nodes still in Qdrant/Neo4j from pre-fix runs |
| High | Notebook 3 — synthetic pair generation (~20k) |
| Medium | Notebook 4 — fine-tune sentence-transformer on Kaggle |
| Medium | Swap `embedding_client.py` to use the fine-tuned model checkpoint |
| Low | Frontend: consume Phase 10/11 events for bubble-tree visualization |
| Low | Add MCQ/interactive scenario step (Phase 12 stretch goal) |
