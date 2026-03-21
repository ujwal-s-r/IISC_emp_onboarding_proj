import pathlib

content = '''# AdaptIQ — Employee Flow: Redis Event Schema

This document defines **every** event emitted to Redis during the complete Employee Onboarding Flow (Phases 6–11).  
The frontend subscribes to \channel:{role_id}\ and renders each event accordingly.

> **Model roles (as at March 2026)**
> | Role | Model | Thinking |
> |---|---|---|
> | Phase 6 — Resume extraction | \qwen/qwen3.5-122b-a10b\ | **ON** — CoT trace in \easoning_content\, JSON array in \content\ |
> | Phase 7 — O\*NET judge/coining | \openai/gpt-oss-20b\ | OFF — returns \1\/\2\/\3\/\NONE\ only in \content\ |
> | Phase 8 — Mastery scoring | \openai/gpt-oss-20b\ | **ON** — CoT trace in \easoning_content\, final JSON array in \content\ |
> | Phase 10 — Dependency resolution | \openai/gpt-oss-20b\ | **ON** — DAG JSON in \content\ |
> | Phase 11 — Journey narration | \qwen/qwen3.5-122b-a10b\ | **ON** — tree + narrative JSON in \content\ |

> **Critical fix (March 2026):** \NvidiaLLMClient.complete()\ now returns **only** \content\, never \easoning + content\ concatenated. This prevents the LLM's thinking trace from leaking into coined canonical skill names.

---

## Standard Event Envelope

`json
{
  "role_id":   "uuid-string",
  "phase":     "resume_extraction | normalization | mastery | gap | path | journey | db",
  "type":      "start | log | stream_chunk | stream_end | decision | result | complete | progress | error",
  "step":      "machine_readable_snake_case",
  "message":   "Human-readable status line",
  "model":     "qwen/qwen3.5-122b-a10b | openai/gpt-oss-20b | null",
  "data":      { }
}
`

---

## Phase 6: \esume_extraction\

### 1. PDF Parsing Starts (immediately on upload)
`json
{
  "phase": "resume_extraction", "type": "start",
  "step": "pdf_parsing",
  "message": "Parsing uploaded Resume PDF — skill extraction will start immediately after",
  "model": null,
  "data": {}
}
`

### 2. PDF Parsed
`json
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
`

### 3. LLM Extraction Started
`json
{
  "phase": "resume_extraction", "type": "log",
  "step": "llm_extraction_start",
  "message": "Sending Resume to LLM for skill and context extraction",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": {}
}
`

### 4. LLM Streaming — Reasoning & Content *(streams rapidly in a loop per token)*
*Note: Thinking is now ON, so \easoning\ chunks fire first, followed by \content\ chunks.*
`json
{
  "phase": "resume_extraction", "type": "stream_chunk",
  "step": "llm_extraction_streaming",
  "message": "",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "chunk_type": "reasoning", "text": "The candidate has listed Python and..." }
}
`
`json
{
  "phase": "resume_extraction", "type": "stream_chunk",
  "step": "llm_extraction_streaming",
  "message": "",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "chunk_type": "content", "text": "[{\"skill_name\": \"Python" }
}
`

### 5. LLM Stream Complete
`json
{
  "phase": "resume_extraction", "type": "stream_end",
  "step": "llm_extraction_streaming",
  "message": "Stream complete",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "reasoning_length": 1400, "content_length": 1240 }
}
`

### 6. Extraction Result
`json
{
  "phase": "resume_extraction", "type": "result",
  "step": "llm_extraction_done",
  "message": "LLM extracted 20 raw skills from Resume",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": {
    "raw_count": 20,
    "skills": [
      { "skill_name": "Python", "context_depth": "Led development of 12 production microservices processing 2M req/day" },
      { "skill_name": "Apache Spark", "context_depth": "Architected PySpark ETL reducing runtime from 4h to 45min on 10TB" }
    ]
  }
}
`

---

## Phase 7: \
ormalization\

Runs **sequentially in a loop per exact skill** extracted. For each skill: embed  Qdrant vector search  LLM judge  decision.

> **Note:** \gpt-oss-20b\ judge/coining expects \easoning\ and \content\. Normalizer \complete()\ will skip reasoning and return ONLY content to prevent polluting Node IDs.

### 7.1 Normalization Starts
`json
{
  "phase": "normalization", "type": "start",
  "step": "normalization_start",
  "message": "Starting O*NET normalization for 20 employee skills",
  "model": null, "data": {}
}
`

### 7.2 Per-Skill: Qdrant Query *(loops once per skill)*
`json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_query",
  "message": "Querying Qdrant for 'PySpark'",
  "model": null,
  "data": { "raw_skill": "PySpark" }
}
`

### 7.3 Per-Skill: Qdrant Results *(loops once per skill)*
`json
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
`

### 7.4a Per-Skill: No Qdrant candidates *(fires if score < 0.50 for all)*
`json
{
  "phase": "normalization", "type": "log",
  "step": "qdrant_no_match",
  "message": "No O*NET candidates found for 'LoRA'. LLM will coin a name.",
  "model": null, "data": { "raw_skill": "LoRA" }
}
`

### 7.4b Per-Skill: LLM Judge NONE *(fires when candidates exist but LLM says none fit)*
`json
{
  "phase": "normalization", "type": "log",
  "step": "llm_judge_none",
  "message": "LLM decided no O*NET match for 'Multi-Agent Systems'",
  "model": null, "data": { "raw_skill": "Multi-Agent Systems", "llm_raw_reply": "NONE" }
}
`

### 7.5a Per-Skill: O*NET Match Confirmed *(loops once per skill validation)*
`json
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
`

### 7.5b Per-Skill: New Skill Coined
A new canonical node is **created in both Qdrant and Neo4j** after this event.
`json
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
`

### 7.6 Normalization Complete
`json
{
  "phase": "normalization", "type": "complete",
  "step": "normalization_done",
  "message": "11/20 skills matched to O*NET. 9 coined.",
  "model": null,
  "data": { "matched": 11, "coined": 9, "total": 20 }
}
`

---

## Phase 8: \mastery\

> **Model**: \openai/gpt-oss-20b\ with \	hinking: True\.  
> \easoning_content\ = long CoT trace (the model's internal deliberation). \content\ = final JSON array.  
> Batch processed (all skills in one prompt).

### 8.1 Mastery Scoring Start
`json
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
`

### 8.2 LLM Streaming — CoT & JSON *(runs rapidly in a continuous loop per generated chunk)*
`json
{
  "phase": "mastery", "type": "stream_chunk",
  "step": "mastery_scoring_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "reasoning", "text": "PySpark: built large-scale ELT at Maersk..." }
}
`

### 8.3 Stream End
`json
{
  "phase": "mastery", "type": "stream_end",
  "step": "mastery_scoring_streaming",
  "message": "Stream complete",
  "model": "openai/gpt-oss-20b",
  "data": { "reasoning_length": 6400, "content_length": 2100 }
}
`

### 8.4 Per-Skill Score Log *(loops and fires once per skill synchronously)*
`json
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
`

### 8.5 Mastery Result
`json
{
  "phase": "mastery", "type": "result",
  "step": "mastery_scoring_done",
  "message": "Current mastery computed for 20 skills",
  "model": "openai/gpt-oss-20b",
  "data": {
    "reasoning_summary": "PySpark: built large-scale ELT at Maersk...",
    "skills": [ ... ]
  }
}
`

---

## Phase 9: \gap\

> **No LLM involved.** Pure math loop matching employee skills vs target skills.

### 9.1 Gap Analysis Start
`json
{
  "phase": "gap", "type": "start",
  "step": "gap_analysis_start",
  "message": "Starting gap analysis: 20 employee skills vs 8 role targets",
  "model": null,
  "data": { "formula": { ... } }
}
`

### 9.2 Per-Skill Gap Log *(loops once per gap computed)*
`json
{
  "phase": "gap", "type": "log",
  "step": "skill_gap_computed",
  "message": "Gap 'Apache Kafka': 0.700 (critical)",
  "model": null,
  "data": {
    "skill_name":           "Apache Kafka",
    "canonical_id":         "TECH_kafka",
    "tier":                 "T1",
    "gap":                  0.700,
    "gap_category":         "critical",
    ...
  }
}
`

### 9.3 Gap Analysis Result
`json
{
  "phase": "gap", "type": "result",
  "step": "gap_analysis_done",
  "message": "Gap analysis complete: 2 critical, 1 moderate, 3 minor, 2 met",
  "model": null,
  "data": { "summary": { "critical": 2, "moderate": 1, "minor": 3, "met": 2 }, "ranked_gaps": [...] }
}
`

---

## Phase 10: \path\

> **Two sub-steps:** 
> 1) LLM DAG derivation (\openai/gpt-oss-20b\ streams CoT).
> 2) NSGA-II 4-objective Pareto loop per gap.

### 10.1 Dependency Resolution Start
`json
{
  "phase": "path", "type": "start",
  "step": "dependency_start",
  "message": "Resolving skill prerequisite order for 5 gaps",
  "model": "openai/gpt-oss-20b", "data": {}
}
`

### 10.2 Graph Query Log
`json
{
  "phase": "path", "type": "log",
  "step": "graph_query",
  "message": "Querying Neo4j for skill prerequisite edges",
  "model": null,
  "data": { "skill_names": ["Apache Kafka", "Docker", "Python"], "edges_found": 2 }
}
`

### 10.3 DAG LLM Streaming *(loops per token chunk)*
`json
{
  "phase": "path", "type": "stream_chunk",
  "step": "dependency_streaming",
  "model": "openai/gpt-oss-20b",
  "data": { "chunk_type": "reasoning", "text": "Python must precede Kafka as a foundational skill..." }
}
`

### 10.4 Dependency Ready
`json
{
  "phase": "path", "type": "result",
  "step": "dependency_ready",
  "message": "Dependency DAG resolved — 3 ordered stages",
  "model": "openai/gpt-oss-20b",
  "data": { "stages": [...], "dependency_edges": [...] }
}
`

### 10.5 NSGA-II Course Selection Start
`json
{
  "phase": "path", "type": "start",
  "step": "nsga_start",
  "message": "Starting NSGA-II course selection across 3 stage(s)",
  "model": null, "data": { "total_stages": 3, "algorithm": "NSGA-II 4-objective Pareto" }
}
`

### 10.6 Per-Gap Course Selection *(loops once per gap stage natively)*
`json
{
  "phase": "path", "type": "progress",
  "step": "nsga_gap_done",
  "message": "Stage 1: courses selected for 'Apache Kafka'",
  "model": null,
  "data": {
    "stage":          1,
    "skill":          "Apache Kafka",
    "gap_category":   "critical",
    "candidates":     28,
    "pareto_front":   9,
    "sprint_title":   "Apache Kafka Fundamentals — Quick Start",
    ...
  }
}
`

### 10.7 All Paths Ready
`json
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
`

---

## Phase 11: \journey\

> Final LLM pass using \qwen/qwen3.5-122b-a10b\ (thinking ON). Validates paths, writes HR-readable narratives, and builds the visual tree mapping structure directly in \content\.

### 11.1 Journey Narration Start
`json
{
  "phase": "journey", "type": "start",
  "step": "narrator_start",
  "message": "Building final learning journey and visualization tree",
  "model": "qwen/qwen3.5-122b-a10b", "data": {}
}
`

### 11.2 LLM Streaming *(loops per token chunk — reasoning then content)*
`json
{
  "phase": "journey", "type": "stream_chunk",
  "step": "narrator_llm_stream",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": { "chunk_type": "content", "text": "{\n  \"validation\": {\"sprint_ok\": true" }
}
`

### 11.3 Stream End
`json
{
  "phase": "journey", "type": "stream_end",
  "step": "narrator_llm_stream",
  "message": "Stream complete",
  "model": "qwen/qwen3.5-122b-a10b", "data": {}
}
`

### 11.4 Journey Ready
*Note the newly flattened \data\ root format to make tree parsing easier for the frontend.*
`json
{
  "phase": "journey", "type": "result",
  "step": "journey_ready",
  "message": "Learning journey complete — 3 paths available",
  "model": "qwen/qwen3.5-122b-a10b",
  "data": {
    "validation": {
      "sprint_ok": true, "balanced_ok": true, "quality_ok": true, "notes": "All paths are coherent."
    },
    "narratives": {
      "sprint":   "Fast-track to Data Engineer readiness in 4.5 weeks by focusing on the highest-priority Kafka and Docker gaps.",
      "balanced": "A 9-week structured programme that blends speed with comprehensive coverage.",
      "quality":  "A 14-week deep-dive programme that builds true expert-level mastery."
    },
    "path_summaries": {
      "sprint":   { "total_weeks": 4.5,  "coverage_score": 0.81, "label": "Sprint Track" },
      "balanced": { "total_weeks": 9.0,  "coverage_score": 0.87, "label": "Balanced Track" },
      "quality":  { "total_weeks": 14.5, "coverage_score": 0.93, "label": "Quality Track" }
    },
    "tree_nodes": 5,
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
`

---

## Final: \db\

### Pipeline Close
Fires after all phases complete. DB writes for mastery and journey are fire-and-forget via \syncio.ensure_future\, so this final UI resolution event fires immediately.
`json
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
`

---

## Complete Event Timeline (Loop visualization)

`	ext
 POST /employee/onboard-path
   
 [Ph 6]  resume_extraction / start         / pdf_parsing
         resume_extraction / log           / pdf_parsed
         resume_extraction / log           / llm_extraction_start
          loops: stream_chunk (reasoning mode loop)
          loops: stream_chunk (content mode loop)
         resume_extraction / stream_end    / llm_extraction_streaming
         resume_extraction / result        / llm_extraction_done
   
 [Ph 7]  normalization     / start         / normalization_start
          loops (per skill)
               normalization / log      / qdrant_query
               normalization / log      / qdrant_results
               conditional: normalization / log / qdrant_no_match
               conditional: normalization / log / llm_judge_none
               outcome A: normalization / decision / llm_judge
               outcome B: normalization / decision / llm_coined
         normalization     / complete      / normalization_done
   
 [Ph 8]  mastery           / start         / mastery_scoring_start
          loops: stream_chunk (reasoning loop)
          loops: stream_chunk (content loop)
         mastery           / stream_end    / mastery_scoring_streaming
          loops (per skill parsed from json): mastery / log / skill_mastery_computed
         mastery           / result        / mastery_scoring_done
   
 [Ph 9]  gap               / start         / gap_analysis_start
          loops (per role target skill): gap / log / skill_gap_computed
         gap               / result        / gap_analysis_done
   
 [Ph 10] path              / start         / dependency_start
         path              / log           / graph_query
          loops: stream_chunk (reasoning + content stream loop)
         path              / result        / dependency_ready
         path              / start         / nsga_start
          loops (per gap skill): path / progress / nsga_gap_done
         path              / result        / paths_ready
   
 [Ph 11] journey           / start         / narrator_start
          loops: stream_chunk (reasoning loop)
          loops: stream_chunk (content loop)
         journey           / stream_end    / narrator_llm_stream
         journey           / result        / journey_ready
   
         db                / complete      / employee_persist_done
`
'''

pathlib.Path('docs/employee_redis.md').write_text(content, encoding='utf-8')
print("Documentation updated successfully!")
