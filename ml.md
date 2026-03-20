## ConFit Fine-Tuning — Complete Data & Training Flow

***

## Datasets Used

**Dataset 1 — Snehaanbhawal Resume Dataset**
Structure of the raw data:
```
Resume.csv
    ID          → unique resume ID
    Resume_str  → full resume text as one long string
    Category    → job category label (24 categories)
                  e.g. "Data Science", "Java Developer", "HR", "Finance"
```
That's it. Two useful columns — the raw resume text and the category label. No pre-extracted skills, no structured fields. Everything needs to be extracted from Resume_str.

**Dataset 2 — Kshitizregmi Jobs and JD Dataset**
Structure of the raw data:
```
jobs.csv (or similar)
    Job Title       → role name string
    Job Description → full JD text
```
Again, raw text. You extract everything from the JD text.

***

## What ConFit Needs as Input

The model needs **sentence pairs** where each pair is:
```
(resume_evidence_sentence, jd_requirement_sentence)
```

Both sentences are about the **same skill**. The pair is **positive** when they describe a similar level of expertise. The pair is a **hard negative** when they describe mismatched levels — same skill, different depth.

**Critical design decision:** You don't just send the raw skill name. You send the **contextual evidence sentence** — the actual description of what the person did with the skill. This is what teaches the model to distinguish depth, not just topic.

```
WRONG approach:
    anchor:   "PySpark"
    positive: "PySpark"

RIGHT approach:
    anchor:   "optimized PySpark jobs processing 10TB daily in production"
    positive: "5+ years PySpark experience in production-scale data pipelines"
```

The skill name alone has zero depth signal. The surrounding context is everything.

***

## Step 1 — Extract Skill Evidence Sentences from Resumes

For each resume in Dataset 1:

Send the resume text to GPT with this exact prompt:

```
You are a skill evidence extractor.

Given this resume, extract skill evidence sentences.
For each skill mentioned, find the sentence or phrase that best describes 
HOW the person used that skill — their actual work, not just the skill name.

Return JSON array:
[
  {
    "skill": "raw skill name as written in resume",
    "evidence": "exact sentence or phrase describing usage",
    "depth_signal": "surface|regular|deep|expert"
  }
]

Rules:
- evidence must describe actual work done, not just list the skill
- if resume only lists the skill with no context, set evidence = null
- depth_signal is your estimate of usage depth
- extract maximum 10 skills per resume

Resume:
{resume_text}
```

**What you get per resume (example):**
```json
[
  {
    "skill": "PySpark",
    "evidence": "optimized PySpark batch jobs processing 10TB daily, reducing runtime by 40%",
    "depth_signal": "deep"
  },
  {
    "skill": "SQL",
    "evidence": "wrote complex SQL queries for sales reporting dashboards",
    "depth_signal": "regular"
  },
  {
    "skill": "Python",
    "evidence": "Python",
    "depth_signal": null   ← no context, discard this
  }
]
```

**Filter:** drop any row where evidence is null or evidence == skill name. You only keep entries with real contextual sentences.

**Across 2400 resumes at ~5 valid skills each = ~12,000 evidence sentences.**

***

## Step 2 — Extract Requirement Sentences from JDs

For each JD in Dataset 2:

Send to GPT with this prompt:

```
You are a job requirement extractor.

Given this job description, extract skill requirement sentences.
For each required skill, find the sentence or phrase that best describes 
what level of proficiency is expected.

Return JSON array:
[
  {
    "skill": "raw skill name as written in JD",
    "requirement": "exact sentence describing what's expected",
    "level": "junior|mid|senior"
  }
]

Rules:
- requirement must describe the expected proficiency, not just list the skill
- if no context is given, set requirement = null
- level is inferred from surrounding context (years required, responsibilities)
- extract maximum 10 skills per JD

Job Description:
{jd_text}
```

**What you get per JD (example):**
```json
[
  {
    "skill": "PySpark",
    "requirement": "5+ years of PySpark experience in production-scale distributed environments",
    "level": "senior"
  },
  {
    "skill": "SQL",
    "requirement": "proficient in SQL for data analysis and reporting",
    "level": "mid"
  }
]
```

**Filter:** drop nulls. Keep only entries with real requirement sentences.

***

## Step 3 — Normalize Both Sides to O*NET Canonical Skills

Before pairing, normalize all raw skill names from both datasets to canonical O*NET skill names using your existing Qdrant + tiny LLM pipeline.

This is critical because resume says "Apache Spark" and JD says "PySpark" — without normalization they won't pair correctly.

```
Resume skill: "Apache Spark" → canonical: "Apache PySpark" (onet_4421)
JD skill:     "PySpark"      → canonical: "Apache PySpark" (onet_4421)
```

