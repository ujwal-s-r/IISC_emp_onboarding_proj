# AdaptIQ — Employee Flow: Redis Event Schema

This document defines **every** event emitted to Redis during the complete Employee Onboarding Flow (Phases 6–11).  
The frontend subscribes to `channel:{role_id}` and renders each event accordingly.

> **Model roles (as at March 2026)**
> | Role | Model | Thinking |
> |---|---|---|
> | Phase 6 — Resume extraction | `stepfun-ai/step-3.5-flash` | OFF — full JSON in `content` |
> | Phase 7 — O\*NET judge/coining | `openai/gpt-oss-20b` | OFF — returns `1`/`2`/`3`/`NONE` only in `content` |
> | Phase 8 — Mastery scoring | `openai/gpt-oss-20b` | **ON** — CoT trace in `reasoning_content`, final JSON array in `content` |
> | Phase 10 — Dependency resolution | `openai/gpt-oss-20b` | **ON** — DAG JSON in `content` |
> | Phase 11 — Journey narration | `openai/gpt-oss-20b` | **ON** — tree + narrative JSON in `content` |

> **Critical fix (March 2026):** `NvidiaLLMClient.complete()` now returns **only** `content`, never `reasoning + content` concatenated. This prevents the LLM's thinking trace from leaking into coined canonical skill names.

---

## Standard Event Envelope

```json
{
  "role_id":   "uuid-string",
  "phase":     "resume_extraction | normalization | mastery | gap | path | journey | db",
  "type":      "start | log | stream_chunk | stream_end | decision | result | complete | progress | error",
  "step":      "machine_readable_snake_case",
  "message":   "Human-readable status line",
  "model":     "stepfun-ai/step-3.5-flash | openai/gpt-oss-20b | null",
  "data":      { }
}
```

---

## Phase 6: `resume_extraction`

### 1. PDF Parsing Starts (immediately on upload)
```json
{
  "phase": "resume_extraction", "type": "start",
  "step": "pdf_parsing",
  "message": "Parsing uploaded Resume PDF — skill extraction will start immediately after",
  "model": null,
  "data": {}
}
```

### 2. PDF Parsed
```json
{
  "phase": "resume_extraction", "type": "log",
  "step": "pdf_parsed",
  "message": "Resume PDF parsed successfully",
  "model": null,
  "data": {
    "resume_char_count": 4812,
    "resume_preview": "Experienced Data Engineer with 5 years..."
  }
}
```

### 3. LLM Extraction Started
```json
{
  "phase": "resume_extraction", "type": "log",
  "step": "llm_extraction_start",
  "message": "Sending Resume to LLM for skill and context extraction",
  "model": "stepfun-ai/step-3.5-flash",
  "data": {}
}
```

### 4. LLM Streaming (repeats per token chunk)
```json
{
  "phase": "resume_extraction", "type": "stream_chunk",
  "step": "llm_extraction_streaming",
  "message": "",
  "model": "stepfun-ai/step-3.5-flash",
  "data": { "chunk_type": "content", "text": "[{\"skill_name\": \"Python" }
}
```

### 5. LLM Stream Complete
```json
{
  "phase": "resume_extraction", "type": "stream_end",
  "step": "llm_extraction_streaming",
  "message": "Stream complete",
  "model": "stepfun-ai/step-3.5-flash",
  "data": { "reasoning_length": 0, "content_length": 1240 }
}
```

### 6. Extraction Result
```json
{
  "phase": "resume_extraction", "type": "result",
  "step": "llm_extraction_done",
  "message": "LLM extracted 20 raw skills from Resume",
  "model": "stepfun-ai/step-3.5-flash",
  "data": {
    "raw_count": 20,
    "skills": [
      { "skill_name": "Python", "context_depth": "Led development of 12 production microservices processing 2M req/day" },
      { "skill_name": "Apache Spark", "context_depth": "Architected PySpark ETL reducing runtime from 4h to 45min on 10TB" }
    ]
  }
}
```

