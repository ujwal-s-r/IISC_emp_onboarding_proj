# AdaptIQ — Employer Flow Reference
### ARTPARK CodeForge Hackathon | Internal Development Reference

---

## What the Employer Flow Does

The employer flow is the setup phase of the system. Its job is to define the **target state** for onboarding: what the role expects, what the team actually uses, what resources are trusted internally, and what skill priorities matter for early productivity.

This flow runs once per role. After that, multiple employees can be onboarded against the same role configuration.

For hackathon scope, the entire employer flow is **fully automated**. The employer uploads the inputs, and the system processes everything without manual review or editing.

---

## Main Goal of Employer Flow

The employer side answers four questions before any employee enters the system:

1. What skills does the **job description** officially require?
2. What skills does the **team actually use** in real work right now?
3. What internal resources should be prioritized over generic web courses?
4. What should count as **Day-1 critical** vs. **learn gradually later**?

The employee flow depends completely on this setup.

---

## Employer Dashboard Scope

For the hackathon, the employer dashboard supports:

- Creating one role at a time
- Uploading a new role whenever needed
- Fully automated processing after upload
- No manual corrections or approval steps
- One PDF for team context to keep input simple
- Optional internal resource URLs

This keeps the build realistic for hackathon execution while still showing a strong product story.

---

## Employer Inputs

Each role setup consists of four inputs.

### 1. Job Description

The employer uploads the JD as text or PDF.

This is the formal description of the role and is used to determine the **official required skill set**. It represents what HR or hiring managers say the person should know.

Typical content extracted from the JD:
- Required tools and technologies
- Expected responsibilities
- Seniority level implied by the wording
- Nice-to-have skills
- Domain or workflow hints

---

### 2. Team Context Pack

The employer uploads a **single PDF** that contains team-specific information.

For hackathon simplicity, the docs should instruct the employer to combine all useful team data into one PDF before uploading. This avoids supporting many file types and complicated ingestion paths.

The team context PDF can contain:
- Current project overview
- Team tech stack
- Current sprint or roadmap summary
- Past project summaries
- Internal onboarding notes
- Team introduction
- Engineering practices or workflow notes
- Internal architecture notes
- Internal repo README content
- Team-owned tools and platforms
- Domain-specific terminology or business context

This input is the most important innovation in your system because it lets the model infer what the team **really needs right now**, not just what appears in the JD.

---

### 3. Role Seniority

The employer chooses one value:
- Junior
- Mid
- Senior
- Lead

This is used as a calibration signal when converting JD skills into target mastery values.

A senior role should expect a higher mastery threshold than a junior role, even if the same skill appears in both.

---

### 4. Curated Resources (Optional)

The employer can provide internal or trusted learning resources as URLs.

These can include:
- Team wiki pages
- Internal docs
- Engineering handbook pages
- Repo documentation
- Internal onboarding docs
- Trusted videos or articles
- Team-maintained tutorials

These resources are prioritized during retrieval later, so the employee sees team-approved material before generic internet content.

---

## Employer Processing Flow Overview

The employer flow has four core processing branches:

1. JD understanding
2. Team context understanding
3. Internal resource indexing
4. Graph expansion for unseen skills

All of these produce structured outputs that are stored and reused by the employee pipeline.

---

## Step 1 — Role Creation

When the employer clicks **Upload New Role**, the system creates a new role record.

This role becomes the container for:
- JD-derived skill requirements
- Team relevance signals
- Internal resources
- Skill tiers
- Team-specific vector collection
- Final target state for onboarding

Conceptually, the role is the anchor object that all employee onboarding sessions point to.

---

## Step 2 — Job Description Processing

The first major task is understanding what the role officially expects.

### What goes in

Input:
- JD PDF or JD text
- Selected role seniority

### What the system extracts

The JD is parsed and sent to the main LLM with a structured extraction prompt. The system asks it to identify:

- Role title
- Core required skills
- Nice-to-have skills
- Role-specific tooling
- Experience level expectations per skill
- Short description of how each skill is expected to be used

The goal is not just to extract the word "PySpark", but to understand whether the JD expects:
- basic familiarity,
- practical working knowledge,
- or production-grade expertise.

### What comes out

The output is a normalized skill requirement list like:

- Skill name
- Role-specific importance
- Inferred level
- Short expectation description

Then each extracted skill goes through the normalization layer so it maps to a canonical skill in the ontology.

### Why this matters

The JD gives the system the **formal target state**.

It tells the engine:
- what the role says it needs,
- what baseline to compare the employee against,
- and what mastery level should be targeted.

---

## Step 3 — Skill Normalization for JD Skills

The raw skill names extracted from the JD are not reliable enough to use directly.

For example:
- "Spark"
- "Apache Spark"
- "PySpark"
- "Spark framework"

could all refer to the same actual skill in your ontology.

### How normalization works

The raw skill string is embedded and searched against the canonical skill index. The top candidates are returned, and a small language model chooses the best canonical mapping from those candidates.

