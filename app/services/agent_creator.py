from langchain_openai import ChatOpenAI
from app.config import settings
from app.utils.logger import logger

class AgentCreator:
    def __init__(self):
        # Initialize the LangChain ChatOpenAI instance
        self.llm = ChatOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            model=settings.LLM_MODEL,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
            default_headers={
                "HTTP-Referer": "https://adaptiq.ai",
                "X-OpenRouter-Title": "AdaptIQ",
            }
        )

    def get_llm(self):
        return self.llm

agent_creator = AgentCreator()