---

## Phase 7: `normalization`

Runs **sequentially per skill** (no batching). For each skill: embed → Qdrant vector search → LLM judge → decision.

> **Note:** `gpt-oss-20b` judge/coining uses `complete()` which returns **only** `content`. The CoT reasoning trace is discarded. This prevents prompt echoing in coined names.

### 7.1 Normalization Starts
```json
{
  "phase": "normalization", "type": "start",
  "step": "normalization_start",
  "message": "Starting O*NET normalization for 20 employee skills",
  "model": null, "data": {}
}
```

### 7.2 Per-Skill: Qdrant Query *(fires once per skill)*
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_query",
  "message": "Querying Qdrant for 'PySpark'",
  "model": null,
  "data": { "raw_skill": "PySpark" }
}
```

### 7.3 Per-Skill: Qdrant Results *(fires once per skill)*
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_results",
  "message": "Qdrant returned 3 candidates for 'PySpark'",
  "model": null,
  "data": {
    "raw_skill": "PySpark",
    "top_candidates": [
      { "rank": 1, "name": "PySpark",       "canonical_id": "TECH_pyspark",       "score": 0.921 },
      { "rank": 2, "name": "Apache Spark",  "canonical_id": "TECH_apache_spark",  "score": 0.878 },
      { "rank": 3, "name": "Dask",          "canonical_id": "TECH_dask",          "score": 0.762 }
    ]
  }
}
```