This gives:
- canonical skill ID
- canonical skill name
- normalization confidence
- candidate ranking trace

### Why this is needed

Without normalization:
- the system may think PySpark and Apache Spark are different skills,
- gap computation becomes noisy,
- graph traversal becomes unreliable,
- and recommendations become inconsistent.

Normalization makes every later stage deterministic.

---

## Step 4 — Assigning Target Mastery from JD

Once JD skills are normalized, the system converts them into **target mastery thresholds**.

This is how the engine knows what "good enough for the role" actually means.

### Example logic

A required skill in a senior role may get a target mastery of 0.85.

A required skill in a mid role may get 0.65.

A nice-to-have skill may get 0.30.

This is not a final employee score — it is the **goal state** used later in gap computation.

### Why this matters

The employee flow will later compute:

current mastery - versus - target mastery

So the JD processing must produce a clean, structured, quantitative target profile for the role.

---

## Step 5 — Team Context Pack Processing

This is the most important part of the employer flow.

The team context pack tells the system what matters in the **real working environment**, not just what is written in the JD.

### What goes in

A single PDF containing any mix of:
- current project docs,
- stack details,
- team notes,
- architecture docs,
- past project summaries,
- onboarding notes,
- internal readmes.

### What the system extracts

The LLM is asked to extract:
- technical skills mentioned
- platforms and tools mentioned
- mention frequency
- whether each skill is mentioned in:
  - current project context,
  - past project context,
  - or generic discussion
- domain-specific concepts
- internal tools or custom stack items
- workflow signals like Agile, experimentation, pipelines, dashboards, notebooks, etc.

### What this means practically

Suppose the JD mentions:
- PySpark
- Databricks
- PyTorch
- TensorFlow

But the team pack repeatedly mentions:
- PySpark
- Databricks
- Delta Lake
- Airflow

and never mentions PyTorch or TensorFlow.

Then the system infers:
- PySpark and Databricks are highly relevant
- Delta Lake and Airflow are operationally important even if lightly stated in the JD
- PyTorch and TensorFlow are probably low-priority for this team

This is how the system becomes **team-aware**, not just role-aware.

---

## Step 6 — Computing Team Relevance Scores

From the extracted team context mentions, each skill gets a relevance score.

This score answers:
**How important is this skill for this specific team, right now?**

### Signals used

- Mention count in the team pack
- Recency of the mention:
  - current project
  - past project
  - generic mention
- Whether the skill appears in implementation-heavy sections
- Whether it appears alongside critical project components

### Interpretation

High relevance means:
- the team uses it actively,
- the employee likely needs it soon,
- and it should be prioritized early in onboarding.

Low relevance means:
- the skill may still matter in the JD,
- but it is not urgent for this team's current work.

### Why this matters

This is the mechanism that converts a generic skill-gap engine into an **adaptive onboarding engine**.

It avoids the common onboarding failure:
everyone studies everything even when only 30% is actually needed in the first month.

---

## Step 7 — Tier Assignment

After team relevance is computed, each skill is assigned a priority tier.

### Tier meaning

- **T1** — Day-1 critical  
  The employee should learn this immediately before starting real work.

- **T2** — First-month essential  
  Important soon, but not necessarily before day one.

- **T3** — Gradual learning  
  Useful but can be learned over time.

- **T4** — JD-only / low real-world urgency  
  Present in the JD, but the team context suggests it is not currently important.

### Why tiers matter

Tiers become one of the most important control signals in the employee flow because they influence:
- path sequencing
- urgency
- optimization
- explanation
- UI color and grouping

This is where your idea of
"PySpark now, Databricks later"
gets operationalized.

---

## Step 8 — Detecting Unknown Skills and Expanding the Graph

Sometimes the team context pack or JD mentions a skill that is not present in O*NET or your existing graph.

Examples:
- very new tools
- internal platforms
- company-specific terminology
- newly popular products

### What happens then

The system triggers the self-expanding graph logic.

The LLM is asked:
- what prerequisites this new skill likely has,
- what other skills it unlocks,
- what category it belongs to,
- and where it fits in the existing ontology.

### What gets created

A new graph node is added for the skill.

Then edges are created to connect it with existing skills.

The new skill is also embedded and inserted into the canonical skill index so that future normalization can detect it directly.

### Why this matters

This prevents the system from failing whenever it sees a modern or custom team-specific skill.

It makes the graph **adaptive to employer input**, which is a very strong architectural point.

---

## Step 9 — Internal Resource Processing

If the employer supplies curated URLs, those are processed into the team-specific retrieval layer.

### What happens

Each URL is fetched and converted into clean text.

That text is chunked into smaller passages.

Each chunk is embedded and stored in the team-specific vector collection for that role.

The chunks carry payload metadata such as:
- source title
- URL
- inferred skill tags
- source type = internal

### Why this matters

Later, when the system retrieves learning resources for an employee, these internal resources are surfaced before generic catalog items.

