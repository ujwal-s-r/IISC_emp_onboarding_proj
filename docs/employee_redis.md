# AdaptIQ — Employee Flow: Redis Event Schema
### Frontend Integration Contract — March 2026

This document defines **every** Redis event emitted during the complete Employee Onboarding Flow (Phases 6–11).
The frontend subscribes to `channel:{role_id}` via WebSocket and renders each event as it arrives.

> The employer flow (`jd_extraction`, `normalization`, `team_context`, `mastery`) is documented separately in `employer_redis.md`.

---

## Model Reference

| Phase | Model | Thinking Mode |
|---|---|---|
| Phase 6 — Resume extraction | `qwen/qwen3.5-122b-a10b` | **ON** — CoT in `reasoning_content`, JSON answer in `content` |
| Phase 7 — O\*NET normalization judge | `openai/gpt-oss-20b` | OFF — returns `1`/`2`/`3`/`NONE` only |
| Phase 8 — Mastery scoring | `openai/gpt-oss-20b` | **ON** — CoT trace + final JSON array |
| Phase 10A — Dependency resolution | `openai/gpt-oss-20b` | **ON** — DAG JSON in content |
| Phase 11 — Journey narration | `qwen/qwen3.5-122b-a10b` | **ON** — tree + narrative JSON |

---

## Standard Event Envelope

Every Redis message is a JSON string with this outer shape:

```json
{
  "role_id":   "uuid-string",
  "phase":     "resume_extraction | normalization | mastery | gap | dependency | path | journey | db",
  "type":      "start | log | stream_chunk | stream_end | decision | result | complete | progress",
  "step":      "machine_readable_snake_case",
  "message":   "Human-readable status line for the UI status bar",
  "model":     "qwen/qwen3.5-122b-a10b | openai/gpt-oss-20b | null",
  "data":      { }
}
```

---

## Phase 6: `resume_extraction`

Triggered immediately when `POST /api/v1/employee/onboard-path` is received.
Uses `qwen/qwen3.5-122b-a10b` with thinking ON — reasoning trace arrives before the JSON answer.

### 6.1 PDF Parsing Start
```json
{
  "phase": "resume_extraction", "type": "start",
  "step": "pdf_parsing",
  "message": "Parsing uploaded Resume PDF for employee",
  "model": null, "data": {}
}
```

### 6.2 PDF Parsed
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

### 6.3 LLM Extraction Started
```json
{
  "phase": "resume_extraction", "type": "log",
  "step": "llm_extraction_start",
  "message": "Sending Resume to LLM for skill and context extraction",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": {}
}
```

### 6.4 LLM Streaming — Reasoning *(fires many times)*
> **UI rendering:** Display in **dim grey / italic** inside the Execution Theater panel.
> These are the model's internal deliberation tokens — not the final answer.
```json
{
  "phase": "resume_extraction", "type": "stream_chunk",
  "step": "llm_extraction_streaming",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "chunk_type": "reasoning", "text": "The resume mentions PySpark in the context of a production ETL pipeline..." }
}
```

### 6.5 LLM Streaming — Content *(fires many times)*
> **UI rendering:** Display normally — this builds up the JSON answer.
```json
{
  "phase": "resume_extraction", "type": "stream_chunk",
  "step": "llm_extraction_streaming",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "chunk_type": "content", "text": "[{\"skill_name\": \"PySpark\"" }
}
```

### 6.6 Stream End
```json
{
  "phase": "resume_extraction", "type": "stream_end",
  "step": "llm_extraction_streaming",
  "message": "Stream complete",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "reasoning_length": 2400, "content_length": 1240 }
}
```

