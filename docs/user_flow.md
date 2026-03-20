# AdaptIQ — Complete Architecture & Flow Reference
### ARTPARK CodeForge Hackathon | Internal Development Reference

---

## What This System Does

AdaptIQ takes a new hire's resume and a company's job description, understands the skill gap between them, factors in what the team actually uses day-to-day, and generates a personalized learning path that gets the person productive as fast as possible. The key differentiation is that it doesn't just look at what the JD says — it infers what the team genuinely needs right now vs. what can be learned gradually vs. what is listed in the JD but irrelevant to this team entirely. Every decision the system makes is exposed in a live execution panel in the UI so the user can see exactly why each course was recommended.

---

## Two Entry Points

The system has two separate dashboards — one for the employer/manager who sets up the role, and one for the employee who gets onboarded. The employer runs first and creates all the context that the employee pipeline depends on.

---

## PART 1 — PRE-SYSTEM SETUP (Run Once at Deployment)

Before any user touches the system, the O*NET dataset needs to be loaded and the base knowledge graph needs to be built. O*NET is a US Department of Labor database that contains a canonical taxonomy of skills, tools, knowledge areas, and how they relate to job roles. It's the backbone of skill normalization in this system.

### O*NET Loading

From the O*NET download, you use four files: Skills.txt, Technology Skills.txt, Knowledge.txt, and the Skills-to-Occupation mapping. From these you build a canonical skill dictionary where every real-world way of writing a skill — "Apache Spark", "PySpark", "pyspark", "Spark framework" — maps to one canonical entry like "Apache PySpark" with a stable ID. Each canonical skill also gets a decay_category assigned: framework (tools that change with versions, decay fast), language (Python fundamentals, decay slow), platform (cloud/SaaS products, decay fastest), or concept (algorithms, SQL logic, barely decay).

Each canonical skill gets embedded using MiniLM sentence-transformers and stored in Qdrant in a collection called `onet_skills`. The vector is the embedding of the skill name plus its O*NET description. This collection is what powers skill normalization later — when a resume says "distributed data wrangling with spark", a Qdrant search here returns the top 5 closest canonical skill names.

### Neo4j Base Graph

The skill graph is built in Neo4j with two types of nodes and three types of relationships. Every canonical skill is a (:Skill) node. The three relationships are:

REQUIRES — a directed prerequisite edge. Python REQUIRES nothing, PySpark REQUIRES Python, Delta Lake REQUIRES PySpark, Databricks REQUIRES Delta Lake. This encodes that you cannot learn Delta Lake without knowing PySpark first. These come from O*NET co-occurrence data plus manual curation.

CAUSALLY_IMPROVES — a causal edge distinct from REQUIRES. This says that mastering skill A has been shown to cause measurable improvement in skill B, not just that they tend to appear together. For example, PySpark mastery causally improves Delta Lake performance with an effect_size of 0.72. This is what powers the causal mask in the recommendation step.

RELATED_TO — lateral relationships between skills at the same level, sourced from O*NET.

### Course Catalog Indexing

Courses are scraped from Coursera, YouTube, and Udemy and stored in two places: the courses table in SQLite with metadata (title, URL, skill tags, level, duration hours, source), and as vectors in Qdrant in a collection called `global_catalog`. Each course vector is the embedding of its title plus skill tags. When the employer uploads internal resources, those go into a separate Qdrant collection per role called `team_{role_id}`, giving team-specific materials priority over generic external courses.

---

## PART 2 — EMPLOYER FLOW

The employer sets up a role once. After this, any number of employees can be onboarded to that role and the system already knows what to target.

### What the Employer Uploads

The employer provides four things: a Job Description (text or PDF), a Team Context Pack (any combination of PDFs, DOCX files, or plain text describing the team, their current project, past projects, and tech stack), optional Curated Resources (URLs or PDFs the team already trusts), and a seniority level for the role (Junior/Mid/Senior/Lead).

### Processing the JD