That gives you:
- better grounding,
- more relevant learning material,
- and stronger product realism.

---

## Step 10 — Building the Role Knowledge Package

After all employer inputs are processed, the system has enough information to build a complete role package.

This package contains:

- Role identity
- JD-derived canonical skills
- Target mastery per skill
- Team relevance per skill
- Tier assignment per skill
- Team-specific internal resource vectors
- Expanded graph nodes if any new skill was discovered

This package is what the employee flow consumes.

Think of it as the **compiled onboarding target profile** for one role.

---

## What Gets Stored from Employer Flow

The employer flow does not just produce temporary outputs. It creates persistent structured state that powers all future employee onboarding runs for that role.

### Core stored outputs

#### Role profile
Contains:
- role title
- role seniority
- original JD text

#### Role skill targets
Contains:
- canonical skill ID
- canonical skill name
- target mastery threshold
- skill importance label

#### Team context signals
Contains:
- canonical skill ID
- mention count
- recency category
- computed relevance score
- assigned tier

#### Internal resources
Contains:
- source URL or document reference
- chunk text
- skill tags
- embeddings in the team-specific vector store

#### Graph expansions
Contains:
- new skill name
- generated relationships
- source of expansion
- time of creation

---

## Recommended Team Context PDF Contents for the Docs

You asked what exactly to tell teams to upload. This is the recommended doc guidance.

### Tell employers to combine these into one PDF:

- Team introduction
- Current project overview
- Key technologies used in the active project
- Past project summaries
- Engineering workflow notes
- Team-owned tools and dashboards
- Important internal concepts or domain terms
- Onboarding notes if available
- Important repo READMEs
- Architecture notes
- Internal best practices or coding standards
- Links or references to learning material the team already trusts

This gives the system enough signal to infer:
- what is urgent,
- what is recurring,
- what is team-specific,
- and what resources should be preferred.

---

## Best Course Catalog Strategy for the Hackathon

Based on the problem statement, the safest and strongest approach is:

### Use a pre-built, provided course catalog

The hackathon explicitly emphasizes:
- zero hallucinations
- strict adherence to the provided course catalog [file:59]

So the best design is **not** live web search during employee inference.

Instead:

1. Build a global catalog before the demo
2. Store it in SQLite + Qdrant
3. Let employer-provided resources extend it per role
4. Restrict the optimizer so it can only choose from indexed items

### Why this is best

- Strong grounding
- Reliable demo
- Fast inference
- Easy explanation to judges
- No hallucination risk
- Satisfies the score criterion directly [file:59]

### What the global catalog should contain

For hackathon scope:
- Around 150–200 real resources
- Covering around 30–40 common skills
- Mix of beginner/intermediate/advanced
- Real URLs
- Real durations
- Skill tags
- Short descriptions

### What the employer adds on top

The employer does **not** need to upload a full catalog.

They just add:
- team-specific trusted links
- internal docs
- internal readmes
- internal wikis

These become high-priority resources layered on top of the shared global catalog.

So your final catalog model is:

- **Global catalog** = pre-built by your system team
- **Role/team catalog extension** = uploaded by employer

That is the cleanest architecture for the hackathon.

---

## End-to-End Employer Flow Summary

1. Employer creates a new role.
2. Employer uploads:
   - JD
   - one team context PDF
   - role seniority
   - optional curated URLs
3. JD is parsed into canonical role skill requirements.
4. Team context is parsed into team relevance signals.
5. Skills are normalized into the ontology.
6. Unknown skills trigger graph expansion.
7. Target mastery is assigned from role expectations.
8. Team relevance and tiers are computed.
9. Curated resources are indexed into the team vector store.
10. Final role knowledge package is stored for employee onboarding.

---

## Why the Employer Flow Matters So Much

If the employer flow is weak, the employee flow becomes generic.

If the employer flow is strong, the employee flow becomes highly adaptive because it knows:

- what the role formally expects,
- what the team truly uses,
- what the urgent skills are,
- what can wait,
- and which resources are actually trusted.

This is what turns your system from a generic recommendation engine into an onboarding engine that feels company-aware and team-aware.

---

## Final Architecture Position of Employer Flow

The employer flow produces the **target state**.

The employee flow produces the **current state**.

The onboarding engine exists in the middle and computes:
- the gap,
- the order,
- the urgency,
- the best grounded resources,
- and the explanation for every recommendation.

Without the employer flow, the employee side has nothing meaningful to optimize against.

---

## Final Hackathon Scope Decisions

For the hackathon build, the employer flow is finalized as:

- Fully automated
- One role uploaded at a time
- Multiple roles supported through repeated uploads
- One PDF for team context
- Optional internal resource URLs
- Pre-built global catalog
- Team-specific catalog extension
- Self-expanding graph included
- Causal mask included later in employee-side optimization
- No manual correction flow
- No advanced admin features

This is realistic, strong, and fully aligned with what the problem statement expects around adaptive pathing, grounding, and reasoning trace. [file:59]
