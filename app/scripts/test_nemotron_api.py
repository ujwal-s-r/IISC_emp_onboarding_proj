import requests
import json
from app.config import settings

def test_nemotron():
    response = requests.post(
      url="https://openrouter.ai/api/v1/chat/completions",
      headers={
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
      },
      data=json.dumps({
        "model": "nvidia/nemotron-nano-9b-v2:free",
        "messages": [
          {
            "role": "user",
            "content": "What is the capital of France?"
          }
        ]
      })
    )
    
    print("Status Code:", response.status_code)
    try:
        data = response.json()
        print(json.dumps(data, indent=2))
        
        # Test what async OpenAI SDK would see:
        if "choices" in data and len(data["choices"]) > 0:
            print("\nExtracted text:", repr(data["choices"][0].get("message", {}).get("content")))
        else:
            print("\nNo choices found!")
            
    except Exception as e:
        print("Failed to parse JSON:", e)
        print("Raw text:", response.text)

if __name__ == "__main__":
    test_nemotron()
