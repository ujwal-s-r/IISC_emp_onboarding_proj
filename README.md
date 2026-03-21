# AdaptIQ — Intelligent Employee Onboarding Platform

AdaptIQ is a full-stack system that transforms the employee onboarding process from a generic checklist into a personalized, evidence-based learning journey. It takes real job descriptions, real team context, and real resumes, then produces three optimized learning paths tailored to each employee's actual skill gaps.

The platform is built around two core flows: an employer setup phase that defines what a role truly requires, and an employee onboarding phase that assesses an individual against those requirements and generates a roadmap to close the gaps.

---

## Table of Contents

1. [The Problem](#the-problem)
2. [How AdaptIQ Solves It](#how-adaptiq-solves-it)
3. [System Architecture](#system-architecture)
4. [Employer Setup Flow](#employer-setup-flow)
5. [Employee Onboarding Flow](#employee-onboarding-flow)
6. [Key Technical Decisions](#key-technical-decisions)
7. [Tech Stack](#tech-stack)
8. [Getting Started](#getting-started)
9. [Project Structure](#project-structure)

---

## The Problem

Traditional onboarding hands every new hire the same training material regardless of what they already know or what the team actually needs. A senior engineer with 5 years of Python experience still gets assigned "Introduction to Python." Meanwhile, the Kafka expertise the team desperately needs goes unaddressed because it was buried in page 4 of the job description.

Three specific gaps exist in current approaches:

- **No understanding of current skill level.** Onboarding treats every employee as a blank slate.
- **No connection to team reality.** Job descriptions list ideal requirements, but teams have immediate, specific needs that differ from the formal spec.
- **No principled way to choose learning resources.** Recommending "the most popular course" ignores trade-offs between speed, difficulty match, and relevance.

---

## How AdaptIQ Solves It

AdaptIQ runs an 11-phase pipeline across two flows. The employer flow establishes what a role requires. The employee flow measures where an individual stands, identifies the gaps, and generates three distinct learning paths using multi-objective optimization.

**What makes this different:**

1. **Team Context Pack** — Employers upload internal team documentation alongside the job description. The system extracts what the team is actively working on and uses that to prioritize which skills matter most right now versus which are long-term goals. This turns a flat skill list into a tiered priority model.

2. **Canonical Skill Normalization** — Every skill extracted from any document is grounded to a canonical identifier using O\*NET taxonomy, vector similarity search, and an LLM judge. "K8s", "Kubernetes", and "container orchestration" all resolve to the same node. When a skill does not exist in the taxonomy, the system coins a new canonical entry and persists it to both the vector database and the knowledge graph, so future employees benefit immediately.

3. **Graph-Based Dependency Resolution** — Skills are not independent. "PySpark" requires "Python." "Kafka Streams" builds on "Apache Kafka." The system queries a Neo4j knowledge graph to discover prerequisite relationships between gap skills, then uses an LLM to arrange them into a staged learning order.

4. **NSGA-II Multi-Objective Course Selection** — Rather than picking the "best" course by a single metric, the system uses a genetic algorithm (NSGA-II) to find the Pareto-optimal set of courses across four competing objectives: relevance, speed, quality, and difficulty match. From the Pareto front, it selects three archetypes — Sprint (fastest), Balanced (best trade-off), and Quality (highest rated) — giving the employee meaningful choices.

5. **Real-Time Visibility** — Every phase streams its progress, LLM reasoning traces, and results to the browser through Redis pub/sub and WebSocket. The frontend sees exactly what the system is thinking, in real time.

---

## System Architecture

```
                        +------------------+
                        |   Next.js 15     |
                        |   Frontend       |
                        |   (React 19)     |
                        +--------+---------+
                                 |
                            WebSocket
                                 |
                        +--------+---------+
                        |   FastAPI        |
                        |   Backend        |
                        +--+----+----+-----+
                           |    |    |
              +------------+    |    +------------+
              |                 |                  |
     +--------v------+  +------v-------+  +-------v--------+
     | Redis          |  | SQLite       |  | Nvidia API     |
     | (Event Bus)    |  | (Persistence)|  | (LLM Gateway)  |
     +----------------+  +--------------+  +----------------+
              |
     +--------v------+         +------------------+
     | Qdrant Cloud  |         | Neo4j Aura       |
     | (2 instances) |         | (Knowledge Graph)|
     +---------------+         +------------------+

     Instance 1: onet_skills (384-dim, skill taxonomy)
     Instance 2: courses_listed (2048-dim, course catalog)
```

The backend is a single FastAPI application that orchestrates all processing. It communicates with five external services: two Qdrant vector database instances for skill matching and course retrieval, a Neo4j graph database for skill relationships, the Nvidia API for LLM inference, and Redis for real-time event streaming.

All long-running operations execute as background tasks. The HTTP endpoint returns immediately with an ID. The frontend opens a WebSocket connection and receives a stream of structured JSON events as each phase completes.

---

## Employer Setup Flow

The employer uploads a job description PDF, a team context document, and selects a seniority level. The system then runs five steps to produce a structured role definition.

**Step 1 — Document Parsing.** Both PDFs are converted to text using pdfplumber in a background thread to avoid blocking the event loop.

**Step 2 — Skill Extraction.** An LLM reads the job description and extracts 15 to 20 skills, each with a reasoning trace explaining why it was identified and how critical it appears.

**Step 3 — Skill Normalization.** Each raw skill name passes through the three-stage normalization pipeline (described below) to produce a canonical identifier grounded in the O\*NET taxonomy.

**Step 4 — Team Context Analysis.** The LLM reads the team context document and identifies which of the extracted skills appear in the team's actual current work. Skills referenced in real team documentation receive higher priority tiers.

**Step 5 — Tier Assignment and Target Mastery.** Skills are assigned to four tiers:

| Tier | Meaning |
|------|---------|
| T1 | Day-one critical — the team needs this immediately |
| T2 | First-month — important but not blocking on day one |
| T3 | Gradual — needed over the first quarter |
| T4 | Long-term — listed in the JD but low urgency based on team context |

A mastery matrix combines the tier with the role seniority to set a numeric target mastery for each skill. A senior role with a T1 skill demands 0.85 mastery. A junior role with a T3 skill requires only 0.20.

The result is a structured role definition with canonical skill IDs, tiers, and numeric target mastery values, all persisted to the database and ready for employee matching.

---

## Employee Onboarding Flow

The employee uploads their resume against an existing role. The system runs six phases to generate a personalized learning plan.

### Phase 6 — Resume Extraction

The resume PDF is parsed in a thread pool, then sent to a 122-billion-parameter LLM (Qwen 3.5) with thinking mode enabled. The prompt instructs the model to extract skills with specific evidence, not just keywords. For each skill, the model captures what the candidate actually did: "Architected PySpark ETL processing 10TB daily, reducing runtime from 4 hours to 45 minutes" rather than just "PySpark."

The model produces an array of skill/evidence pairs. Its internal reasoning trace is streamed to the frontend in real time so the user can see the analysis happening.

### Phase 7 — Skill Normalization

The same normalization pipeline used in the employer flow processes each resume skill. This ensures that employer-side "Kubernetes" and employee-side "k8s" resolve to the same canonical identifier, making gap computation reliable.

The normalization pipeline works in three stages:

1. **Vector retrieval.** The raw skill name is embedded into a 384-dimensional vector and queried against the O\*NET skill collection in Qdrant. The top three candidates above a similarity threshold are returned.

2. **LLM judge.** A lightweight LLM call (with reasoning disabled for speed) evaluates the three candidates and picks the best semantic match, or returns "none" if none are appropriate.

3. **Auto-coining.** If no match exists, the LLM generates a clean canonical name. That name is immediately embedded and persisted to both Qdrant and Neo4j. The next employee with the same skill will find it on the first vector search, with no manual intervention needed.

Every normalization decision is published as a Redis event, creating a complete audit trail.

### Phase 8 — Mastery Scoring

All normalized skills are sent in a single batch to an LLM with thinking mode enabled. The model classifies each skill into one of five depth levels (expert, advanced, intermediate, basic, surface) based on the evidence extracted in Phase 6.

The classification follows a strict rubric. Hard metrics and ownership language ("led", "architected") push scores up. Vague phrasing ("familiar with", "exposure to") enforces caps. Surface mentions with no supporting project context are scored at the floor.

Each depth level maps to a deterministic numeric score: expert = 0.90, advanced = 0.70, intermediate = 0.50, basic = 0.25, surface = 0.10.

### Phase 9 — Gap Analysis

This phase requires no LLM. For each skill that appears in the role's target list, the system computes:

- **Gap** = max(0, target mastery - current mastery)
- **Priority** = tier weight multiplied by gap magnitude

Skills are categorized as critical (gap >= 0.50), moderate (0.25 to 0.50), minor (0.05 to 0.25), or met (below 0.05). The output is sorted by priority score so the most urgent gaps surface first.

### Phase 10A — Dependency Resolution

The system queries Neo4j for prerequisite relationships (REQUIRES, BUILDS\_ON, LEADS\_TO) between gap skills. These graph edges, combined with the gap list, are passed to an LLM that produces a directed acyclic graph: skills organized into sequential stages where each stage depends only on earlier stages.

This ensures the learning plan does not ask someone to learn PySpark before they know Python.

### Phase 10B — Course Selection (NSGA-II Optimization)

For each gap skill, the system embeds the skill name using a 2048-dimensional model and retrieves the top 30 matching courses from a Qdrant collection containing indexed learning resources.

These 30 candidates are then optimized using NSGA-II, a multi-objective genetic algorithm, across four objectives that are all normalized to the 0-to-1 range and minimized:

| Objective | What It Measures |
|-----------|-----------------|
| f1: Relevance | 1 minus the cosine similarity score — higher similarity is better |
| f2: Speed | Normalized course duration — shorter is better |
| f3: Quality | 1 minus the normalized quality/popularity score — higher rated is better |
| f4: Difficulty Match | Absolute difference between course difficulty and required level — perfect match is better |

NSGA-II runs for 40 generations with a population of 30. It uses non-dominated sorting to identify the Pareto front — the set of courses where no single course is strictly better than another across all four objectives. Within the front, crowding distance promotes diversity.

From the final Pareto front, three courses are selected:

| Track | Selection Rule | Who It Serves |
|-------|---------------|---------------|
| Sprint | Lowest f2 (fastest) | Employee who needs to get productive quickly |
| Balanced | Closest to the geometric center of all objectives | Employee who wants a well-rounded option |
| Quality | Lowest f3 (highest quality and ratings) | Employee who wants the deepest learning experience |

This gives the employee a genuine choice rather than a single recommendation.

### Phase 11 — Journey Narration

The final phase sends the complete picture — gap analysis, dependency graph, and selected courses — to a large LLM. The model validates that the learning plan is logically coherent, writes brief human-readable narratives for each track, and structures the entire journey into a tree format for frontend visualization.

The tree has the role goal as its root, skill gaps as main branches (colored by severity), and prerequisite skills as smaller nodes underneath. Each branch carries three course options (Sprint, Balanced, Quality) that the frontend can display as selectable cards.

---

## Key Technical Decisions

### Why a Team Context Document?

Job descriptions are written for recruiters. They list idealized requirements, not what the team needs this quarter. By ingesting an internal team document — architecture decisions, project notes, current tech stack — the system learns that "we migrated to Kafka last month and half the team is still learning it." That skill becomes T1 instead of T3, and the new hire's learning plan reflects the team's actual urgency.

### Why O\*NET Normalization with a Knowledge Graph?

Data quality is the foundation. If employer-side "Kubernetes" and employee-side "k8s" are treated as different skills, the gap analysis produces false negatives. By grounding every skill to a canonical identifier in the O\*NET occupational taxonomy, and extending it dynamically with new skills through auto-coining, the system maintains a single source of truth.

Neo4j stores the relationships between these canonical skills. This is not something an LLM can reliably hallucinate — prerequisite chains need to be consistent across all employees processed against the same role. The graph provides that consistency.

### Why NSGA-II Instead of Simple Ranking?

Picking a course by a single criterion (highest rated, shortest, most relevant) ignores the trade-offs. A 2-week course may be fast but poorly matched to the skill level. The highest-rated course may take 12 weeks. NSGA-II finds the set of courses where improving one objective necessarily worsens another — the Pareto front. Selecting three archetypes from that front gives the employee a principled choice rather than an arbitrary recommendation.

### Why Real-Time Streaming?

The full pipeline takes 60 to 120 seconds. Without streaming, the user stares at a spinner. With Redis pub/sub proxied through WebSocket, the frontend shows every phase as it happens: skills being extracted, normalization decisions, LLM reasoning traces, gap computations, course selections. The user sees the system thinking, which builds trust and keeps them engaged.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS | User interface and real-time event rendering |
| Backend | FastAPI, Python 3.10, async/await | API, orchestration, background task management |
| Persistence | SQLite via aiosqlite | Role definitions, employee records, learning paths |
| Event Bus | Redis pub/sub | Real-time event streaming from backend to frontend |
| Real-Time | WebSocket (FastAPI native) | Browser connection for live progress updates |
| Vector Search (Skills) | Qdrant Cloud, 384-dim embeddings (multilingual-e5-small) | O\*NET skill taxonomy matching |
| Vector Search (Courses) | Qdrant Cloud, 2048-dim embeddings (NemoRetriever) | Course catalog retrieval for NSGA-II |
| Knowledge Graph | Neo4j Aura | Skill prerequisite relationships and dependency edges |
| LLM Inference | Nvidia API | All language model calls (extraction, scoring, narration) |
| PDF Parsing | pdfplumber | Resume and job description text extraction |
| Optimization | NSGA-II (custom implementation) | Multi-objective course selection |

**Models Used:**

| Model | Where It Is Used | Thinking Mode |
|-------|-----------------|---------------|
| Qwen 3.5 122B | Resume extraction (Phase 6) | On |
| GPT-OSS 20B | Normalization judge (Phase 7) | Off |
| GPT-OSS 20B | Mastery scoring (Phase 8) | On |
| GPT-OSS 20B | Dependency ordering (Phase 10A) | On |
| Qwen 3.5 122B | Journey narration (Phase 11) | On |
| Step 3.5 Flash | Job description extraction (Employer flow) | Off |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 20+
- Redis server (local or remote)
- Accounts for: Nvidia API, Qdrant Cloud, Neo4j Aura

### Backend Setup

```bash
cd IISC_emp_onboarding_proj
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root (see `.env.example` for all required variables):

```
NVIDIA_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COURSES_URL=...
QDRANT_COURSES_API_KEY=...
NEO4J_URI=...
NEO4J_PASSWORD=...
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite+aiosqlite:///./DB/adaptiq.db
```

Start the backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:3000` and connects to the backend at `http://localhost:8000`.

### Docker (Optional)

```bash
cp .env.example .env   # Fill in API keys and service URLs
docker compose up --build
```

This starts Redis, the backend, and the frontend as separate containers with health checks.

---

## Project Structure

```
app/
  main.py                          Application entry point and middleware
  config.py / settings.py          Environment configuration
  api/routers/
    employer.py                    POST /setup-role endpoint
    employee.py                    POST /onboard-path endpoint
    websocket.py                   WebSocket proxy for Redis events
  services/
    skill_normalizer.py            3-stage normalization pipeline
    pdf_service.py                 PDF text extraction
    employer_flow/
      orchestrator.py              Employer setup pipeline (5 steps)
    employee_flow/
      orchestrator.py              Employee pipeline (Phases 6-9)
      dependency_resolver.py       Phase 10A: Neo4j + LLM DAG ordering
      path_generator.py            Phase 10B: NSGA-II course optimization
      journey_narrator.py          Phase 11: Narration and tree generation
  clients/
    embedding_client.py            Local 384-dim embedding model
    vector_client.py               Qdrant operations
    graph_client.py                Neo4j queries
    llm_client.py                  Nvidia API streaming client
    redis_client.py                Redis pub/sub wrapper
  models/
    domain.py                      SQLAlchemy models (Role, Employee, etc.)
    schemas.py                     Pydantic response schemas
  db/
    session.py                     Async SQLite session factory
frontend/                          Next.js 15 application
machine_learning/                  Data exploration and model fine-tuning notebooks
docs/                              Architecture and integration documentation
```