Now pairing is done on canonical_id, not raw string matching.

***

## Step 4 — Build the Positive Pairs

Match resume evidence sentences with JD requirement sentences where:
- Same canonical skill ID
- Same job category (resume Category == JD category inferred from job title)
- Compatible depth level — resume depth_signal and JD level should roughly match

```python
positive_pairs = []

for resume_skill in resume_evidence_rows:
    for jd_skill in jd_requirement_rows:
        if (
            resume_skill["canonical_id"] == jd_skill["canonical_id"]
            and resume_skill["category"] == jd_skill["category"]
            and depth_compatible(resume_skill["depth_signal"], jd_skill["level"])
        ):
            positive_pairs.append({
                "anchor":   resume_skill["evidence"],
                "positive": jd_skill["requirement"],
                "skill":    resume_skill["canonical_name"],
                "label":    1
            })
```

**depth_compatible logic:**
```python
def depth_compatible(resume_depth, jd_level):
    mapping = {
        ("deep", "senior"):   True,
        ("expert", "senior"): True,
        ("regular", "mid"):   True,
        ("surface", "junior"):True,
        ("deep", "mid"):      True,   # slightly lenient
    }
    return mapping.get((resume_depth, jd_level), False)
```

Target: ~400-600 clean positive pairs after filtering.

***

## Step 5 — Build the Hard Negative Pairs

Same canonical skill, same category, but **mismatched depth level**:

```python
hard_negatives = []

for resume_skill in resume_evidence_rows:
    for jd_skill in jd_requirement_rows:
        if (
            resume_skill["canonical_id"] == jd_skill["canonical_id"]
            and resume_skill["category"] == jd_skill["category"]
            and depth_mismatched(resume_skill["depth_signal"], jd_skill["level"])
        ):
            hard_negatives.append({
                "anchor":   resume_skill["evidence"],
                "positive": jd_skill["requirement"],
                "skill":    resume_skill["canonical_name"],
                "label":    0
            })
```

**depth_mismatched logic:**
```python
def depth_mismatched(resume_depth, jd_level):
    mismatches = {
        ("surface", "senior"): True,
        ("surface", "mid"):    True,
        ("regular", "senior"): True,
    }
    return mismatches.get((resume_depth, jd_level), False)
```

Target: ~200-300 hard negatives.

***

## Step 6 — Final Dataset Structure for Training

```python
# For MultipleNegativesRankingLoss you only need positive pairs
# Other items in the same batch automatically become in-batch negatives
# So your training InputExamples are only the positives

from sentence_transformers import InputExample

train_examples = [
    InputExample(texts=[pair["anchor"], pair["positive"]])
    for pair in positive_pairs
]

# Hard negatives are used separately for evaluation only
# They tell you how well the model separates mismatched pairs
eval_examples = hard_negatives
```

**What each InputExample contains:**
- `texts[0]` = resume evidence sentence e.g. *"optimized PySpark batch jobs processing 10TB daily"*
- `texts[1]` = JD requirement sentence e.g. *"5+ years PySpark in production-scale environments"*
- No skill name, no tags, no metadata — **pure sentence pair only**

The model learns to align these by meaning, not by keyword overlap. This is why it generalizes — it understands "10TB daily production batch jobs" ≈ "production-scale environments" semantically, not because "PySpark" appears in both.

***

## Step 7 — Fine-Tuning

```python
from sentence_transformers import SentenceTransformer, losses
from torch.utils.data import DataLoader

model = SentenceTransformer("all-MiniLM-L6-v2")

train_dataloader = DataLoader(train_examples, batch_size=32, shuffle=True)
train_loss = losses.MultipleNegativesRankingLoss(model)

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=3,
    warmup_steps=50,
    output_path="models/skillfit-minilm"
)
```

With batch size 32: each positive pair sees 31 other anchors as automatic negatives per forward pass. With 500 positives and 3 epochs = ~46 gradient steps with 31 negatives each = strong training signal from a small dataset.

**Training time: 15-20 minutes on Kaggle T4.**

***

## Step 8 — How It's Used at Runtime

During employee flow Step 3 (mastery computation), for each skill:

```python
skillfit = SentenceTransformer("models/skillfit-minilm")

resume_vec = skillfit.encode(skill["evidence"])
jd_vec     = skillfit.encode(skill["jd_requirement"])

alignment_score = cosine_similarity(resume_vec, jd_vec)
# Returns 0.0 to 1.0
# High = resume evidence closely matches what the JD expects
# Low  = surface mention vs deep requirement → contributes low mastery
```

This score replaces `context_depth_score` in the mastery formula. No GPT call, no subjectivity, pure geometric alignment between what the person did and what the role demands.