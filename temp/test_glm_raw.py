"""
Raw output probe for z-ai/glm4.7.
Run from the project root:
    python temp/test_glm_raw.py
"""
import asyncio
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

from app.clients.nvidia_llm_client import resume_llm_client

SAMPLE_RESUME = """
Ujwal S R | Python, FastAPI, TensorFlow, PySpark, Docker, SQL
Experience:
- AIML Intern @ Maersk (2025-2026): Built ML pipelines using PySpark on Databricks
  processing 5TB daily. Developed FastAPI microservices for real-time scoring.
- Projects: Fine-tuned BERT for NER using PyTorch. Deployed containerized apps on Kubernetes.
Skills: Python, PySpark, FastAPI, PyTorch, TensorFlow, Docker, Kubernetes, SQL, Git
"""

PROMPT = (
    "You are an expert Technical Skills Extractor. Extract skills from this resume.\n\n"
    "For each technical skill, extract:\n"
    "1. skill_name: The raw skill name (e.g., PySpark)\n"
    "2. context_depth: Short phrase of HOW they used it\n\n"
    "Return strictly a JSON array inside a ```json block only.\n"
    "Example:\n"
    "```json\n"
    '[{"skill_name": "Python", "context_depth": "Built backend APIs"}]\n'
    "```\n\n"
    "Resume:\n"
    + SAMPLE_RESUME
)


async def main():
    print("=" * 60)
    print("STREAMING (reasoning=grey, content=white)")
    print("=" * 60)

    reasoning, content = await resume_llm_client.stream(
        PROMPT,
        temperature=0.3,
        max_tokens=16384,
    )

    print()
    print("=" * 60)
    print("POST-STREAM DIAGNOSTICS")
    print("=" * 60)
    print(f"reasoning_length : {len(reasoning)}")
    print(f"content_length   : {len(content)}")
    print()
    print("--- CONTENT (repr) ---")
    print(repr(content))
    print()
    print("--- REASONING first 600 chars (repr) ---")
    print(repr(reasoning[:600]))


if __name__ == "__main__":
    asyncio.run(main())
