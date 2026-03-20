Phase-by-Phase Plan: Employer Flow Business Logic
When we begin coding, we will implement the Employer Flow using this structured sequence:

Phase 1: Data Models & API Entry Points
Define SQLAlchemy database tables (Role, TargetSkill, TeamRelevanceSignal).
Define Pydantic schemas for the incoming multipart form data and outgoing REST responses.
Set up the POST /setup-role endpoint and wire up the basic WebSocket ConnectionManager.
Phase 2: Job Description (JD) Processing Logic
Implement parsing of the JD PDF using pdfplumber.
Create the LLM prompt to extract canonical skills, required seniority levels, and context strings.
Implement the mathematical mapping of role seniority to base "Target Mastery" threshold scores (e.g., Senior = 0.85, Mid = 0.65).

Phase 3: Team Context Processing Logic
Implement parsing for the Team Context PDF.
Create the LLM prompt to extract skill mentions, frequency counts, and project recency (current vs. past).
Implement the calculation for the Team Relevance Score based on those signals.

Phase 4: Skill Normalization & Graph Expansion
Combine the skills from the JD and Team Context.
Implement the Qdrant vector search to find the closest matching O*NET canonical skills.
Implement the "Tiny LLM" reranking step to finalize the canonical match.
Self-Expanding Graph: Add logic to detect unknown skills (low similarity scores), generate their prerequisites via the LLM, and insert them as new nodes into the Neo4j Graph and Qdrant index.
Phase 5: Priority Tier Assignment & Curation
Merge Target Masteries and Team Relevance Scores.
Assign Priority Tiers (T1, T2, T3, T4) representing Day-1 Critical vs. Learn Gradually.
Process any curated URLs by chunking the text, embedding it, and saving it to a role-specific Qdrant collection.
Phase 6: Orchestration & Assembly
Build the employer_orchestrator.py script that ties Phases 2 through 5 together sequentially.
Inject the WebSocket manager into the orchestrator so it fires a ws.broadcast() at the beginning and end of every single sub-phase.
Persist the final "Compiled Role Package" to the SQLite database.