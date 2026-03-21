# AdaptIQ: System Working Flow

*Last updated: March 2026 — all 11 phases of the employee flow are live.*

This document explains how the AdaptIQ backend flows operate end-to-end, from the initial API request through all 11 pipeline phases down to database persistence.

---

## 🏗️ 1. The Employer Setup Flow (Orchestrator)

The core engine of the "Employer side" is the Orchestrator (`app/services/employer_flow/orchestrator.py`). It chains PDF parsing, LLM generation, vector search, and graph traversal in a single asynchronous background pipeline.

It heavily uses **Redis Pub/Sub** to stream its current step, LLM reasoning, and live token streams back to the frontend in real-time, preventing HTTP timeouts on long LLM calls.

### Sequence Diagram: Creating a Role

```mermaid
sequenceDiagram
    actor Employer
    participant API as /setup-role Endpoint
    participant DB as SQLite (aiosqlite)
    participant PDF as PDF Service
    participant LLM as Nvidia API (step-3.5-flash)
    participant Norm as normalizer.py
    participant Qdrant as Vector DB (onet_skills)
    participant Neo4j as Graph DB
    participant Redis as Redis Pub/Sub

    Employer->>API: POST /setup-role (FormData + PDFs)
    API->>DB: Create basic Role {title, seniority}
    DB-->>API: Returns Role ID
    API->>Employer: HTTP 202 Accepted (Role ID)

    note over API, Redis: Background Task Begins

    API->>Redis: publish(jd_extraction/start/pdf_parsing)
    API->>PDF: extract_text(JD Bytes), extract_text(Context Bytes)
    PDF-->>API: JD Text, Context Text
    API->>Redis: publish(jd_extraction/log/pdf_parsed)

    API->>Redis: publish(jd_extraction/log/llm_extraction_start)
    API->>LLM: Prompt (JD Text) → Stream tokens
    LLM-->>API: stream_chunk×N → redis, then final JSON
    API->>Redis: publish(jd_extraction/result/llm_extraction_done)

    API->>Norm: normalize_skills(raw_skills)
    loop For Each Skill
        Norm->>Qdrant: embed 384d → query_points(limit=3)
        Qdrant-->>Norm: Top 3 Candidates
        Norm->>LLM: LLM Judge (gpt-oss-20b, no thinking)
        LLM-->>Norm: "1" | "2" | "3" | "NONE"
        alt Match Found
            Norm->>Neo4j: Fetch O*NET metadata
        else NONE
            Norm->>LLM: Coin canonical name
            Norm->>Qdrant: upsert(New Vector)
            Norm->>Neo4j: MERGE(New Node)
        end
        Norm->>Redis: publish(normalization/decision/llm_judge or llm_coined)
    end
    Norm-->>API: List of normalized skills with canonical_id

    API->>LLM: Team context analysis (Tiers + Mastery Matrix)
    LLM-->>API: JSON {canonical_id: {tier, target_mastery}}
    API->>DB: persistTargetSkills(matrix_scores)
    API->>Redis: publish(db/complete)
```

---

## 🧠 2. Advanced Skill Normalization (In-Depth)

`app/services/skill_normalizer.py` — grounds raw LLM skill names to O*NET canonical IDs.

**Why it matters:** "K8s" and "Kubernetes" both normalize to `TECH_kubernetes`. Without this, employee/employer skills can never match.

**The Agentic Pipeline:**
1. **Local vector search** (`intfloat/multilingual-e5-small`, 384-dim) — no external API call; fast.
2. **LLM Judge** (`gpt-oss-20b`, thinking OFF) — evaluates top-3 candidates semantically.  
   `complete()` returns **only** `content` (never reasoning) to prevent CoT text from becoming a skill name.
3. **Auto-coin & persist** — if NONE: new canonical node created in Qdrant + Neo4j permanently.

```mermaid
graph TD
    A([Raw Skill from JD/Resume]) --> B[Generate 384d Dense Vector]
    B --> C[(Qdrant onet_skills)]
    C -- Returns Top 3 --> D{Score ≥ 0.50?}
    D -- No --> H
    D -- Yes --> E((gpt-oss-20b Judge\nthinking OFF))
    E --> F{Is Match Valid?}
    F -- Yes --> G[Return Canonical ID + Neo4j metadata]
    F -- No / NONE --> H[Prompt LLM to Coin a Canonical Name]
    H --> I{Coined name valid?}
    I -- No empty/NONE --> J[Drop Skill]
    I -- Yes --> K[Upsert to Qdrant + MERGE to Neo4j]
    K --> L[Return New Canonical ID]
```