### 6.7 Extraction Result
```json
{
  "phase": "resume_extraction", "type": "result",
  "step": "llm_extraction_done",
  "message": "LLM extracted 20 raw skills from Resume",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": {
    "raw_count": 20,
    "reasoning": "Candidate demonstrates strong Python ownership with measurable production outcomes. Kubernetes is surface-only — listed in skills section with no project evidence.",
    "skills": [
      { "skill_name": "PySpark",    "context_depth": "Architected ETL pipeline reducing runtime from 4h to 45min across 10TB datasets at Maersk" },
      { "skill_name": "Kubernetes", "context_depth": "Surface mention — listed in skills section only" }
    ]
  }
}
```

---

## Phase 7: `normalization`

Runs sequentially per skill — no batching.
For each skill: embed (local 384-dim)  Qdrant `onet_skills` search  `gpt-oss-20b` judge (no thinking)  decision.

### 7.1 Normalization Start
```json
{
  "phase": "normalization", "type": "start",
  "step": "normalization_start",
  "message": "Starting O*NET normalization for 20 employee skills",
  "model": null, "data": {}
}
```

### 7.2 Qdrant Query *(fires once per skill)*
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_query",
  "message": "Querying Qdrant for 'PySpark'",
  "model": null,
  "data": { "raw_skill": "PySpark" }
}
```

### 7.3 Qdrant Results *(fires once per skill)*
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

### 7.4a No Qdrant Candidates *(fires if all scores < 0.50)*
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_no_match",
  "message": "No O*NET candidates found for 'LoRA fine-tuning'. LLM will coin a name.",
  "model": null,
  "data": { "raw_skill": "LoRA fine-tuning" }
}
```

### 7.4b LLM Judge Says NONE *(fires when candidates exist but none match)*
```json
{
  "phase": "normalization", "type": "log",
  "step": "llm_judge_none",
  "message": "LLM decided no O*NET match for 'Multi-Agent Systems'",
  "model": null,
  "data": { "raw_skill": "Multi-Agent Systems", "llm_raw_reply": "NONE" }
}
```

### 7.5a O\*NET Match Confirmed
```json
{
  "phase": "normalization", "type": "decision",
  "step": "llm_judge",
  "message": "LLM resolved 'PySpark'  'PySpark'",
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

### 7.5b New Skill Coined *(new Qdrant point + Neo4j node created after this)*
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
  "data": { "matched": 11, "coined": 9, "no_match": 9, "total": 20 }
}
```

> **UI note:** If `no_match > 3`, show a "New Skills Detected" badge — these are domain-specific skills not yet in O*NET that the system auto-added to the knowledge graph.

---

## Phase 8: `mastery`

One batch LLM call for all skills. `gpt-oss-20b` with thinking ON.
Reasoning trace arrives first (dim grey), then the full JSON array.

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
      "note": "LLM classifies evidence quality; score is deterministic from that classification"
    }
  }
}
```

### 8.2 Streaming — CoT Reasoning *(fires many times)*
> **UI rendering:** Dim grey, collapsible in Execution Theater.
```json
{
  "phase": "mastery", "type": "stream_chunk",
  "step": "mastery_scoring_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "reasoning", "text": "PySpark: ETL pipeline at scale at Maersk — this is independent production ownership..." }
}
```

### 8.3 Streaming — Content Chunks *(fires many times)*
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

### 8.5 Per-Skill Score *(fires once per skill after stream ends)*
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
    "reasoning":       "Built large-scale ELT pipelines independently in production at Maersk — ownership without explicit metrics."
  }
}
```

### 8.6 Mastery Result *(fires once)*
```json
{
  "phase": "mastery", "type": "result",
  "step": "mastery_scoring_done",
  "message": "Current mastery computed for 20 skills",
  "model": "openai/gpt-oss-20b",
  "data": {
    "reasoning_summary": "Transformers: fine-tuned on 3M records, hard metric confirms expert... PySpark: scale and ownership at Maersk...",
    "skills": [
      { "skill_name": "Transformers",        "depth_level": "expert",   "current_mastery": 0.90, "canonical_id": "TECH_transformers",             "reasoning": "Hard metric (6095% accuracy) + full ownership  expert." },
      { "skill_name": "PySpark",             "depth_level": "advanced", "current_mastery": 0.70, "canonical_id": "TECH_pyspark",                  "reasoning": "Production ETL at scale, independent ownership." },
      { "skill_name": "Kubernetes",          "depth_level": "surface",  "current_mastery": 0.10, "canonical_id": "TECH_kubernetes",               "reasoning": "Keyword-only listing in skills section." },
      { "skill_name": "Multi-Agent Orchestration", "depth_level": "advanced", "current_mastery": 0.70, "canonical_id": "TECH_multi_agent_orchestration", "reasoning": "Designed architecture but no hard metrics." }
    ]
  }
}
```

