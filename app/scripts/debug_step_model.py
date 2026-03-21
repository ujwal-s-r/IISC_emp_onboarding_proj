"""
Debug: Test stepfun-ai/step-3.5-flash raw output.

This script tests the new Nvidia model with the team context prompt
to understand the exact response structure before integration.
"""
import asyncio
import sys
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

TEAM_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "temp", "team.pdf")
JD_PDF_PATH   = os.path.join(os.path.dirname(__file__), "..", "..", "temp", "jd.pdf")

SAMPLE_SKILLS = "Python, Machine Learning, Docker, Kubernetes, Data Engineering, PySpark, SQL, MLflow"

TEAM_CONTEXT_PROMPT = """
You are analyzing internal team documentation for a new hire.
Your goal is to find which of the provided 'skills' are actually mentioned in the team context, and determine their recency/importance.

For each skill provided in the list that is found in the text, determine:
1. Recency Category: "current_project", "past_project", or "general".
2. Reasoning: A brief explanation based on the text of why you assigned this recency.

Output MUST be a valid JSON array of objects with keys: "skill_name", "recency_category", "reasoning".
If a skill is NOT found, omit it from the array.

Target Skills to look for:
{skills_list}

Team Context Document:
{team_text}
"""

async def main():
    from openai import AsyncOpenAI
    from app.config import settings
    from app.services.pdf_service import pdf_service

    client = AsyncOpenAI(
        api_key=settings.NVIDIA_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1",
    )

    # Load and print PDF text previews
    with open(TEAM_PDF_PATH, "rb") as f:
        team_bytes = f.read()
    with open(JD_PDF_PATH, "rb") as f:
        jd_bytes = f.read()

    team_text = pdf_service.extract_text(team_bytes)
    jd_text   = pdf_service.extract_text(jd_bytes)

    print(f"\n{'='*65}")
    print(f"📄 JD TEXT (first 200 chars):\n{jd_text[:200]}")
    print(f"\n{'='*65}")
    print(f"📄 TEAM TEXT (first 200 chars):\n{team_text[:200]}")
    print(f"\n{'='*65}")

    # Test the team context prompt
    prompt = TEAM_CONTEXT_PROMPT.format(skills_list=SAMPLE_SKILLS, team_text=team_text)

    print("\n🚀 Calling stepfun-ai/step-3.5-flash (streaming)...\n")

    full_reasoning = []
    full_content   = []

    completion = await client.chat.completions.create(
        model="stepfun-ai/step-3.5-flash",
        messages=[{"role": "user", "content": prompt}],
        temperature=1,
        top_p=0.9,
        max_tokens=16384,
        stream=True,
    )

    async for chunk in completion:
        if not getattr(chunk, "choices", None):
            print(f"  [No choices chunk]: {chunk}")
            continue

        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        content   = getattr(delta, "content", None)

        if reasoning:
            full_reasoning.append(reasoning)
        if content:
            full_content.append(content)

    reasoning_str = "".join(full_reasoning)
    content_str   = "".join(full_content)

    print(f"\n{'='*65}")
    print(f"💭 REASONING (first 400 chars):\n{reasoning_str[:400] or '(empty)'}")
    print(f"\n{'='*65}")
    print(f"📦 CONTENT (full):\n{content_str}")
    print(f"\n{'='*65}")
    print(f"Stats: reasoning={len(reasoning_str)} chars, content={len(content_str)} chars")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, RuntimeError):
        pass