The JD text is sent to GPT with a structured extraction prompt that asks for each required skill, what level it's needed at (senior/mid/junior), and a one-sentence description of what that level means in context. The extracted skills are then normalized to O*NET canonical names (explained fully in Section 5.2). Once normalized, each skill gets a target mastery score: senior maps to 0.85, mid to 0.65, junior to 0.40, nice-to-have to 0.30. These targets are stored in the role_skills table in SQLite and are what the employee's actual mastery gets subtracted from to compute the skill gap.

### Processing the Team Context Pack

This is where the system becomes genuinely different from every other onboarding tool. The team context pack is sent to GPT with a prompt asking it to list every technical skill and tool mentioned across all documents, how many times each appears, and whether it appears in the context of the current active project, a past project, or just a general mention. The output is a list of skill mentions with counts and recency categories.

These are then normalized to O*NET canonical names and stored in the team_context table in SQLite. The recency category and mention count together produce a team relevance score for each skill. A skill mentioned 12 times in the current project description gets a relevance score close to 1.0. A skill mentioned twice in a past project gets around 0.5. A skill in the JD that doesn't appear anywhere in the team docs gets a relevance score of 0.05 — it's not suppressed by the employer explicitly, it's inferred as low priority because the team doesn't seem to use it. This is how PyTorch gets deprioritized without anyone typing "suppress PyTorch".

From the relevance score plus the gap size (computed later per employee), each skill gets a tier: T1 means it's critical on day one — high team relevance and a large gap. T2 means it's needed in the first month — medium relevance or medium gap. T3 means it can be learned gradually. T4 means it's in the JD but the team doesn't seem to use it, shown grayed out in the UI as optional.

### Self-Expanding Graph Trigger

When the employer uploads team context that mentions a tool not yet in the Neo4j graph — for example "Databricks Unity Catalog" which might be too new for O*NET — the system triggers the self-expanding graph. GPT is asked: given this new skill name and all the skills already in the graph, what are its prerequisites, what skills does it unlock, and what O*NET category does it belong to? GPT returns a structured JSON with these relationships. The system then creates a new (:Skill) node in Neo4j with the appropriate REQUIRES edges, embeds the skill name and description with MiniLM, upserts it into the Qdrant onet_skills collection, adds it to the SQLite skill_ontology table, and logs the expansion in skill_graph_expansions. The graph is now aware of this skill for all future employees.

### Curated Resources

Each internal PDF or URL the employer uploads gets parsed into 512-token chunks using LangChain's text splitter, each chunk gets embedded with MiniLM, and the vectors are upserted into the team_{role_id} Qdrant collection with a payload containing the title, chunk index, and GPT-extracted skill tags. These will be surfaced with priority over external courses during retrieval.

---

## PART 3 — EMPLOYEE FLOW

This is the core pipeline that runs for every new hire. There are 12 logical steps. Each step produces outputs that feed into the next, and every intermediate result is persisted in SQLite and surfaced in the Execution Theatre UI.

---

### Step 1 — Resume Ingestion and GPT Extraction

The employee uploads their resume PDF. pdfplumber converts it to raw text. That text is sent to GPT with a structured extraction prompt that asks for: the candidate's full career timeline (each role with title, company, start year, end year, duration in years, seniority level, list of skills used, and a one-sentence description of HOW they used each skill), certifications with year and skill tags, and notable projects with scale (personal/academic/internal/production) and skills used.

The seniority level is inferred by GPT from the job title — "Software Analyst" → junior, "Senior Data Engineer" → senior. The skill_context field per skill is the most important part: it captures "optimized PySpark jobs processing 10TB daily" vs. "used PySpark in a tutorial" — same skill name, completely different depth of usage.

The full parsed JSON is stored in the employees table alongside the raw resume text. This JSON is the input to all subsequent steps.

---

### Step 2 — Skill Normalization via Qdrant + Tiny LLM

Every unique skill string across the entire career timeline needs to be mapped to its O*NET canonical name so the system can do mathematics on skills without ambiguity. "Apache Spark", "PySpark", "Spark" should all resolve to one canonical ID.

