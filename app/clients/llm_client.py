from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import logger

class LLMClient:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.LLM_MODEL
        self.base_url = "https://openrouter.ai/api/v1"
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers={
                "HTTP-Referer": "https://adaptiq.ai", # Optional
                "X-OpenRouter-Title": "AdaptIQ", # Optional
            }
        )

    async def test_connection(self):
        logger.info(f"Testing connection to OpenRouter (via OpenAI SDK) with model: {self.model}")
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            if response.choices:
                logger.info("OpenRouter connection successful.")
                return True
            return False
        except Exception as e:
            logger.error(f"OpenRouter connection error: {str(e)}")
            return False

llm_client = LLMClient()

