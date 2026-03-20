import requests
import time

API_URL = "http://127.0.0.1:8000/api/v1"

def test_employer_setup():
    print("🚀 Triggering Employer Setup Flow...")
    files = {
        "jd_file": ("jd.pdf", open("temp/jd.pdf", "rb"), "application/pdf"),
        "team_context_file": ("team.pdf", open("temp/team.pdf", "rb"), "application/pdf")
    }
    data = {
        "title": "Senior Data Engineeer",
        "seniority": "Senior"
    }
    
    response = requests.post(f"{API_URL}/employer/setup-role", files=files, data=data)
    
    if response.status_code != 202 and response.status_code != 200:
        print(f"❌ Failed to initiate setup: {response.text}")
        return
        
    result = response.json()
    role_id = result.get("id")
    print(f"✅ Setup initiated! Role ID: {role_id}")
    
    print("\n⏳ Polling for completion (waiting for background orchestrator)...")
    
    for _ in range(60): # Poll for up to 120 seconds
        time.sleep(2)
        r = requests.get(f"{API_URL}/employer/roles/{role_id}")
        if r.status_code != 200:
            print(f"Error fetching role: {r.text}")
            continue
            
        role_data = r.json()
        skills = role_data.get("target_skills", [])
        
        if skills:
            print(f"\n🎉 SUCCESS! Orchestrator finished.")
            print(f"Retrieved {len(skills)} normalized skills:\n")
            for skill in skills:
                print(f" - {skill['skill_name']}  (Target Mastery: {skill['target_mastery']:.2f})")
                if skill.get("canonical_id"):
                     print(f"     -> Matched O*NET ID: {skill['canonical_id']}")
            return
            
    print("\n⚠️ Timed out waiting for orchestrator. Check Uvicorn logs!")

if __name__ == "__main__":
    test_employer_setup()