This is a two-stage process. First, the raw skill string is embedded with MiniLM and a Qdrant search returns the top 5 closest canonical skills from the onet_skills collection, each with a similarity score. Second, those 5 candidates plus the original raw string are passed to a tiny local LLM (Qwen2.5-0.5B or Phi-3-mini) with a prompt asking it to pick the best match. The Qdrant search is fast and handles most cases, but the tiny LLM adds natural language understanding to disambiguate edge cases like "distributed data wrangling" → PySpark rather than Hadoop.

The Qdrant similarity score of the chosen candidate becomes the normalization_confidence score (C_norm), a number between 0 and 1. This confidence score directly enters the mastery formula later — a skill that matched with 0.97 confidence contributes more to mastery than one that matched ambiguously at 0.78.

If the top candidate's similarity score is below 0.75, the skill is considered unknown and the self-expanding graph is triggered automatically, adding this skill to Neo4j and Qdrant for future use.

All normalization results are stored in the employee_skills_raw table: raw string, canonical ID, canonical name, confidence score, and all five candidates with their scores for full traceability.

The Execution Theatre shows a table of every skill mapping, the Qdrant scores, and which candidate the tiny LLM chose.

---

### Step 3 — Mastery Score Computation

For each canonical skill the employee has, a mastery score between 0 and 1 is computed from five signals. This is not a black box — every component is stored separately and shown in the UI.

**Years Score** is the total number of years the employee used this skill across all roles, normalized to a ceiling of 5 years (5 years = 1.0). Someone who used PySpark for 3 years gets 0.60.

**Recency Score** is how recently they last used it. If they used it in their most recent role, the score is high. If they haven't used it in 4 years, it decays linearly to near zero. The formula is: 1.0 minus (years since last use divided by 5), clamped to 0.

**Seniority Score** is the highest seniority level at which they used this skill, mapped to a number. Intern = 0.10, Junior = 0.30, Mid = 0.60, Senior = 0.85, Lead = 1.00. Using PySpark as a Senior Data Engineer signals deeper usage than using it as an intern.

**Context Depth Score** comes from GPT. All the skill_context strings extracted in Step 1 are sent to GPT in a single batch call. GPT rates each one from 0 to 1: 0.2 means "mentioned only or in passing", 0.5 means "regular use in normal tasks", 0.8 means "optimized, led, or architected", 1.0 means "expert-level with demonstrated complexity". This is one single GPT call per employee covering all their skills.

**Ebbinghaus Temporal Decay** applies the forgetting curve to the raw mastery estimate. Skills decay over time when not actively used. The decay rate varies by category: frameworks decay at λ=0.15 per year (tools change versions and feel unfamiliar), platforms at λ=0.20 (cloud interfaces change fast), languages at λ=0.05 (Python fundamentals are durable), and concepts at λ=0.03 (SQL logic barely fades). The decay factor is e raised to the power of negative lambda times years since last use. A PySpark score from 2 years ago decays by a factor of e^(-0.15 × 2) ≈ 0.74.

The final mastery formula combines all five signals:

M_skill = (0.30 × years_score + 0.25 × recency_score + 0.20 × seniority_score + 0.25 × context_depth_score) × decay_factor × normalization_confidence

Each component is stored individually in the employee_mastery table so any judge or developer can verify every number. Certifications add a small bonus (0.10, also decayed by years since certification) on top of the computed score.

---

### Step 4 — Team Relevance Inference and Tier Assignment

The team_context table was populated during the employer setup. For each canonical skill in the gap, the system looks up its mention count and recency category in that table. The relevance score formula is: 0.60 multiplied by the recency weight (current project = 1.0, past project = 0.5, general mention = 0.2) plus 0.40 multiplied by frequency score (mention count divided by 10, capped at 1.0).

A skill not found in the team context table at all gets a relevance score of 0.05 — not zero, because it might still be worth learning, just not urgent.

