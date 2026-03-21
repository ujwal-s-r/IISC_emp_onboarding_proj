# AdaptIQ — Employer Flow: Redis Event Schema

This document defines every event emitted to Redis during the Employer Setup Flow. The frontend should subscribe to `channel:{role_id}` and render each event accordingly.

---

## Standard Event Envelope

```json
{
  "role_id":   "uuid-string",
  "phase":     "jd_extraction | normalization | team_context | mastery | db",
  "type":      "start | log | decision | result | error | complete",
  "step":      "human_readable string",
  "message":   "Human-readable status line",
  "model":     "nvidia/nemotron-3-super-120b-a12b:free | openai/gpt-oss-20b | null",
  "data":      { }
}
```

---

## Phase 1: `jd_extraction`

### 1. Flow Start
```json
{
  "phase": "jd_extraction", "type": "start",
  "step": "pdf_parsing",
  "message": "Parsing uploaded PDFs",
  "data": {}
}
```

### 2. PDF Extracted
```json
{
  "phase": "jd_extraction", "type": "log",
  "step": "pdf_parsed",
  "message": "PDFs parsed successfully",
  "data": {
    "jd_char_count": 3200,
    "team_char_count": 1800,
    "jd_preview": "We are looking for a Senior Data Engineer..."
  }
}
```

### 3. LLM Skill Extraction Started
```json
{
  "phase": "jd_extraction", "type": "log",
  "step": "llm_extraction_start",
  "message": "Sending JD to LLM for skill extraction",
  "model": "nvidia/nemotron-3-super-120b-a12b:free",
  "data": {}
}
```

### 4. LLM Skill Extraction Result
```json
{
  "phase": "jd_extraction", "type": "result",
  "step": "llm_extraction_done",
  "message": "LLM extracted 8 raw skills",
  "model": "nvidia/nemotron-3-super-120b-a12b:free",
  "data": {
    "raw_count": 8,
    "reasoning": "The JD specifically mentions PySpark in the responsibilities section...",
    "skills": [
      {"skill_name": "PySpark", "jd_level": "senior", "category": "framework", "reasoning": "Listed as primary tool in the data engineering section."}
    ]
  }
}
```

---

## Phase 2: `normalization` (per skill)

### 5. Normalization Phase Start
```json
{
  "phase": "normalization", "type": "start",
  "step": "normalization_start",
  "message": "Starting O*NET normalization for 8 skills",
  "data": {}
}
```

### 6. Qdrant Query (per skill)
```json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_query",
  "message": "Querying Qdrant for 'PySpark'",
  "data": {
    "raw_skill": "PySpark",
    "top_candidates": [
      {"rank": 1, "name": "PySpark", "canonical_id": "TECH_pyspark", "score": 0.890},
      {"rank": 2, "name": "Apache Spark", "canonical_id": "TECH_apache_spark", "score": 0.821},
      {"rank": 3, "name": "Dask", "canonical_id": "TECH_dask", "score": 0.742}
    ]
  }
}
```

### 7. LLM Judge Result (per skill)
```json
{
  "phase": "normalization", "type": "decision",
  "step": "llm_judge",
  "message": "LLM judge resolved 'PySpark' → 'PySpark'",
  "model": "openai/gpt-oss-20b",
  "data": {
    "raw_skill": "PySpark",
    "llm_raw_reply": "Candidate 1 is an exact match for PySpark...",
    "chosen_candidate": 1,
    "matched_name": "PySpark",
    "canonical_id": "TECH_pyspark",
    "source": "onet_match"
  }
}
```

### 8. New Skill Coined (if no Qdrant match)
```json
{
  "phase": "normalization", "type": "decision",
  "step": "llm_coined",
  "message": "New canonical skill coined: 'Temporal Reasoning Architecture'",
  "model": "openai/gpt-oss-20b",
  "data": {
    "raw_skill": "temporal reasoning",
    "llm_raw_reply": "Temporal Reasoning Architecture",
    "coined_name": "Temporal Reasoning Architecture",
    "canonical_id": "TECH_temporal_reasoning_architecture",
    "source": "llm_new"
  }
}
```

### 9. Normalization Complete
```json
{
  "phase": "normalization", "type": "complete",
  "step": "normalization_done",
  "message": "7/8 skills matched to O*NET. 1 new skill coined.",
  "data": {
    "matched": 7,
    "coined": 1,
    "no_match": 0
  }
}
```

---

## Phase 3: `team_context`

### 10. Team Context Analysis Start
```json
{
  "phase": "team_context", "type": "start",
  "step": "team_analysis_start",
  "message": "Sending skills + Team Context to LLM",
  "model": "nvidia/nemotron-3-super-120b-a12b:free",
  "data": {}
}
```

### 11. Team Context LLM Result
```json
{
  "phase": "team_context", "type": "result",
  "step": "team_analysis_done",
  "message": "Team Context analysis complete. 5 skills found active in team.",
  "model": "nvidia/nemotron-3-super-120b-a12b:free",
  "data": {
    "reasoning": "PySpark is mentioned in the Q1 project tracker under active ETL pipelines...",
    "signals": [
      {"skill_name": "PySpark", "recency_category": "current_project", "assigned_tier": "T1"}
    ]
  }
}
```

---

## Phase 4: `mastery`

### 12. Mastery Matrix Result
```json
{
  "phase": "mastery", "type": "result",
  "step": "mastery_matrix_done",
  "message": "Target mastery computed for all 8 skills",
  "data": {
    "seniority": "senior",
    "matrix_axes": {
      "y_axis": "Seniority Level (intern → lead)",
      "x_axis": "Team Tier (T1=critical → T4=secondary)"
    },
    "skills": [
      {
        "skill_name": "PySpark", "canonical_id": "TECH_pyspark",
        "tier": "T1", "team_recency": "current_project",
        "target_mastery": 0.85
      }
    ]
  }
}
```

---

## Phase 5: `db`

### 13. Persist Started
```json
{
  "phase": "db", "type": "log",
  "step": "db_persist_start",
  "message": "Saving all skill metrics to SQLite"
}
```

### 14. Persist Complete
```json
{
  "phase": "db", "type": "complete",
  "step": "db_persist_done",
  "message": "Employer Flow complete. 8 skills saved.",
  "data": {
    "total_skills": 8,
    "onet_matched": 7,
    "llm_coined": 1
  }
}
```
