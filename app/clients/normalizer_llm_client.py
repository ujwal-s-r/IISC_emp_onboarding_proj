"""
Normalizer LLM Client
=====================
A dedicated lightweight LLM client using 'openai/gpt-oss-20b:free' via OpenRouter,
used exclusively by the LLM-based Skill Normalizer for fast, cheap disambiguation.
"""
from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import logger


class NormalizerLLMClient:
    MODEL = settings.LLM_MODEL

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://adaptiq.ai",
                "X-OpenRouter-Title": "AdaptIQ-Normalizer",
            },
        )
        logger.info(f"NormalizerLLMClient initialized with model: {self.MODEL}")

    async def complete(self, prompt: str, max_tokens: int = 500) -> str:
        """Fire a simple single-turn completion, return the text."""
        try:
            response = await self.client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.0,
            )
            
            if not response.choices:
                logger.warning("[NormalizerLLMClient] OpenRouter returned no choices.")
                return "NONE"
                
            msg = response.choices[0].message
            content = msg.content
            
            # Check for reasoning if content is null
            if content is None:
                # Some models put results in reasoning or just fail to fill content
                reasoning = getattr(msg, 'reasoning', None)
                logger.warning(f"[NormalizerLLMClient] Content is null. Reasoning available: {bool(reasoning)}")
                if reasoning:
                    return reasoning.strip()
                return "NONE"
                
            return content.strip()
            
        except Exception as e:
            logger.error(f"[NormalizerLLMClient] API call failed: {e}")
            return "NONE"


# Singleton
normalizer_llm_client = NormalizerLLMClient()