### 7.4a Per-Skill: No Qdrant candidates *(fires if score < 0.50 for all)*
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_no_match",
  "message": "No O*NET candidates found for 'LoRA'. LLM will coin a name.",
  "model": null, "data": { "raw_skill": "LoRA" }
}
```

### 7.4b Per-Skill: LLM Judge NONE *(fires when candidates exist but LLM says none fit)*
```json
{
  "phase": "normalization", "type": "log",
  "step": "llm_judge_none",
  "message": "LLM decided no O*NET match for 'Multi-Agent Systems'",
  "model": null, "data": { "raw_skill": "Multi-Agent Systems", "llm_raw_reply": "NONE" }
}
```

### 7.5a Per-Skill: O*NET Match Confirmed
```json
{
  "phase": "normalization", "type": "decision",
  "step": "llm_judge",
  "message": "LLM resolved 'PySpark' → 'PySpark'",
  "model": "openai/gpt-oss-20b",
  "data": {
    "raw_skill":        "PySpark",
    "llm_raw_reply":    "1",
    "chosen_candidate": 1,
    "matched_name":     "PySpark",
    "canonical_id":     "TECH_pyspark",
    "source":           "onet_match"
  }
}
```

### 7.5b Per-Skill: New Skill Coined
A new canonical node is **created in both Qdrant and Neo4j** after this event.
```json
{
  "phase": "normalization", "type": "decision",
  "step": "llm_coined",
  "message": "New skill coined: 'Multi-Agent Orchestration'",
  "model": "openai/gpt-oss-20b",
  "data": {
    "raw_skill":     "Multi-Agent Systems",
    "llm_raw_reply": "Multi-Agent Orchestration",
    "coined_name":   "Multi-Agent Orchestration",
    "canonical_id":  "TECH_multi_agent_orchestration",
    "source":        "llm_new"
  }
}
```

### 7.6 Normalization Complete
```json
{
  "phase": "normalization", "type": "complete",
  "step": "normalization_done",
  "message": "11/20 skills matched to O*NET. 9 coined.",
  "model": null,
  "data": { "matched": 11, "coined": 9, "total": 20 }
}
```

---

## Phase 8: `mastery`

> **Model**: `openai/gpt-oss-20b` with `thinking: True`.  
> `reasoning_content` = long CoT trace (the model's internal deliberation). `content` = final JSON array.  
> Both use **separate token budgets** (max 24 576 total) — no truncation risk.  
> Mandatory downgrade rules: "familiar with" → basic; skills-section-only → surface.  
> Upgrade signals: hard metrics + ownership → raise one level.

### 8.1 Mastery Scoring Start
```json
{
  "phase": "mastery", "type": "start",
  "step": "mastery_scoring_start",
  "message": "Scoring current mastery for 20 skills via LLM",
  "model": "openai/gpt-oss-20b",
  "data": {
    "formula": {
      "description": "current_mastery = depth_score(context_depth_evidence)",
      "depth_scale": { "expert": 0.90, "advanced": 0.70, "intermediate": 0.50, "basic": 0.25, "surface": 0.10 },
      "note": "LLM classifies evidence; score is deterministic from that level"
    }
  }
}
```

### 8.2 LLM Streaming — CoT Reasoning *(fires many times, dim grey in UI)*
```json
{
  "phase": "mastery", "type": "stream_chunk",
  "step": "mastery_scoring_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "reasoning", "text": "PySpark: built large-scale ELT at Maersk, no explicit metrics but scale is implied..." }
}
```

### 8.3 LLM Streaming — JSON Content *(fires many times)*
```json
{
  "phase": "mastery", "type": "stream_chunk",
  "step": "mastery_scoring_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "content", "text": "[{\"skill_name\": \"PySpark\"" }
}
```

### 8.4 Stream End
```json
{
  "phase": "mastery", "type": "stream_end",
  "step": "mastery_scoring_streaming",
  "message": "Stream complete",
  "model": "openai/gpt-oss-20b",
  "data": { "reasoning_length": 6400, "content_length": 2100 }
}
```

### 8.5 Per-Skill Score Log *(fires once per skill)*
```json
{
  "phase": "mastery", "type": "log",
  "step": "skill_mastery_computed",
  "message": "Mastery 'PySpark': 0.70 (advanced)",
  "model": null,
  "data": {
    "skill_name":      "PySpark",
    "canonical_id":    "TECH_pyspark",
    "depth_level":     "advanced",
    "current_mastery": 0.70,
    "reasoning":       "Built large-scale ELT pipelines in production at Maersk — independent ownership without explicit metrics."
  }
}
```

### 8.6 Mastery Result
Fires once with the full scored array. Also includes the first 600 chars of the CoT trace for frontend visibility.
```json
{
  "phase": "mastery", "type": "result",
  "step": "mastery_scoring_done",
  "message": "Current mastery computed for 20 skills",
  "model": "openai/gpt-oss-20b",
  "data": {
    "reasoning_summary": "PySpark: built large-scale ELT at Maersk... Transformers: 60→95% accuracy improvement, expert candidate...",
    "skills": [
      { "skill_name": "Transformers",          "depth_level": "expert",    "current_mastery": 0.90, "canonical_id": "TECH_transformers",  "reasoning": "Hard metric (60→95%) + ownership → upgraded to expert." },
      { "skill_name": "PySpark",               "depth_level": "advanced",  "current_mastery": 0.70, "canonical_id": "TECH_pyspark",       "reasoning": "Production ELT, independent ownership." },
      { "skill_name": "Multi-Agent Systems",   "depth_level": "advanced",  "current_mastery": 0.70, "canonical_id": "TECH_multi_agent_orchestration", "reasoning": "Designed architecture, no hard metrics." },
      { "skill_name": "PyTorch",               "depth_level": "surface",   "current_mastery": 0.10, "canonical_id": "TECH_pytorch",       "reasoning": "Surface mention — listed in skills section only." }
    ]
  }
}
```

---

## Phase 9: `gap`

> **Pure deterministic math — no LLM call.**  
> Input: `mastery_skills` (employee actual) vs `target_skills` (role required, fetched from SQLite).  
> `gap = max(0, target_mastery − current_mastery)`  
> `priority_score = tier_weight × gap` where `T1=1.0 | T2=0.7 | T3=0.4 | T4=0.1`

### 9.1 Gap Analysis Start
```json
{
  "phase": "gap", "type": "start",
  "step": "gap_analysis_start",
  "message": "Starting gap analysis: 20 employee skills vs 8 role targets",
  "model": null,
  "data": {
    "formula": {
      "description":            "gap = max(0, target_mastery - current_mastery)",
      "priority_score_formula": "priority_score = tier_weight × gap",
      "tier_weights":           { "T1": 1.0, "T2": 0.7, "T3": 0.4, "T4": 0.1 },
      "depth_scale":            { "expert": 0.90, "advanced": 0.70, "intermediate": 0.50, "basic": 0.25, "surface": 0.10 },
      "gap_categories": {
        "critical": "gap ≥ 0.50 — urgent training required",
        "moderate": "gap 0.25–0.49 — targeted upskilling recommended",
        "minor":    "gap 0.05–0.24 — small refinement needed",
        "met":      "gap < 0.05 — employee meets or exceeds target"
      }
    }
  }
}
```

### 9.2 Per-Skill Gap Log *(fires once per role target skill)*
Gaps are computed by matching employee skills against role targets via `canonical_id` first, then `skill_name` fuzzy fallback.
```json
{
  "phase": "gap", "type": "log",
  "step": "skill_gap_computed",
  "message": "Gap 'Apache Kafka': 0.700 (critical)  priority=0.700",
  "model": null,
  "data": {
    "skill_name":           "Apache Kafka",
    "canonical_id":         "TECH_kafka",
    "tier":                 "T1",
    "target_mastery":       0.70,
    "current_mastery":      0.00,
    "gap":                  0.700,
    "gap_category":         "critical",
    "tier_weight":          1.0,
    "priority_score":       0.700,
    "assessment_reasoning": "Skill absent from resume"
  }
}
```

### 9.3 Gap Analysis Result
Sorted by `priority_score` descending.
```json
{
  "phase": "gap", "type": "result",
  "step": "gap_analysis_done",
  "message": "Gap analysis complete: 2 critical, 1 moderate, 3 minor, 2 met",
  "model": null,
  "data": {
    "summary": { "critical": 2, "moderate": 1, "minor": 3, "met": 2 },
    "ranked_gaps": [
      {
        "skill_name": "Apache Kafka", "tier": "T1",
        "target_mastery": 0.70, "current_mastery": 0.00,
        "gap": 0.700, "gap_category": "critical",
        "tier_weight": 1.0, "priority_score": 0.700,
        "assessment_reasoning": "Skill absent from resume"
      }
    ]
  }
}
```

---

## Phase 10: `path`

> **Two sub-steps:** (A) Dependency Resolution via Neo4j + `gpt-oss-20b` thinking → DAG of stages. (B) NSGA-II 4-objective Pareto optimisation → 3 course tracks per gap.

### 10.1 Dependency Resolution Start
```json
{
  "phase": "path", "type": "start",
  "step": "dependency_start",
  "message": "Resolving skill prerequisite order for 5 gaps",
  "model": "openai/gpt-oss-20b", "data": {}
}
```

### 10.2 Graph Query Log
```json
{
  "phase": "path", "type": "log",
  "step": "graph_query",
  "message": "Querying Neo4j for skill prerequisite edges",
  "model": null,
  "data": { "skill_names": ["Apache Kafka", "Docker", "Python"], "edges_found": 2 }
}
```

### 10.3 DAG LLM Streaming *(reasoning + content)*
```json
{
  "phase": "path", "type": "stream_chunk",
  "step": "dependency_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "reasoning", "text": "Python must precede Kafka as a foundational skill..." }
}
```

### 10.4 Dependency Ready
```json
{
  "phase": "path", "type": "result",
  "step": "dependency_ready",
  "message": "Dependency DAG resolved — 3 ordered stages",
  "model": "openai/gpt-oss-20b",
  "data": {
    "stages": [
      { "stage": 1, "skills": ["Python", "Docker"], "rationale": "Foundational — no cross-dependencies." },
      { "stage": 2, "skills": ["Apache Kafka"],    "rationale": "Requires distributed systems understanding." }
    ],
    "dependency_edges": [
      { "from": "Python", "to": "Apache Kafka", "type": "PREREQUISITE" }
    ]
  }
}
```

### 10.5 NSGA-II Course Selection Start
```json
{
  "phase": "path", "type": "start",
  "step": "nsga_start",
  "message": "Starting NSGA-II course selection across 3 stage(s)",
  "model": null,
  "data": { "total_stages": 3, "algorithm": "NSGA-II 4-objective Pareto" }
}
```

### 10.6 Per-Gap Course Selection *(fires once per gap)*
For each gap: embed skill name → search `courses_listed` Qdrant collection (top-30) → NSGA-II (40 generations, 4 objectives) → pick Sprint / Balanced / Quality representative.
```json
{
  "phase": "path", "type": "progress",
  "step": "nsga_gap_done",
  "message": "Stage 1: courses selected for 'Apache Kafka'",
  "model": null,
  "data": {
    "stage":          1,
    "skill":          "Apache Kafka",
    "gap_category":   "critical",
    "required_level": 3,
    "candidates":     28,
    "pareto_front":   9,
    "sprint_title":   "Apache Kafka Fundamentals — Quick Start",
    "balanced_title": "Kafka for Developers: Core to Streams API",
    "quality_title":  "Complete Apache Kafka Series — From Beginner to Expert"
  }
}
```

### 10.7 All Paths Ready
```json
{
  "phase": "path", "type": "result",
  "step": "paths_ready",
  "message": "All 3 learning paths generated",
  "model": null,
  "data": {
    "sprint":                { "total_weeks": 4.5, "coverage_score": 0.81 },
    "balanced":              { "total_weeks": 9.0, "coverage_score": 0.87 },
    "quality":               { "total_weeks": 14.5, "coverage_score": 0.93 },
    "total_skills_planned":  5
  }
}
```

---

## Phase 11: `journey`

> Final LLM pass using `gpt-oss-20b` thinking ON. Validates paths, writes HR-readable narratives, builds the visualization tree JSON for the frontend bubble-tree renderer.

### 11.1 Journey Narration Start
```json
{
  "phase": "journey", "type": "start",
  "step": "narrator_start",
  "message": "Building final learning journey and visualization tree",
  "model": "openai/gpt-oss-20b", "data": {}
}
```

### 11.2 LLM Streaming *(reasoning + content)*
```json
{
  "phase": "journey", "type": "stream_chunk",
  "step": "narrator_llm_stream",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "content", "text": "{\n  \"validation\": {\"sprint_ok\": true" }
}
```

### 11.3 Stream End
```json
{
  "phase": "journey", "type": "stream_end",
  "step": "narrator_llm_stream",
  "message": "Stream complete",
  "model": "openai/gpt-oss-20b", "data": {}
}
```

### 11.4 Journey Ready
```json
{
  "phase": "journey", "type": "result",
  "step": "journey_ready",
  "message": "Learning journey complete — 3 paths available",
  "model": "openai/gpt-oss-20b",
  "data": {
    "validation":    { "sprint_ok": true, "balanced_ok": true, "quality_ok": true, "notes": "All paths are coherent." },
    "narratives": {
      "sprint":   "Fast-track to Data Engineer readiness in 4.5 weeks by focusing on the highest-priority Kafka and Docker gaps. Designed for candidates who need to contribute immediately.",
      "balanced": "A 9-week structured programme that blends speed with comprehensive coverage, ensuring both technical depth and breadth.",
      "quality":  "A 14-week deep-dive programme that builds true expert-level mastery through in-depth courses and hands-on projects."
    },
    "path_summaries": {
      "sprint":   { "total_weeks": 4.5,  "coverage_score": 0.81, "label": "Sprint Track" },
      "balanced": { "total_weeks": 9.0,  "coverage_score": 0.87, "label": "Balanced Track" },
      "quality":  { "total_weeks": 14.5, "coverage_score": 0.93, "label": "Quality Track" }
    },
    "tree": {
      "root": {
        "id": "root", "type": "role_goal", "label": "Data Engineer", "size": "large",
        "children": [
          {
            "id": "skill_kafka", "type": "main_branch", "label": "Apache Kafka",
            "severity": "critical", "border_color": "#EF4444", "stage": 1, "gap": 0.70,
            "course_options": {
              "sprint":   { "title": "Apache Kafka Fundamentals — Quick Start",         "weeks": 1.5 },
              "balanced": { "title": "Kafka for Developers: Core to Streams API",       "weeks": 3.0 },
              "quality":  { "title": "Complete Apache Kafka Series — Beginner to Expert", "weeks": 5.0 }
            },
            "children": [
              { "id": "twig_python", "type": "twig", "label": "Python", "size": "small", "depends_on": "Apache Kafka" }
            ]
          }
        ]
      }
    }
  }
}
```

---

## Final: `db`

### Pipeline Close
Fires after all phases complete. DB writes for mastery and journey are fire-and-forget via `asyncio.ensure_future`, so this event fires immediately.
```json
{
  "phase": "db", "type": "complete",
  "step": "employee_persist_done",
  "message": "Employee analysis complete",
  "model": null,
  "data": {
    "total_skills":  20,
    "mastery_count": 20,
    "gap_summary":   { "critical": 2, "moderate": 1, "minor": 3, "met": 2 },
    "learning_paths": {
      "sprint_weeks":   4.5,
      "balanced_weeks": 9.0,
      "quality_weeks":  14.5
    }
  }
}
```

---

## Complete Event Timeline (all 11 phases, in order)

```
 POST /employee/onboard-path
   ↓
 [Ph 6]  resume_extraction / start         / pdf_parsing
         resume_extraction / log           / pdf_parsed
         resume_extraction / log           / llm_extraction_start
         resume_extraction / stream_chunk  / llm_extraction_streaming   (×N content tokens)
         resume_extraction / stream_end    / llm_extraction_streaming
         resume_extraction / result        / llm_extraction_done
   ↓
 [Ph 7]  normalization     / start         / normalization_start
         normalization     / log           / qdrant_query               (×per skill)
         normalization     / log           / qdrant_results             (×per skill)
         normalization     / log           / qdrant_no_match            (if no hits)
         normalization     / log           / llm_judge_none             (if judge says NONE)
         normalization     / decision      / llm_judge                  (onet_match)
         normalization     / decision      / llm_coined                 (new skill)
         normalization     / complete      / normalization_done
   ↓
 [Ph 8]  mastery           / start         / mastery_scoring_start
         mastery           / stream_chunk  / mastery_scoring_streaming  (×N reasoning chunks)
         mastery           / stream_chunk  / mastery_scoring_streaming  (×N content chunks)
         mastery           / stream_end    / mastery_scoring_streaming
         mastery           / log           / skill_mastery_computed     (×per skill)
         mastery           / result        / mastery_scoring_done
   ↓
 [Ph 9]  gap               / start         / gap_analysis_start
         gap               / log           / skill_gap_computed         (×per target skill)
         gap               / result        / gap_analysis_done
   ↓
 [Ph 10] path              / start         / dependency_start
         path              / log           / graph_query
         path              / stream_chunk  / dependency_streaming       (×N reasoning+content)
         path              / result        / dependency_ready
         path              / start         / nsga_start
         path              / progress      / nsga_gap_done              (×per gap skill)
         path              / result        / paths_ready
   ↓
 [Ph 11] journey           / start         / narrator_start
         journey           / stream_chunk  / narrator_llm_stream        (×N reasoning+content)
         journey           / stream_end    / narrator_llm_stream
         journey           / result        / journey_ready
   ↓
         db                / complete      / employee_persist_done
```