Tier assignment uses both relevance and gap size together. T1 requires relevance ≥ 0.80 and gap ≥ 0.50. T2 requires relevance ≥ 0.50 and gap ≥ 0.30. T3 is anything with relevance ≥ 0.20. T4 is everything else. This tier directly controls where in the learning path a skill appears and what color it gets in the UI.

---

### Step 5 — Skill Gap Computation

The gap for each skill is simply target mastery (from role_skills table) minus current mastery (from employee_mastery table), but only if the result is greater than 0.05. Tiny gaps below 0.05 are ignored as negligible. The raw gap is stored alongside a weighted_gap which is raw_gap multiplied by the team relevance score. The weighted_gap is what NSGA-II uses for its coverage objective — covering a high-relevance gap scores more than covering a low-relevance gap of the same size.

---

### Step 6 — Neo4j KG Query, Prerequisite Validation, and Self-Expanding Graph

With the gap skills identified, a Cypher query runs against Neo4j to fetch all REQUIRES chains up to 3 hops deep for all gap skills. For example, if Delta Lake is in the gap, the query returns PySpark → Delta Lake and Python → PySpark → Delta Lake. For each prerequisite returned, the system checks if the employee's mastery of that prerequisite is above 0.60 (the threshold for "sufficiently learned"). If a prerequisite is below threshold and not already in the gap vector, it is automatically injected as a T1 skill with the reason "prerequisite for [target skill]". This ensures the path never recommends Delta Lake before ensuring PySpark is covered.

After prerequisite validation, all gap skills including auto-added prerequisites are passed through NetworkX topological sort on the subgraph of just those skills. The topological order is the hard-ordered sequence that the optimizer must respect — it cannot place Databricks before Delta Lake, period.

If during normalization any skill was unknown and the self-expanding graph was triggered, that new Neo4j node is available by this step and participates in the prerequisite query normally.

The Execution Theatre shows the Neo4j subgraph rendered interactively using vis.js or a similar library, the Cypher query that was run, any auto-added prerequisites highlighted in orange, and any self-expanded skills marked with a special icon.

---

### Step 7 — Causal Mask Application

Before course retrieval and optimization, a second Neo4j query fetches all CAUSALLY_IMPROVES edges between the gap skills. This tells the system which courses have multiplicative value — a course that teaches PySpark doesn't just close the PySpark gap, it causally improves Delta Lake mastery with an effect_size of 0.72.

Each course candidate retrieved from Qdrant in the next step receives a causal_score: the sum of effect sizes for all causal edges where the course's skill tags appear on the source side. The total ranking score per course is 40% gap coverage, 30% team relevance, and 30% causal score. This means a course that causally improves multiple downstream skills is strongly preferred over one that's equally direct but causally isolated.

The reasoning trace for causal recommendations explicitly states "this course is recommended because mastering it causally improves [skill] with effect size [X], not merely because learners tend to take them together." This is the line that will make IISc judges stop and re-read the slide.

---

### Step 8 — NSGA-II Multi-Objective Path Optimization

pymoo's NSGA-II algorithm finds the Pareto-optimal set of course assignments across all gap skills simultaneously. The decision variable is which course from the candidate pool to assign to each skill. There are four objectives being optimized at once.

F1 is gap coverage — the sum of gap_coverage_score across all selected courses, negated because pymoo minimizes. F2 is team relevance — the sum of team relevance scores of selected courses, negated. F3 is total learning hours — minimized directly because we want to respect the learner's time. F4 is tier priority score — a weighted score that rewards placing T1 skills early in the path and penalizes placing them late, negated.

The topological order from Step 6 is enforced as a hard constraint — the optimizer cannot violate prerequisite ordering regardless of what the objectives say.

NSGA-II runs for 100 generations with a population of 50. After convergence it produces a Pareto front — a set of solutions that are each optimal in different trade-off combinations. The system selects the Pareto-optimal solution with the minimum total learning hours (F3) as the recommended path, because among all solutions that fully cover the gap with good team relevance, the shortest one respects the learner most.