---

## Phase 9: `gap`

Pure deterministic math — no LLM call.
`gap = max(0, target_mastery  current_mastery)` | `priority_score = tier_weight  gap`
`T1=1.0 | T2=0.7 | T3=0.4 | T4=0.1`

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
      "priority_score_formula": "priority_score = tier_weight  gap",
      "tier_weights":           { "T1": 1.0, "T2": 0.7, "T3": 0.4, "T4": 0.1 },
      "gap_categories": {
        "critical": "gap  0.50",
        "moderate": "gap 0.25–0.49",
        "minor":    "gap 0.05–0.24",
        "met":      "gap < 0.05 — employee meets or exceeds target"
      }
    }
  }
}
```

### 9.2 Per-Skill Gap *(fires once per role target)*
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
```json
{
  "phase": "gap", "type": "result",
  "step": "gap_analysis_done",
  "message": "Gap analysis complete: 3 critical, 2 moderate, 1 minor, 2 met",
  "model": null,
  "data": {
    "summary": { "critical": 3, "moderate": 2, "minor": 1, "met": 2 },
    "ranked_gaps": [
      {
        "skill_name": "Apache Kafka", "canonical_id": "TECH_kafka", "tier": "T1",
        "target_mastery": 0.70, "current_mastery": 0.00,
        "gap": 0.700, "gap_category": "critical",
        "tier_weight": 1.0, "priority_score": 0.700,
        "assessment_reasoning": "Skill absent from resume"
      },
      {
        "skill_name": "Docker", "canonical_id": "TECH_docker", "tier": "T2",
        "target_mastery": 0.65, "current_mastery": 0.25,
        "gap": 0.400, "gap_category": "moderate",
        "tier_weight": 0.7, "priority_score": 0.280,
        "assessment_reasoning": "Used in a university project — basic level."
      }
    ]
  }
}
```

---

## Phase 10A: `dependency`

Neo4j graph query + `gpt-oss-20b` (thinking ON) to topologically order the gap skills into sequential learning stages.

> **Important:** This phase uses `"phase": "dependency"` in all events — not `"path"`.

### 10.1 Dependency Resolution Start
```json
{
  "phase": "dependency", "type": "start",
  "step": "dep_resolution_start",
  "message": "Resolving learning order for 5 skills",
  "model": null,
  "data": { "skills": ["Apache Kafka", "Docker", "Python", "SQL", "Kubernetes"] }
}
```

### 10.2 Graph Query Complete
```json
{
  "phase": "dependency", "type": "log",
  "step": "graph_query_done",
  "message": "Knowledge graph returned 3 dependency edges",
  "model": null,
  "data": {
    "edges": [
      { "from": "Python",  "to": "Apache Kafka", "rel_type": "REQUIRES"   },
      { "from": "Docker",  "to": "Kubernetes",   "rel_type": "REQUIRES"   },
      { "from": "SQL",     "to": "Apache Kafka", "rel_type": "BUILDS_ON"  }
    ]
  }
}
```

### 10.3 LLM DAG Streaming *(reasoning + content)*
```json
{
  "phase": "dependency", "type": "stream_chunk",
  "step": "dep_llm_stream",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "reasoning", "text": "Python must precede Kafka as it is a hard prerequisite for the Kafka Python client..." }
}
```

### 10.4 Dependency Resolution Done
```json
{
  "phase": "dependency", "type": "result",
  "step": "dep_resolution_done",
  "message": "Learning order resolved: 3 stage(s) across 5 skills",
  "model": null,
  "data": {
    "stages":           3,
    "skills_per_stage": {
      "1": ["Python", "SQL"],
      "2": ["Docker", "Apache Kafka"],
      "3": ["Kubernetes"]
    },
    "edges": 3
  }
}
```

---

## Phase 10B: `path`

NSGA-II 4-objective Pareto optimisation.
For each gap skill: embed  Qdrant `courses_listed` top-30  NSGA-II (40 gen, 4 obj)  Sprint / Balanced / Quality.

**NSGA-II Objectives (all minimised):**
| Objective | Formula | Meaning |
|---|---|---|
| `f1` | `1  cosine_similarity` | Maximise course relevance |
| `f2` | `(duration_score  1) / 3` | Minimise learning time |
| `f3` | `1  popularity_norm` | Maximise course quality / trust |
| `f4` | `|course_level  required_level| / 2` | Minimise difficulty mismatch |

### 10.5 NSGA-II Start
```json
{
  "phase": "path", "type": "start",
  "step": "nsga_start",
  "message": "Starting NSGA-II course selection across 3 stage(s)",
  "model": null,
  "data": { "total_stages": 3, "algorithm": "NSGA-II 4-objective Pareto" }
}
```

### 10.6 Per-Gap Course Selection *(fires once per gap skill)*
```json
{
  "phase": "path", "type": "progress",
  "step": "nsga_gap_done",
  "message": "Stage 1: courses selected for 'Apache Kafka'",
  "model": null,
  "data": {
    "stage":          2,
    "skill":          "Apache Kafka",
    "gap_category":   "critical",
    "required_level": 3,
    "candidates":     28,
    "pareto_front":   9,
    "sprint_title":   "Apache Kafka Fundamentals — Quick Start",
    "balanced_title": "Kafka for Developers: Core to Streams API",
    "quality_title":  "Complete Apache Kafka Series — Beginner to Expert"
  }
}
```

### 10.6b Course Search Failed *(fires instead of 10.6 if Qdrant is unreachable)*
```json
{
  "phase": "path", "type": "log",
  "step": "nsga_gap_done",
  "message": "Course search failed for 'Apache Kafka' — skipping",
  "model": null,
  "data": { "skill": "Apache Kafka", "error": "Connection refused" }
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
    "sprint":                { "total_weeks": 4.5,  "coverage_score": 0.81 },
    "balanced":              { "total_weeks": 9.0,  "coverage_score": 0.87 },
    "quality":               { "total_weeks": 14.5, "coverage_score": 0.93 },
    "total_skills_planned":  5
  }
}
```

---

## Phase 11: `journey`

Final LLM pass using `qwen/qwen3.5-122b-a10b` (thinking ON).
Validates path coherence, writes HR narratives, and builds the full visualization tree JSON.

### 11.1 Journey Narration Start
```json
{
  "phase": "journey", "type": "start",
  "step": "narrator_start",
  "message": "Building final learning journey and visualization tree",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "role": "Senior Data Engineer", "skills": 5 }
}
```

### 11.2 LLM Streaming *(reasoning + content — same pattern as Phase 8)*
```json
{
  "phase": "journey", "type": "stream_chunk",
  "step": "narrator_llm_stream",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "chunk_type": "reasoning", "text": "Sprint path puts Kafka before Python which is incorrect. I will reorder..." }
}
```

### 11.3 Stream End
```json
{
  "phase": "journey", "type": "stream_end",
  "step": "narrator_llm_stream",
  "message": "Stream complete",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": {}
}
```

### 11.4 Journey Ready  **The main event the UI renders from**

```json
{
  "phase": "journey", "type": "result",
  "step": "journey_ready",
  "message": "Learning journey complete — 3 paths available",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": {
    "validation": {
      "sprint_ok":   true,
      "balanced_ok": true,
      "quality_ok":  true,
      "notes":       "All paths are coherent."
    },
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
    "tree_nodes": 5,
    "tree": {
      "root": {
        "id": "root",
        "type": "role_goal",
        "label": "Senior Data Engineer",
        "size": "large",
        "children": [
          {
            "id": "skill_python",
            "type": "main_branch",
            "label": "Python",
            "severity": "moderate",
            "size": "medium",
            "border_color": "#F59E0B",
            "stage": 1,
            "gap": 0.35,
            "children": [],
            "course_options": {
              "sprint":   { "title": "Python Crash Course",                    "duration": "1–4 Weeks", "institution": "Coursera",    "rating": 4.7 },
              "balanced": { "title": "Python for Data Engineers",              "duration": "1–4 Weeks", "institution": "DataCamp",    "rating": 4.8 },
              "quality":  { "title": "Complete Python Bootcamp: Zero to Hero", "duration": "1–3 Months","institution": "Udemy",       "rating": 4.6 }
            }
          },
          {
            "id": "skill_apache_kafka",
            "type": "main_branch",
            "label": "Apache Kafka",
            "severity": "critical",
            "size": "medium",
            "border_color": "#EF4444",
            "stage": 2,
            "gap": 0.70,
            "children": [
              {
                "id": "twig_python",
                "type": "twig",
                "label": "Python",
                "size": "small",
                "depends_on": "Apache Kafka"
              }
            ],
            "course_options": {
              "sprint":   { "title": "Apache Kafka Fundamentals — Quick Start",         "duration": "1–4 Weeks", "institution": "Confluent", "rating": 4.5 },
              "balanced": { "title": "Kafka for Developers: Core to Streams API",       "duration": "1–3 Months","institution": "Udemy",     "rating": 4.7 },
              "quality":  { "title": "Complete Apache Kafka Series — Beginner to Expert","duration": "1–3 Months","institution": "Udemy",     "rating": 4.8 }
            }
          },
          {
            "id": "skill_docker",
            "type": "main_branch",
            "label": "Docker",
            "severity": "moderate",
            "size": "medium",
            "border_color": "#F59E0B",
            "stage": 1,
            "gap": 0.40,
            "children": [],
            "course_options": {
              "sprint":   { "title": "Docker in 1 Hour",             "duration": "1–4 Weeks", "institution": "YouTube",  "rating": 4.6 },
              "balanced": { "title": "Docker and Kubernetes Essentials","duration": "1–4 Weeks","institution": "Coursera", "rating": 4.7 },
              "quality":  { "title": "Docker Mastery",               "duration": "1–3 Months","institution": "Udemy",    "rating": 4.8 }
            }
          }
        ]
      }
    }
  }
}
```

---

## Final: `db`

Fires after all phases complete. DB writes are fire-and-forget so this fires immediately after Phase 11.

```json
{
  "phase": "db", "type": "complete",
  "step": "employee_persist_done",
  "message": "Employee analysis complete",
  "model": null,
  "data": {
    "total_skills":  20,
    "mastery_count": 20,
    "gap_summary":   { "critical": 3, "moderate": 2, "minor": 1, "met": 2 },
    "learning_paths": {
      "sprint_weeks":   4.5,
      "balanced_weeks": 9.0,
      "quality_weeks":  14.5
    }
  }
}
```

---

## Complete Event Timeline

```
 POST /employee/onboard-path
   
    [Ph 6]  resume_extraction / start         / pdf_parsing
             resume_extraction / log           / pdf_parsed
             resume_extraction / log           / llm_extraction_start
             resume_extraction / stream_chunk  / llm_extraction_streaming    loops: reasoning chunks
             resume_extraction / stream_chunk  / llm_extraction_streaming    loops: content chunks
             resume_extraction / stream_end    / llm_extraction_streaming
             resume_extraction / result        / llm_extraction_done
   
    [Ph 7]  normalization     / start         / normalization_start
             normalization     / log           / qdrant_query                loops: per skill
             normalization     / log           / qdrant_results              loops: per skill
             normalization     / log           / qdrant_no_match            (conditional — if no hits)
             normalization     / log           / llm_judge_none             (conditional — if judge says NONE)
             normalization     / decision      / llm_judge                  (onet_match path)
             normalization     / decision      / llm_coined                 (new skill path)
             normalization     / complete      / normalization_done
   
    [Ph 8]  mastery           / start         / mastery_scoring_start
             mastery           / stream_chunk  / mastery_scoring_streaming   loops: reasoning chunks
             mastery           / stream_chunk  / mastery_scoring_streaming   loops: content chunks
             mastery           / stream_end    / mastery_scoring_streaming
             mastery           / log           / skill_mastery_computed      loops: per skill
             mastery           / result        / mastery_scoring_done
   
    [Ph 9]  gap               / start         / gap_analysis_start
             gap               / log           / skill_gap_computed          loops: per target skill
             gap               / result        / gap_analysis_done
   
    [Ph 10A] dependency       / start         / dep_resolution_start
              dependency       / log           / graph_query_done
              dependency       / stream_chunk  / dep_llm_stream              loops: reasoning+content
              dependency       / stream_end    / dep_llm_stream
              dependency       / result        / dep_resolution_done
   
    [Ph 10B] path             / start         / nsga_start
              path             / progress      / nsga_gap_done               loops: per gap skill
              path             / result        / paths_ready
   
    [Ph 11] journey           / start         / narrator_start
             journey           / stream_chunk  / narrator_llm_stream         loops: reasoning+content
             journey           / stream_end    / narrator_llm_stream
             journey           / result        / journey_ready               render the tree here!
   
            db                / complete      / employee_persist_done
