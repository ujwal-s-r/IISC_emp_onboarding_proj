"""
Debug: Print raw team context LLM output to understand structure.
"""
import asyncio, sys, os
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

TEAM_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "temp", "team.pdf")

TEAM_CONTEXT_PROMPT = """
You are analyzing internal team documentation for a new hire.
Your goal is to find which of the provided 'skills' are actually mentioned in the team context, and determine their recency/importance.

For each skill provided in the list that is found in the text, determine:
1. Recency Category: "current_project", "past_project", or "general". (If currently critical, use current_project).
2. Reasoning: A brief explanation based on the text of why you assigned this recency.

Output MUST be a valid JSON array of objects with keys: "skill_name", "recency_category", "reasoning".
If a skill is NOT found, omit it from the array.

Target Skills to look for:
{skills_list}

Team Context Document:
{team_text}
"""

SAMPLE_SKILLS = "Python, Machine Learning, Docker, Kubernetes, Data Engineering, React, PySpark, SQL"

async def main():
    from app.services.pdf_service import pdf_service
    from app.services.agent_creator import agent_creator

    with open(TEAM_PDF_PATH, "rb") as f:
        team_bytes = f.read()
    team_text = pdf_service.extract_text(team_bytes)
    print(f"\n📄 Extracted {len(team_text)} chars from team.pdf")
    print(f"Team doc preview:\n{team_text[:400]}\n{'='*65}")

    llm = agent_creator.get_llm()
    prompt = TEAM_CONTEXT_PROMPT.format(skills_list=SAMPLE_SKILLS, team_text=team_text)
    resp = await llm.ainvoke(prompt)

    print(f"\n🤖 Raw LLM Response:")
    print(f"Type: {type(resp)}")
    print(f"Content:\n{resp.content}")
    print(f"\n--- Additional Response Attributes ---")
    for attr in ["response_metadata", "usage_metadata", "additional_kwargs"]:
        val = getattr(resp, attr, None)
        if val:
            print(f"{attr}: {val}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, RuntimeError):
        pass
