# AdaptIQ — Employee Flow: Redis Event Schema

This document defines every event emitted to Redis during the Employee Onboarding Flow.  
The frontend subscribes to `channel:{employee_id}` (per upload session) and renders each event accordingly.

> **Model roles (as at March 2026)**
> | Role | Model | Thinking |
> |---|---|---|
> | Resume extraction | `stepfun-ai/step-3.5-flash` | OFF |
> | Mastery scoring | `openai/gpt-oss-20b` | **ON** — reasoning in `reasoning_content`, answer in `content` |
> | O*NET judge/coining | `openai/gpt-oss-20b` | OFF |

---

## Standard Event Envelope

```json
{
  "role_id":   "uuid-string",
  "phase":     "resume_extraction | normalization | mastery | gap | db",
  "type":      "start | log | stream_chunk | stream_end | decision | result | complete | error",
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

### 1. Normalization Starts
```json
{
  "phase": "normalization", "type": "start",
  "step": "normalization_start",
  "message": "Starting O*NET normalization for 20 employee skills",
  "model": null,
  "data": {}
}
```

### 2. Per-Skill: Qdrant Query (one per skill)
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_query",
  "message": "Querying Qdrant for 'PySpark'",
  "model": null,
  "data": {}
}
```

### 3. Per-Skill: Qdrant Results
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_results",
  "message": "Qdrant returned 3 candidates for 'PySpark'",
  "model": null,
  "data": {}
}
```

### 4a. Per-Skill: O*NET Match Confirmed
```json
{
  "phase": "normalization", "type": "decision",
  "step": "llm_judge",
  "message": "LLM resolved 'PySpark' → 'Apache Spark'",
  "model": "openai/gpt-oss-20b",
  "data": {
    "raw_name":    "PySpark",
    "matched_name":"Apache Spark",
    "canonical_id":"onet_15_1252_00_spark",
    "source":      "onet_match"
  }
}
```

### 4b. Per-Skill: Coined (no O*NET match)
```json
{
  "phase": "normalization", "type": "decision",
  "step": "llm_coined",
  "message": "New skill coined: 'LangChain'",
  "model": "openai/gpt-oss-20b",
  "data": {
    "raw_name":     "LangChain",
    "coined_name":  "LangChain",
    "canonical_id": "TECH_langchain",
    "source":       "llm_new"
  }
}
```

### 5. Normalization Complete
```json
{
  "phase": "normalization", "type": "complete",
  "step": "normalization_done",
  "message": "15/20 skills matched to O*NET. 5 coined.",
  "model": null,
  "data": { "matched": 15, "coined": 5, "total": 20 }
}
```

---

## Phase 8: `mastery`

> **Model**: `openai/gpt-oss-20b` with `thinking: True`  
> The model reasons in `reasoning_content` (CoT trace) and emits the final JSON in `content`.  
> Both use separate token budgets — no truncation risk.

### 1. Mastery Scoring Starts
```json
{
  "phase": "mastery", "type": "start",
  "step": "mastery_scoring_start",
  "message": "Scoring current mastery for 20 skills via LLM",
  "model": "openai/gpt-oss-20b",
  "data": {
    "formula": {
      "description": "current_mastery = depth_score(context_depth_evidence)",
      "depth_scale": {
        "expert": 0.90, "advanced": 0.70, "intermediate": 0.50,
        "basic": 0.25, "surface": 0.10
      },
      "note": "LLM classifies evidence; score is deterministic from that level"
    }
  }
}
```

### 2. LLM Streaming — Reasoning (CoT trace, dim grey in UI)
```json
{
  "phase": "mastery", "type": "stream_chunk",
  "step": "mastery_scoring_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "reasoning", "text": "Python: led 12 microservices..." }
}
```

### 3. LLM Streaming — Content (JSON answer)
```json
{
  "phase": "mastery", "type": "stream_chunk",
  "step": "mastery_scoring_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "content", "text": "[{\"skill_name\": \"Python\"" }
}
```

### 4. Stream End
```json
{
  "phase": "mastery", "type": "stream_end",
  "step": "mastery_scoring_streaming",
  "message": "Stream complete",
  "model": "openai/gpt-oss-20b",
  "data": { "reasoning_length": 4200, "content_length": 1800 }
}
```

### 5. Per-Skill Score Log (one per skill)
```json
{
  "phase": "mastery", "type": "log",
  "step": "skill_mastery_computed",
  "message": "Mastery 'Python': 0.90 (expert)",
  "model": null,
  "data": {
    "skill_name":      "Python",
    "canonical_id":    "TECH_python",
    "depth_level":     "expert",
    "current_mastery": 0.90,
    "reasoning":       "Led 12 production microservices with 2M req/day — architectural ownership with hard metrics."
  }
}
```

### 6. Mastery Result (all skills)
```json
{
  "phase": "mastery", "type": "result",
  "step": "mastery_scoring_done",
  "message": "Current mastery computed for 20 skills",
  "model": "openai/gpt-oss-20b",
  "data": {
    "reasoning_summary": "First 600 chars of CoT trace...",
    "skills": [
      { "skill_name": "Python",        "depth_level": "expert",       "current_mastery": 0.90, "canonical_id": "TECH_python",  "reasoning": "Led 12 microservices at 2M req/day." },
      { "skill_name": "Apache Spark",  "depth_level": "expert",       "current_mastery": 0.90, "canonical_id": "TECH_spark",   "reasoning": "Architected PySpark ETL with 90% runtime reduction." },
      { "skill_name": "Docker",        "depth_level": "intermediate",  "current_mastery": 0.50, "canonical_id": "TECH_docker",  "reasoning": "Wrote Dockerfiles for team deployment in production." },
      { "skill_name": "Kubernetes",    "depth_level": "surface",       "current_mastery": 0.10, "canonical_id": "TECH_k8s",    "reasoning": "Keyword only — no usage context." }
    ]
  }
}
```

---

## Phase 9: `gap`

> Pure deterministic math — no LLM call.  
> Formula: `gap = max(0, target_mastery − current_mastery)`  
> `priority_score = tier_weight × gap` where `T1=1.0 | T2=0.7 | T3=0.4 | T4=0.1`

### 1. Gap Analysis Starts
```json
{
  "phase": "gap", "type": "start",
  "step": "gap_analysis_start",
  "message": "Starting gap analysis: 20 employee skills vs 18 role targets",
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

### 2. Per-Skill Gap Log (one per target skill)
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

### 3. Gap Analysis Result (all skills, ranked by priority)
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
      },
      {
        "skill_name": "Kubernetes", "tier": "T2",
        "target_mastery": 0.70, "current_mastery": 0.10,
        "gap": 0.600, "gap_category": "critical",
        "tier_weight": 0.7, "priority_score": 0.420,
        "assessment_reasoning": "Keyword-only listing with zero usage context."
      }
    ]
  }
}
```

---

## Final: `db`

### Pipeline Close
```json
{
  "phase": "db", "type": "complete",
  "step": "employee_persist_done",
  "message": "Employee analysis complete",
  "model": null,
  "data": {
    "total_skills":  20,
    "mastery_count": 20,
    "gap_summary": { "critical": 2, "moderate": 1, "minor": 3, "met": 2 }
  }
}
```

---

## Full Event Sequence (timeline order)

```
upload → resume_extraction/start/pdf_parsing
       → resume_extraction/log/pdf_parsed
       → resume_extraction/log/llm_extraction_start
       → resume_extraction/stream_chunk/llm_extraction_streaming  (×N)
       → resume_extraction/stream_end/llm_extraction_streaming
       → resume_extraction/result/llm_extraction_done
       → normalization/start/normalization_start
       → normalization/log/qdrant_query                           (×skills)
       → normalization/log/qdrant_results                         (×skills)
       → normalization/decision/llm_judge OR llm_coined           (×skills)
       → normalization/complete/normalization_done
       → mastery/start/mastery_scoring_start
       → mastery/stream_chunk/mastery_scoring_streaming            (×N — reasoning)
       → mastery/stream_chunk/mastery_scoring_streaming            (×N — content)
       → mastery/stream_end/mastery_scoring_streaming
       → mastery/log/skill_mastery_computed                        (×skills)
       → mastery/result/mastery_scoring_done
       → gap/start/gap_analysis_start
       → gap/log/skill_gap_computed                                (×target skills)
       → gap/result/gap_analysis_done
       → db/complete/employee_persist_done
```