```

---

## Frontend Rendering Guide

### How to Subscribe

```js
// 1. Send the POST — get employee_id back immediately
const { employee_id, role_id } = await api.post("/employee/onboard-path", form);

// 2. Open WebSocket — backend proxies from Redis in real-time
const ws = new WebSocket(`wss://api/employee/ws/${role_id}`);
ws.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
```

---

### Status Bar (phase/type  message)

Show `event.message` in a one-line status bar at the top of the page.
Use `event.type` to control the icon:

| `type` | Icon |
|---|---|
| `start` |  spinner |
| `log` | ℹ info |
| `stream_chunk` | 〰 pulsing dot |
| `stream_end` |  check |
| `result` |  green check |
| `complete` |  confetti |

---

### Execution Theater Panel

Render one **collapsible card per phase** in a sidebar. Each card shows:
- Phase title, start time, model name
- A live log list of all `log` and `decision` events for that phase
- A streaming text area for `stream_chunk` events

**Stream chunk colour coding:**
```js
if (data.chunk_type === "reasoning") {
  // dim grey italic — model is thinking
  appendToPanel(<span style={{ color: "#9CA3AF", fontStyle: "italic" }}>{data.text}</span>)
} else {
  // normal — model is writing the answer
  appendToPanel(<span>{data.text}</span>)
}
```

---

### Normalization Table (Phase 7)

On each `llm_judge` or `llm_coined` decision event, append a row to a table:

| Raw Skill |  | Canonical Name | Source | Canonical ID |
|---|---|---|---|---|
| `PySpark` |  | `PySpark` |  O\*NET Match | `TECH_pyspark` |
| `Multi-Agent Systems` |  | `Multi-Agent Orchestration` |  New Coined | `TECH_multi_agent_orchestration` |

When `normalization_done` fires, show a summary badge:
```
 11 matched    9 coined    0 unresolved
