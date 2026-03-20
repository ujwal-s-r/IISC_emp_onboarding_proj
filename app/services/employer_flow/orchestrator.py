from app.services.agent_creator import agent_creator
from app.services.pdf_service import pdf_service
from app.utils.logger import logger
from app.api.routers.websocket import manager
import json

# 1. Prompts
JD_EXTRACTION_PROMPT = """
You are an expert HR and Technical Skills Analyst. Your task is to extract required skills from the following Job Description (JD).
For each skill, you must identify:
1. Canonical Skill Name (e.g., 'Apache PySpark' instead of 'Spark').
2. Required JD Level: 'junior', 'mid', 'senior', or 'lead'.
3. Knowledge Category: 'framework', 'language', 'platform', or 'concept'.
4. Brief Reasoning: Why this level and category were assigned based on the text.

Output MUST be a valid JSON array of objects with the following keys exactly:
"skill_name", "jd_level", "category", "reasoning".

Job Description:
{jd_text}
"""

TEAM_CONTEXT_PROMPT = """
You are analyzing internal team documentation for a new hire.
Your goal is to find which of the provided 'skills' are actually mentioned in the team context, and determine their recency/importance.

For each skill provided in the list that is found in the text, determine:
1. Recency Category: "current_project", "past_project", or "general". (If currently critical, use current_project).

Output MUST be a valid JSON array of objects with keys: "skill_name", "recency_category".
If a skill is NOT found, omit it from the array.

Target Skills to look for:
{skills_list}

Team Context Document:
{team_text}
"""

# 2. Master Matrix Logic
# Seniority X Tier -> Target Mastery
MASTERY_MATRIX = {
    "intern": {"T1": 0.35, "T2": 0.20, "T3": 0.10, "T4": 0.10},
    "junior": {"T1": 0.50, "T2": 0.35, "T3": 0.20, "T4": 0.20},
    "mid":    {"T1": 0.70, "T2": 0.55, "T3": 0.35, "T4": 0.35},
    "senior": {"T1": 0.85, "T2": 0.70, "T3": 0.50, "T4": 0.50},
    "lead":   {"T1": 0.95, "T2": 0.80, "T3": 0.60, "T4": 0.60}
}
# Assuming T3/T4 are the same column based on user's table (T3/T4).

def calculate_tier(recency: str) -> str:
    """Simple heuristic to assign Tier based on Team Context recency."""
    if recency == "current_project": return "T1"
    if recency == "general": return "T2"
    if recency == "past_project": return "T3"
    return "T4" # Not mentioned in team context

async def orchestrate_employer_flow(role_id: str, jd_bytes: bytes, team_bytes: bytes, assumed_seniority: str = "senior"):
    """Orchestration for Phase 2: JD & Team parsing -> 2D Mastery Calculation."""
    
    # --- STEP 1: PARSE PDFS ---
    await manager.broadcast_to_session(role_id, {"step": "pdf_processing", "status": "in_progress", "message": "Parsing PDFs..."})
    jd_text = pdf_service.extract_text(jd_bytes)
    team_text = pdf_service.extract_text(team_bytes) if team_bytes else ""
    
    # --- STEP 2: EXTRACT JD SKILLS ---
    await manager.broadcast_to_session(role_id, {"step": "jd_extraction", "status": "in_progress", "message": "Extracting JD requirements..."})
    llm = agent_creator.get_llm()
    
    jd_resp = await llm.ainvoke(JD_EXTRACTION_PROMPT.format(jd_text=jd_text))
    # Basic JSON cleanup
    cleaned_json = jd_resp.content.strip()
    if cleaned_json.startswith("```json"): cleaned_json = cleaned_json[7:]
    if cleaned_json.endswith("```"): cleaned_json = cleaned_json[:-3]
    skills_json = json.loads(cleaned_json)

    # --- STEP 3: ANALYZE TEAM CONTEXT ---
    await manager.broadcast_to_session(role_id, {"step": "team_analysis", "status": "in_progress", "message": "Analyzing Team Context for skill relevance..."})
    extracted_skill_names = [s["skill_name"] for s in skills_json]
    
    team_signals = []
    if team_text.strip():
        team_resp = await llm.ainvoke(TEAM_CONTEXT_PROMPT.format(skills_list=", ".join(extracted_skill_names), team_text=team_text))
        cleaned_team = team_resp.content.strip()
        if cleaned_team.startswith("```json"): cleaned_team = cleaned_team[7:]
        if cleaned_team.endswith("```"): cleaned_team = cleaned_team[:-3]
        team_signals = json.loads(cleaned_team)

    # Convert team signals to dict for easy lookup
    signal_map = {sig["skill_name"].lower(): sig["recency_category"] for sig in team_signals}

    # --- STEP 4: 2D TARGET COMPUTATION ---
    await manager.broadcast_to_session(role_id, {"step": "mastery_computation", "status": "in_progress", "message": "Computing optimal target masteries via 2D matrix..."})
    
    final_skills = []
    for skill in skills_json:
        name_lower = skill["skill_name"].lower()
        recency = signal_map.get(name_lower, "none")
        tier = calculate_tier(recency)
        
        # Use the Role's overall seniority, or fallback to JD level if specified. Here we use the assumed_seniority logic.
        sen = assumed_seniority.lower()
        if sen not in MASTERY_MATRIX: sen = "mid"
        
        target = MASTERY_MATRIX[sen][tier]
        
        final_skills.append({
            "skill_name": skill["skill_name"],
            "category": skill["category"],
            "tier": tier,
            "team_recency": recency,
            "target_mastery": target,
            "reasoning": skill["reasoning"]
        })

    # --- COMPLETE ---
    await manager.broadcast_to_session(role_id, {"step": "completed", "status": "completed", "message": "Employer Flow complete.", "data": {"skills": final_skills}})
    return final_skills
