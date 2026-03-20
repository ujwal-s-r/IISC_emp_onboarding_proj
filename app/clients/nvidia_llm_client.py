"""
Nvidia LLM Client
=================
A dedicated LLM client using the official Nvidia API endpoint:
https://integrate.api.nvidia.com/v1

Uses 'openai/gpt-oss-20b' with streaming to accurately capture both
reasoning content and standard message content as requested.
"""
from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import logger


class NvidiaLLMClient:
    MODEL = "openai/gpt-oss-20b"

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        logger.info(f"NvidiaLLMClient initialized with model: {self.MODEL}")

    async def complete(self, prompt: str, max_tokens: int = 4096) -> str:
        """Fire a streaming completion and accumulate the full text (reasoning + content)."""
        try:
            # The Nvidia API for this model requires streaming to reliably extract reasoning chunks
            completion = await self.client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0, # 0.0 for factual matching
                top_p=1,
                max_tokens=max_tokens,
                stream=True,
            )
            
            full_text = []
            
            async for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                
                delta = chunk.choices[0].delta
                
                # Extract reasoning if available
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    full_text.append(reasoning)
                    
                # Extract standard content if available
                if getattr(delta, "content", None) is not None:
                    full_text.append(delta.content)
            
            final_string = "".join(full_text).strip()
            
            if not final_string:
                logger.warning("[NvidiaLLMClient] Stream completed but accumulated no text.")
                return "NONE"
            
            return final_string
            
        except Exception as e:
            logger.error(f"[NvidiaLLMClient] API call failed: {e}")
            return "NONE"


# Singleton
nvidia_llm_client = NvidiaLLMClient()