The Execution Theatre shows the Pareto front as a 3D scatter plot with the selected solution highlighted.

---

### Step 9 — Qdrant Grounded Course Retrieval

For each skill in the ordered gap, the system builds a query string combining the canonical skill name and the tier level (e.g. "Apache PySpark T1 intermediate level course"), embeds it with MiniLM, and searches Qdrant. The team_{role_id} collection is searched first and results get a 1.3x score boost. The global_catalog collection is searched second. Results are merged, deduplicated by course_id, and the top 5 candidates per skill are passed to NSGA-II as the course pool for that skill.

This is the grounding guarantee — NSGA-II can only pick from courses that exist in the indexed catalog. The system cannot hallucinate a course that was never indexed. This directly satisfies the "zero hallucinations, strict catalog adherence" criterion worth 15% of the score.

---

### Step 10 — LangGraph Reasoning Trace

After NSGA-II selects the optimal course per skill, a LangGraph agent with four sequential nodes generates the reasoning trace. The gap_explainer node explains why the gap exists with the exact numbers (current mastery with decay shown, target mastery, gap size). The course_selector node explains why this specific course was chosen over the other candidates with scores compared. The order_justifier node explains why this skill appears at its position in the path using the Neo4j prerequisite chain. The tier_explainer node explains why this skill is T1/T2/T3 using the team context mention count and recency.

The full reasoning trace per skill is stored in the reasoning_traces table and shown in the Execution Theatre and on hover in the final roadmap.

---

### Step 11 — Bayesian Uncertainty and Diagnostic Quiz

After mastery scores are computed, for each skill a Beta distribution is fitted using the mastery score as the mean. Alpha = mastery × 10, Beta = (1 - mastery) × 10. The variance of this Beta distribution is computed. High variance means the system isn't confident about its mastery estimate — typically when a skill has ambiguous or conflicting evidence (e.g., used at a senior level but only for 3 months two years ago).

If the variance exceeds the threshold of 0.02, the skill is flagged in the diagnostic_flags table and the UI shows a locked quiz card before that skill's course. The employee answers 5 targeted questions. Their answers update the mastery score in SQLite and the pipeline from Step 5 onward reruns with the new, sharper mastery estimate. The path may change based on quiz results — this is the "truly adaptive" part of the system.

---

### Step 12 — Persistence and UI Rendering

All results are written to the employee_paths table: the ordered skill sequence, the selected courses with metadata, the full reasoning trace, the diagnostic flags, the tier breakdown, total learning hours, and the NSGA-II Pareto scores for transparency.

The frontend reads this table and renders the final learning roadmap as an interactive DAG using ReactFlow. Each node represents one course, colored by tier (T1=red, T2=orange, T3=green, T4=grey). Internal team resources have a blue border. Hovering a node shows the reasoning trace popup. Clicking opens the course URL. Locked nodes (diagnostic quiz pending) show a lock icon and the quiz UI. As the employee marks courses complete, mastery scores update in SQLite and the path can re-optimize dynamically if gaps close faster or slower than expected.

---

## DATA FLOW SUMMARY TABLE

| Step | Input | Process | Output | Stored In |
|---|---|---|---|---|
| 1 | Resume PDF | pdfplumber + GPT extraction | career_timeline JSON | SQLite: employees |
| 2 | Raw skill strings | MiniLM embed + Qdrant search + Tiny LLM rerank | canonical skills + confidence scores | SQLite: employee_skills_raw |
| 3 | Career timeline + canonical skills | Mastery formula (years, recency, seniority, depth, decay, confidence) | mastery_vector {skill: 0.0-1.0} | SQLite: employee_mastery |
| 4 | team_context table | Relevance formula + tier assignment | relevance scores + T1-T4 tiers | SQLite: team_context (read) |
| 5 | mastery_vector + role_skills + team relevance | Gap = target - current, weighted by relevance | gap_vector with tiers | In-memory, used in next steps |
| 6 | gap_vector | Neo4j Cypher query + topological sort | ordered skill sequence with auto-added prereqs | Neo4j (expansions to SQLite) |
| 7 | ordered skills + Neo4j causal edges | Causal score per course candidate | causal_score per course | In-memory scoring |
| 8 | Course pools per skill + causal scores | NSGA-II 4-objective optimization | Optimal course per skill | In-memory, fed to Step 12 |
| 9 | Per-skill query | Qdrant team-first search + global fallback | Top 5 course candidates per skill | Qdrant (read) |
| 10 | Optimal path + gap data | LangGraph 4-node CoT agent | Reasoning trace per skill | SQLite: reasoning_traces |
| 11 | mastery_vector | Beta distribution variance check | Diagnostic flags | SQLite: diagnostic_flags |
| 12 | All above | Assemble + persist | Final learning path | SQLite: employee_paths → UI |