---

## 🔄 3. Redis + WebSocket Event Architecture

All heavy compute (embedding, vector search, LLM generation, graph traversal) takes 10–60 seconds per flow.

**Pattern:**
1. Frontend opens WS: `ws://api/employer/ws/setup/{role_id}` or `ws://api/employee/ws/{role_id}`.
2. HTTP POST returns **202 Accepted** immediately.
3. Background task fires hundreds of JSON events to Redis `channel:{role_id}`.
4. WS router subscribes and proxies events to browser tick-by-tick.

**Event envelope:**
```json
{"role_id": "...", "phase": "...", "type": "start|log|stream_chunk|stream_end|decision|result|complete|progress", "step": "...", "message": "...", "model": "...", "data": {}}
```

See `docs/employee_redis.md` for the complete event catalogue (Phases 6–11).

---

## 👤 4. The Employee Onboarding Flow (Phases 6–11)

`POST /api/v1/employee/onboard-path` — multipart: `role_id` + `resume` PDF.

`app/services/employee_flow/orchestrator.py` runs a linear, sequential pipeline of 6 phases. Each fires its own Redis events and passes its output to the next stage. All phases complete before `employee_persist_done` fires.

### Complete Sequence Diagram

```mermaid
sequenceDiagram
    actor Employee
    participant API as /employee/onboard-path
    participant DB as SQLite
    participant Redis as Redis Pub/Sub
    participant PDF as PDF Service
    participant LLM1 as step-3.5-flash\n(resume extraction)
    participant Norm as skill_normalizer.py
    participant LLM2 as gpt-oss-20b\n(mastery, thinking ON)
    participant Dep as dependency_resolver.py
    participant LLM3 as gpt-oss-20b\n(DAG ordering, thinking ON)
    participant NSGA as path_generator.py\nNSGA-II
    participant Qdrant2 as Qdrant courses_listed\n(2048-dim NemoRetriever)
    participant LLM4 as gpt-oss-20b\n(journey narration, thinking ON)

    Employee->>API: POST /onboard-path (role_id + resume PDF)
    API->>DB: Create Employee record
    DB-->>API: employee_id
    API->>Employee: HTTP 202 {employee_id, role_id}

    note over API, LLM4: Background pipeline starts

    rect rgb(240,248,255)
      note over API: Phase 6 — Resume Extraction
      API->>Redis: pdf_parsing (start)
      API->>PDF: extract_text(resume bytes) [threadpool]
      PDF-->>API: resume text
      API->>Redis: pdf_parsed (log)
      API->>Redis: llm_extraction_start (log)
      API->>LLM1: Prompt: extract [skill_name, context_depth] array
      LLM1-->>API: stream_chunk×N → Redis
      LLM1-->>API: Final JSON
      API->>Redis: llm_extraction_done (result)
    end

    rect rgb(240,255,240)
      note over API: Phase 7 — O*NET Normalization
      API->>Norm: normalize_skills(raw_skills)
      Norm-->>Redis: qdrant_query, qdrant_results, llm_judge|llm_coined (×per skill)
      Norm-->>API: normalized skills with canonical_id
      API->>Redis: normalization_done (complete)
    end

    rect rgb(255,248,220)
      note over API: Phase 8 — Mastery Scoring
      API->>Redis: mastery_scoring_start (start)
      API->>LLM2: Batch: classify context_depth evidence for all skills
      LLM2-->>API: reasoning stream_chunk×N → Redis
      LLM2-->>API: content stream_chunk×N → Redis
      LLM2-->>API: Final JSON array
      API->>Redis: skill_mastery_computed (log, ×per skill)
      API->>Redis: mastery_scoring_done (result)
    end

    rect rgb(255,240,245)
      note over API: Phase 9 — Gap Analysis (pure math)
      API->>DB: fetch target_skills for role_id
      DB-->>API: [{skill, tier, target_mastery}]
      API->>Redis: gap_analysis_start (start)
      note over API: gap = max(0, target − current)\npriority = tier_weight × gap
      API->>Redis: skill_gap_computed (log, ×per target skill)
      API->>Redis: gap_analysis_done (result)
    end

    rect rgb(245,240,255)
      note over API: Phase 10A — Dependency Resolution
      API->>Dep: resolve_dependencies(gap_skills)
      Dep->>DB: Query Neo4j REQUIRES/BUILDS_ON/LEADS_TO edges
      Dep->>LLM3: Order skills into stages (thinking ON)
      LLM3-->>Dep: stream_chunk×N → Redis
      LLM3-->>Dep: DAG JSON {stages, dependency_edges}
      Dep-->>API: ordered stages
      API->>Redis: dependency_ready (result)
    end

    rect rgb(245,255,240)
      note over API: Phase 10B — NSGA-II Course Selection
      API->>NSGA: generate_paths(stages, gaps)
      API->>Redis: nsga_start (start)
      loop For each gap skill
        NSGA->>Qdrant2: embed skill (2048d NemoRetriever)\nsearch courses_listed top-30
        Qdrant2-->>NSGA: course candidates with scores
        note over NSGA: NSGA-II 4-objective Pareto\n40 gen, pop=30\nf1=relevance f2=speed f3=quality f4=difficulty
        NSGA->>NSGA: pick_three → Sprint / Balanced / Quality
        API->>Redis: nsga_gap_done (progress)
      end
      API->>Redis: paths_ready (result)
    end

    rect rgb(255,245,235)
      note over API: Phase 11 — Journey Narration
      API->>LLM4: paths + gaps → validate + narrate + tree JSON
      LLM4-->>API: reasoning stream_chunk×N → Redis
      LLM4-->>API: content stream_chunk×N → Redis
      LLM4-->>API: Final journey JSON
      API->>Redis: narrator_start → narrator_llm_stream×N → journey_ready
    end

    API->>DB: persist EmployeeMastery + journey (fire-and-forget)
    API->>Redis: employee_persist_done (db/complete)
```