```

---

### Mastery Radar / Bar Chart (Phase 8)

On `mastery_scoring_done`, render a bar chart from `data.skills`:
- X-axis: skill names
- Y-axis: `current_mastery` (0–1)
- Bar colour by `depth_level`: expert=green, advanced=teal, intermediate=yellow, basic=orange, surface=red
- Tooltip: `reasoning` field from each skill object

---

### Gap Priority List (Phase 9)

On `gap_analysis_done`, render `data.ranked_gaps` as a sorted list:
- Show `skill_name`, tier badge (`T1`/`T2`/...), gap bar (target vs current), priority score
- Colour the gap bar: critical=red, moderate=amber, minor=yellow, met=green

---

### Dependency DAG (Phase 10A)

On `dep_resolution_done`, extract `data.skills_per_stage` and render a horizontal stage diagram:
```
Stage 1: [Python] [SQL]
  
Stage 2: [Docker] [Apache Kafka]
  
Stage 3: [Kubernetes]
```

Use arrows from `dependency` graph edges to show directed prerequisites.

---

### Pareto Path Visualizer (Phase 10B)

On `paths_ready`, show three track cards side by side:

```
    
   Sprint Track          Balanced Track        Quality Track    
  4.5 weeks               9.0 weeks                14.5 weeks          
  Coverage: 81%           Coverage: 87%            Coverage: 93%       
    
