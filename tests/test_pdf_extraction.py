import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.pdf_service import pdf_service
from app.utils.logger import logger

def test_extraction():
    temp_dir = "./temp"
    jd_path = os.path.join(temp_dir, "jd.pdf")
    team_path = os.path.join(temp_dir, "team.pdf")

    # 1. Test JD Extraction
    if os.path.exists(jd_path):
        logger.info(f"--- EXTRACTING JD: {jd_path} ---")
        with open(jd_path, "rb") as f:
            content = f.read()
            text = pdf_service.extract_text(content)
            print("\n=== START JD TEXT ===")
            print(text)
            print("=== END JD TEXT ===\n")
    else:
        logger.error(f"JD file not found: {jd_path}")

    # 2. Test Team Context Extraction
    if os.path.exists(team_path):
        logger.info(f"--- EXTRACTING TEAM CONTEXT: {team_path} ---")
        with open(team_path, "rb") as f:
            content = f.read()
            text = pdf_service.extract_text(content)
            print("\n=== START TEAM CONTEXT TEXT ===")
            print(text)
            print("=== END TEAM CONTEXT TEXT ===\n")
    else:
        logger.error(f"Team context file not found: {team_path}")

if __name__ == "__main__":
    test_extraction()