---

## KEY DESIGN DECISIONS AND WHY

**Why Neo4j instead of NetworkX for the main graph?** Neo4j persists the graph across sessions, supports Cypher queries for flexible traversal, and visually renders in the Execution Theatre. NetworkX is used only for in-memory topological sort on the subgraph extracted per query.

**Why separate REQUIRES and CAUSALLY_IMPROVES edges?** Prerequisites are logical constraints (you cannot learn Delta Lake without PySpark). Causal edges are probabilistic improvements (knowing PySpark helps Delta Lake mastery by a measurable amount). Conflating them would misrepresent the reasoning.

**Why is team relevance inferred instead of explicitly set by the employer?** Explicit suppression requires employer effort and is prone to error. Inference from document frequency and recency is automatic, scales to any team pack, and is grounded in actual team behavior rather than what someone thinks they use.

**Why is the normalization confidence score multiplied into the mastery formula?** A skill that GPT extracted as "some kind of distributed processing tool" and matched to PySpark with 0.78 confidence should contribute less to mastery than "PySpark" matching with 0.97 confidence. The confidence acts as a reliability weight on the entire mastery estimate for that skill.

**Why NSGA-II instead of a greedy algorithm?** A greedy algorithm would pick the best course for each skill independently. NSGA-II optimizes all skills simultaneously, which allows it to discover that one course covering two skills is better than two separate courses even if neither is individually optimal. The Pareto front also gives you multiple valid alternatives if the top recommendation doesn't suit the employee.

**Why Beta distribution instead of just using the mastery score directly?** The mastery score is a point estimate. The Beta distribution captures uncertainty around that estimate. Two employees can both have PySpark mastery = 0.50 — one because they used it consistently for 1 year at mid level (low variance, high confidence), one because they used it intensely for 3 months as a senior 3 years ago (high variance, uncertain). The Beta distribution distinguishes these cases and triggers a diagnostic quiz only for the uncertain one.

---

## WHAT THE EXECUTION THEATRE SHOWS

The Execution Theatre is a sidebar panel in the UI that renders one card per pipeline step. Each card is collapsed by default and expands on click. This is not decorative — it is the mechanism by which the system satisfies the Reasoning Trace scoring criterion. Users and judges can inspect the exact Qdrant query vectors, the Neo4j Cypher queries, the mastery score components, the Pareto front chart, the LangGraph CoT output, and the Beta distribution charts for uncertain skills. Nothing is hidden inside a black box.

---

## WHAT IS TIME-PERMITTING

**ConFit-style contrastive skill encoder:** A MiniLM fine-tuned on (resume evidence, JD requirement) positive pairs using MultipleNegativesRankingLoss. This would replace the GPT context depth score with a geometrically-learned alignment score. Data generated via GPT augmentation (~400 pairs), trained in ~15 minutes on Kaggle T4 GPU. If time permits, this replaces context_depth_score in the mastery formula with a more principled similarity measure.

**Self-expanding graph** is included in the main architecture above, not time-permitting.

**Causal mask** is included in the main architecture above, not time-permitting.

---

*AdaptIQ v1.0 | Reference document for development. No need to refer back to the conversation.*
'''