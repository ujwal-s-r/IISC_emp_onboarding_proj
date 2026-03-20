# AdaptIQ: System Working Flow

This document provides an in-depth explanation of how the AdaptIQ backend flows operate, from the initial API request down to database persistence.

---

## 🏗️ 1. The Employer Setup Flow (Orchestrator)

The core engine of the generic "Employer side" is the Orchestrator (`app/services/employer_flow/orchestrator.py`). It chains together PDF parsing, LLM generation, Vector search algorithms, and Graph traversals in a single asynchronous background pipeline. 

It heavily utilizes WebSockets via `app/api/routers/websocket.py` to stream its current step and status back to the frontend in real-time, preventing standard HTTP timeouts on long LLM calls.

### Sequence Diagram: Creating a Role

```mermaid
sequenceDiagram
    actor Employer
    participant API as /setup-role Endpoint
    participant DB as SQLite (aiosqlite)
    participant Socket as WebSocket Manager
    participant PDF as PDF Service
    participant LLM as Nvidia API (gpt-oss-20b)
    participant Norm as normalizer.py
    participant Qdrant as Vector DB
    participant Neo4j as Graph DB

    Employer->>API: POST /setup-role (FormData + PDFs)
    API->>DB: Create basic Role {title, seniority}
    DB-->>API: Returns Role ID
    API->>Employer: HTTP 202 Accepted (Role ID)
    
    note over API, Neo4j: Background Task Begins

    API->>Socket: broadcast(step="parsing", status="in_progress")
    API->>PDF: extract_text(JD Bytes), extract_text(Context Bytes)
    PDF-->>API: JD Text, Context Text
    
    API->>Socket: broadcast(step="llm_extraction")
    API->>LLM: Prompt (JD Text) -> Extract raw skills array
    LLM-->>API: JSON `[{"skill_name": "React", ...}]`
    
    API->>Socket: broadcast(step="normalization")
    API->>Norm: normalize_skills(raw_skills)
    
    loop For Each Skill
        Norm->>Qdrant: embed & query_points(limit=3)
        Qdrant-->>Norm: Top 3 Candidates
        Norm->>LLM: Prompt LLM Judge (Candidate 1, 2, 3 vs. Raw)
        LLM-->>Norm: Selected Candidate (or 'NONE')
        
        alt Match Found
            Norm->>Neo4j: Fetch O*NET importance/level
            Neo4j-->>Norm: Level (e.g. 2.45)
        else 'NONE'
            Norm->>LLM: "Coin Canonical Name"
            LLM-->>Norm: Coined Name
            Norm->>Qdrant: upsert(New Vector)
            Norm->>Neo4j: MERGE(New Node)
        end
    end
    Norm-->>API: List of Normalized Skills with `canonical_id`
    
    API->>Socket: broadcast(step="team_context")
    API->>LLM: Prompt (Normalized Skills + Context Text) -> Assign Tiers
    LLM-->>API: JSON `{"TECH_react": {"tier": "T1"}}`
    
    note over API: Local Math: Seniority matrix vs T1/T2/T3
    
    API->>DB: persistTargetSkills(matrix_scores)
    API->>Socket: broadcast(step="complete", status="done")
```

---

## 🧠 2. Advanced Skill Normalization (In-Depth)

The most complex sub-system is `app/services/skill_normalizer.py`. It is responsible for taking unstructured, messy LLM outputs from the JD parser and locking them strictly to the O*NET standard taxonomy. 

### Why is this needed?
If an employer asks for "K8s" and a candidate's resume says "Kubernetes", standard string matching yields a 0% match. By forcing both inputs through the normalizer, they both resolve to the standard Canonical ID `TECH_kubernetes`.

### The Agentic Pipeline
Unlike traditional fast-text matching, we use a 2-stage "Agentic" approach involving both our local Vector database and a live LLM "Judge". 

1. **Local Vector Search (`intfloat/multilingual-e5-small`)**: We generate an incredibly fast 384-dimension vector locally, without hitting an external API. We query Qdrant to find the 3 closest matches.
2. **Nvidia LLM Judge (`gpt-oss-20b`)**: The `openai/gpt-oss-20b` model streams chunks of reasoning directly from Nvidia's official architecture. It acts as an impartial judge, evaluating if Qdrant's candidates actually mean the same thing as the raw user input.
3. **Database Auto-Growth**: Traditional taxonomies rot over time as new tools are invented (e.g., "LangChain" doesn't exist in O*NET). If the LLM Judge determines no candidate matches, it generates a clean taxonomy name itself and **automatically provisions a new node in both Neo4j and Qdrant**. This ensures the system "learns" new technical terms permanently on the fly.

### Process Flow

```mermaid
graph TD
    A([Raw Skill from JD/Resume]) --> B[Generate 384d Dense Vector]
    B --> C[(Qdrant Cloud)]
    C -- Returns Top 3 --> D{Score > 0.50?}
    D -- No --> H
    D -- Yes --> E((Nvidia GPT-20B Judge))
    E -- Evaluates Semantic Fit --> F{Is Match Valid?}
    
    F -- Yes --> G[Return Canonical ID & Fetch Metadata from Neo4j]
    F -- No --> H[Prompt LLM to Coin a Canonical Name]
    
    H --> I{Is Coined Name 'NONE'?}
    I -- Yes --> J[Skip - Drop Invalid Skill]
    I -- No --> K[Upsert to Qdrant & Merge to Neo4j]
    
    K --> L[Return New Canonical ID]
```

## 🔄 3. Continuous WebSocket Integration

Because these flows involves heavy compute (Embedding, Vector Search, LLM Generation, Graph Traversal), a single `setup-role` operation can take 10 to 45 seconds.

Standard HTTP connections will timeout or leave the user staring at a blank loader. We solved this with `app/api/routers/websocket.py`.

* **Frontend**: Initiates a WebSocket connection: `ws://api/employer/ws/setup/{role_id}`.
* **Backend**: 
    1. Returns a 202 Accepted HTTP response to the original POST instantly.
    2. Modifies state locally.
    3. Triggers `manager.broadcast_to_session(role_id, payload)` asynchronously.
* **Result**: The frontend UI can dynamically check off boxes ("Parsing PDF..." -> "Extracting Skills..." -> "Normalizing against O*NET...") creating a modern, transparent "Execution Theatre" UX.