---

## 📊 5. NSGA-II Course Selection (Detailed)

NSGA-II (Non-dominated Sorting Genetic Algorithm II) is used to select the best 1-course representative from a pool of up to 30 Qdrant-retrieved candidates for each skill gap.

**4 Objectives (all minimised):**

| Objective | Field | Meaning |
|---|---|---|
| `f1` | `-relevance_score` | Qdrant similarity — higher is better |
| `f2` | `duration_weeks` | Time to complete — faster is better |
| `f3` | `-(quality × popularity)` | Course quality and social proof |
| `f4` | `\|difficulty − required_level\|` | Perfect difficulty match |

**Three path archetypes:**

| Track | Selection Rule |
|---|---|
| Sprint | Candidate with lowest `f2` (fastest) on Pareto front |
| Balanced | Candidate closest to geometric centre of Pareto front |
| Quality | Candidate with lowest `f3` (highest quality×popularity) |

**Qdrant `courses_listed` collection:** 2048-dim vectors using `nvidia/nv-embedqa-e5-v5` (NemoRetriever). Schema per point: `{title, provider, duration_weeks, difficulty_level, quality_score, popularity}`.

---

## 🌳 6. Journey Tree Structure (Phase 11 Output)

The journey narration phase outputs a tree JSON consumed by the frontend bubble-tree renderer:

```
root (role goal)
  └── main_branch (skill gap, e.g. "Apache Kafka")
        ├── course_options: {sprint, balanced, quality}
        └── twig (prerequisite skill, e.g. "Python")
              └── course_options: {sprint, balanced, quality}
```

Node types and visual rules:
| node type | size | border colour |
|---|---|---|
| `role_goal` | large | blue |
| `main_branch` — critical gap | medium | `#EF4444` (red) |
| `main_branch` — moderate gap | medium | `#F59E0B` (amber) |
| `main_branch` — minor gap | medium | `#3B82F6` (blue) |
| `twig` | small | grey |

---

## 🔬 7. Machine Learning Pipeline (`machine_learning/`)

| Notebook | Status | Purpose |
|---|---|---|
| `01_data_exploration.ipynb` | ✅ Done | Profile O*NET taxonomy; identify key fields. |
| `02_data_preparation.ipynb` | ✅ Done | Export `resume_evidence.jsonl` + `jd_requirements.jsonl` (~2 k pairs). |
| `03_synthetic_pair_generation.ipynb` | 🔜 Next | LLM-augment to ~20 k skill context pairs. |
| `04_model_training.ipynb` | 🔜 Pending | Fine-tune `intfloat/multilingual-e5-small` on synthetic pairs (Kaggle GPU). |

**Goal:** Replace the current general-purpose 384-dim embedding model in `embedding_client.py` with a domain-specific model that understands resume/JD language for more accurate O*NET matching.
