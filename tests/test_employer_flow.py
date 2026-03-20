import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.pdf_service import pdf_service
from app.services.employer_flow.orchestrator import orchestrate_employer_flow
from app.utils.logger import logger

async def test_employer_flow():
    temp_dir = "./temp"
    jd_path = os.path.join(temp_dir, "jd.pdf")
    team_path = os.path.join(temp_dir, "team.pdf")

    if not os.path.exists(jd_path):
        logger.error(f"Test Error: {jd_path} not found.")
        return

    logger.info("Test: Reading JD PDF...")
    with open(jd_path, "rb") as f:
        jd_bytes = f.read()
    
    team_bytes = b""
    if os.path.exists(team_path):
        logger.info("Test: Reading Team Context PDF...")
        with open(team_path, "rb") as f:
            team_bytes = f.read()
    else:
        logger.warning("Test Note: team.pdf not found. Proceeding without team context.")

    logger.info("Test: Starting employer flow orchestration...")
    try:
        results = await orchestrate_employer_flow("test_session_senior_role", jd_bytes, team_bytes, assumed_seniority="senior")
        print("\n--- EXTRACTED SKILLS WITH 2D TARGET MODELLING ---")
        import json
        print(json.dumps(results, indent=2))
        logger.info("Test completed successfully.")
    except Exception as e:
        logger.error(f"Test Flow failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_employer_flow())
