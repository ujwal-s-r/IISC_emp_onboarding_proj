# AdaptIQ: Project Progress & Roadmap

This document serves as an in-depth tracker of what has been implemented so far, the methodologies used, and the precise next steps required to complete the AdaptIQ platform.

---

## 🟢 Completed Phases & Implementations

### Phase 1: Core Infrastructure Setup
* **FastAPI Backend Structure**: The project has been fully scaffolded with a robust, modular layout (`app/api`, `app/services`, `app/models`, `app/clients`, `app/utils`).
* **Configuration Management**: Implemented `app/config.py` using Pydantic `BaseSettings` to strongly type and validate `.env` secrets.
* **Database & ORM**: Configured a local SQLite database using asynchronous SQLAlchemy (`aiosqlite`). 
  * Defined core domain models (`Role`, `TargetSkill`, `TeamRelevanceSignal`) in `app/models/domain.py`.
* **Professional Logging**: Built `app/utils/logger.py` with `loguru` to ensure timestamped, structured logging to stdout and `logs/app.log`.
* **Real-time WebSocket Manager**: Created a generic `ConnectionManager` in `app/api/routers/websocket.py` to allow orchestrators to yield live JSON status updates directly to the frontend.

### Phase 2: Client Integrations
All external APIs have been encapsulated behind Singleton clients for easy dependency injection and mocking.
* **Vector Client (`vector_client.py`)**: Interacts with Qdrant Cloud for skill embeddings.
* **Graph Client (`graph_client.py`)**: Interacts with Neo4j Aura for traversing O*NET relationships.
* **Embedding Client (`embedding_client.py`)**: Uses local `sentence-transformers` (`intfloat/multilingual-e5-small`) to generate 384-dimensional dense vectors for both Queries and Documents.
* **Nvidia LLM Client (`nvidia_llm_client.py`)**: A specialized, streaming integration with `integrate.api.nvidia.com` using the `openai/gpt-oss-20b` model. It correctly parses and extracts both the model's `reasoning_content` and final reply.

### Phase 3: The Employer Flow (Setup Role Orchestrator)
The entire backend flow for an Employer creating a new role is complete and verified. It lives in `app/services/employer_flow/orchestrator.py`.
1. **API Endpoint**: `POST /employer/setup-role` accepts multipart form data (Title, Seniority, JD PDF, Team PDF) and triggers the orchestrator as a background task.
2. **PDF Parsing**: `pdf_service.py` extracts raw text from the uploaded bytes.
3. **Skill Extraction**: The LLM analyzes the JD to pull a raw list of required skills.
4. **Team Context Analysis**: The LLM reads the Team Context PDF and assigns a `Tier` (T1-T4) to every extracted skill based on its relevance to the team's current work.
5. **2D Mastery Matrix Computation**: A complex math step that maps the requested "Seniority" (e.g., Senior) against the "Team Tier" (e.g., T1) to generate a dynamic Target Mastery Score (0.0 to 1.0) for every single skill.
6. **Persistence**: The final normalized skills, their relevance signals, and computed targets are saved via an async DB session to SQLite.

### Phase 3.5: Advanced Skill Normalization
We implemented an Agentic 2-Stage pipeline in `app/services/skill_normalizer.py` to ground the raw LLM skills against the standard O*NET taxonomy.
1. **Vector Retrieval**: Embeds the raw skill name and queries Qdrant for the Top-3 closest O*NET elements.
2. **LLM Judge**: The Nvidia LLM evaluates the 3 candidates and picks the semantic best fit, returning its Canonical ID (e.g., `TECH_react`).
3. **Self-Learning Auto-Growth**: If the LLM judge decides *no* candidate matches, it coins a clean Canonical Name. The system then **automatically creates** a brand new node in Neo4j and a new vector in Qdrant. 
   * *Safety Guard:* Failsafes were added to prevent empty strings or "NONE" from polluting the database.


---

## 🟡 Remaining Phases & Next Steps

### Phase 4: The Employee Flow (Onboarding Setup)
This is the immediate next chunk of work. We need to mirror the employer flow structure for the employee.

1. **API Endpoint**: Create `POST /api/v1/employee/onboard-path` inside a new router (`app/api/routers/employee.py`). It should accept a Resume PDF and link to an existing `role_id`.
2. **Resume Parsing & Evaluation (`resume_parser.py`)**: 
   * Extract raw text from the Resume PDF.
   * Send text to the Nvidia LLM to assess the candidate's *current* mastery level (0.0 - 1.0) for every `TargetSkill` associated with the target `role_id`.
3. **Gap Analysis (`gap_calculator.py`)**:
   * Cross-reference current skills vs. Target Mastery scores to find missing proficiencies.
4. **Path Optimization (`path_optimizer.py`)**:
   * Generate a prioritized list of learning modules or tasks to bridge the gap.
   * *Stretch Goal:* Use the NSGA-II optimizing algorithm here to balance Time-to-Complete vs. Impact on Team (Tier).
5. **Database Models**: Add `Employee`, `LearningPath`, and `EmployeeMastery` models to `domain.py`.

### Phase 5: Graph Traversals & Hackathon Features
Once the core onboarding path exists, we implement the "Wow Factors".

1. **Dependency Injection via Neo4j**:
   * Modify the Path Optimizer. If the Gap Analysis shows an employee lacks "PySpark", the backend must query Neo4j: `MATCH (sk:Skill {canonical_id: "TECH_pyspark"})<-[:REQUIRES_SKILL]-(prereq:Skill)`.
   * The system automatically injects the exact prerequisite graph relationships into the employee's onboarding path.
2. **Live WebSocket MCQs**:
   * Add a generic WebSocket listener.
   * The Orchestrator pauses, prompts the LLM to generate a personalized MCQ based on the candidate's gap, streams the JSON question to the frontend, and waits for the frontend to emit the answer back before continuing the optimization.
3. **"Day in the Life" Interactive Scenario**:
   * Final step of the employee flow. The LLM acts as a game-master. It streams a scenario (e.g., "The production DB is down") over WebSockets, and the employee must respond with theoretical commands or code.