```

Let the user select a track — this controls which `course_options` key to show in the tree.

---

### Career Roadmap Bubble-Tree (Phase 11 — `journey_ready`)

This is the final product rendered from `data.tree`. Use **ReactFlow**, **D3.js**, or **vis.js**.

#### Data Structure

```
journey_ready.data.tree.root
     type = "role_goal"    large central bubble, bold text
     label = "Senior Data Engineer"
  
   children[i]  (type = "main_branch")   medium bubble
       label        = skill name
       severity     = "critical" | "moderate"
       border_color = "#EF4444" (critical) | "#F59E0B" (moderate)
       stage        = 1 | 2 | 3 ...
       gap          = 0.0–1.0
       course_options.{sprint|balanced|quality}    course card data
  
   children[i].children[j]  (type = "twig")   small bubble
        label      = prerequisite skill name
        depends_on = parent main_branch skill
```

#### Node Rendering Rules

```js
function renderNode(node) {
  if (node.type === "role_goal")  return <LargeBubble label={node.label} color="#1E40AF" />
  if (node.type === "main_branch") {
    const bgColor = node.severity === "critical" ? "#FEE2E2" : "#FEF3C7"
    return <MediumBubble
      label={node.label}
      borderColor={node.border_color}
      bg={bgColor}
      badge={`Stage ${node.stage} | Gap ${(node.gap * 100).toFixed(0)}%`}
    />
  }
  if (node.type === "twig") return <SmallBubble label={node.label} color="#E5E7EB" dashed />
}
```

#### Edge Rendering Rules

- **root  main_branch**: solid thick edge, weight proportional to `gap`
- **main_branch  twig**: dashed thin edge (prerequisite dependency)

#### Course Card on Node Click

When user clicks a `main_branch` node, show a panel with the selected track's course:
```js
const selectedTrack = "sprint" | "balanced" | "quality" // from user selection
const course = node.course_options[selectedTrack]
// display: course.title, course.institution, course.duration, course.rating ()
```

#### Validation Banner

```js
if (!journey_ready.data.validation.sprint_ok) {
  showBanner(" Sprint path has coherence issues: " + journey_ready.data.validation.notes)
}
```

#### Track Narrative

Show `journey_ready.data.narratives[selectedTrack]` as a paragraph above the tree.

#### Path Summary Footer

```js
const s = journey_ready.data.path_summaries
// Sprint: 4.5w | Balanced: 9.0w | Quality: 14.5w
```

---

## Error Handling

If `event.type === "error"` is received at any phase, or if `employee_persist_done` never arrives after 5 minutes:
- Show a toast: "Analysis failed — please try again or contact support"
- Expose `event.data.error` in the console / debug panel
- The employee status in SQLite will be set to `"failed"` (safe to retry)
