# AdaptIQ — Employee Flow: Redis Event Schema

This document defines every event emitted to Redis during the Employee Onboarding Flow. The frontend should subscribe to `channel:{role_id}` and render each event accordingly.

---

## Standard Event Envelope

```json
{
  "role_id":   "uuid-string",
  "phase":     "resume_extraction | normalization | mastery | gap | path | db",
  "type":      "start | log | stream_chunk | stream_end | decision | result | error | complete",
  "step":      "human_readable string",
  "message":   "Human-readable status line",
  "model":     "z-ai/glm4.7 | openai/gpt-oss-20b | null",
  "data":      { }
}
```

---

## Phase 6: `resume_extraction`

### 1. Flow Start
```json
{
  "phase": "resume_extraction", "type": "start",
  "step": "pdf_parsing",
  "message": "Parsing uploaded Resume PDF for employee",
  "data": {}
}
```

### 2. PDF Extracted
```json
{
  "phase": "resume_extraction", "type": "log",
  "step": "pdf_parsed",
  "message": "Resume PDF parsed successfully",
  "data": {
    "resume_char_count": 4500,
    "resume_preview": "Experienced software engineer with 5 years in Python..."
  }
}
```

### 3. LLM Skill Extraction Started
```json
{
  "phase": "resume_extraction", "type": "log",
  "step": "llm_extraction_start",
  "message": "Sending Resume to LLM for skill and context extraction",
  "model": "z-ai/glm-4-9b-chat",
  "data": {}
}
```

### 4. Live Streaming Chunks (Fires multiple times)
As the model generates text, it handles both `reasoning_content` (thinking) and `content` (JSON output).
```json
{
  "phase": "resume_extraction", "type": "stream_chunk",
  "step": "llm_extraction_streaming",
  "message": "",
  "model": "z-ai/glm-4-9b-chat",
  "data": {
    "chunk_type": "reasoning", // or "content"
    "text": "The candidate has worked with FastAPI for 3 years..."
  }
}
```

### 5. Final Resume LLM Result
Fires once the LLM finishes generating and the JSON is parsed.
```json
{
  "phase": "resume_extraction", "type": "result",
  "step": "llm_extraction_done",
  "message": "LLM extracted 22 raw skills from Resume",
  "model": "z-ai/glm-4-9b-chat",
  "data": {
    "raw_count": 22,
    "reasoning": "Extracted core backend technologies and cloud infrastructure experience...",
    "skills": [
      {"skill_name": "FastAPI", "context_depth": "Built backend APIs for processing e-commerce orders"}
    ]
  }
}
```

---

## Phase 7: `normalization` (per skill)

### 6. Normalization Phase Start
```json
{
  "phase": "normalization", "type": "start",
  "step": "normalization_start",
  "message": "Starting O*NET normalization for employee's 22 skills",
  "data": {}
}
```

### 7. Normalization Complete
Detailed per-skill events (Qdrant & LLM Judge) follow the same structure as the Employer flow.
```json
{
  "phase": "normalization", "type": "complete",
  "step": "normalization_done",
  "message": "18/22 employee skills matched to O*NET. 4 coined.",
  "data": {
    "matched": 18,
    "coined": 4
  }
}
```

---

## Phase 8: `mastery` (Upcoming)

### 8. Mastery Score Computation
Computes the current mastery level ($0.0 \rightarrow 1.0$) for each skill based on context and depth.
```json
{
  "phase": "mastery", "type": "result",
  "step": "mastery_computation_done",
  "message": "Employee mastery scores computed",
  "data": {
    "skills": [
      {
        "skill_name": "FastAPI",
        "current_mastery": 0.85,
        "reasoning": "High depth in building production APIs mentioned in context."
      }
    ]
  }
}
```

---

## Phase: `db`

### 9. Persist Complete
```json
{
  "phase": "db", "type": "complete",
  "step": "employee_persist_done",
  "message": "Employee resume parsing complete.",
  "data": {
    "total_skills": 22
  }
}
```
