"""
Nvidia LLM Client
=================
A unified client using the official Nvidia API endpoint:
https://integrate.api.nvidia.com/v1

Supports two purpose-built models:
  - JUDGE_MODEL  = openai/gpt-oss-20b       (skill normalization judge/coining)
  - ORCHESTRATOR_MODEL = stepfun-ai/step-3.5-flash (JD extraction + team context)

Both models are used in streaming mode to capture:
  - reasoning_content (the model's internal chain-of-thought, logged for transparency)
  - content          (the actual JSON output we parse)

These are accumulated separately and returned as (reasoning, content) tuples.
"""
from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import logger


JUDGE_MODEL        = "openai/gpt-oss-20b"
ORCHESTRATOR_MODEL = "stepfun-ai/step-3.5-flash"


class NvidiaLLMClient:
    """
    Generic Nvidia streaming LLM client.
    Returns (reasoning_str, content_str) so callers can log reasoning
    separately from the parsed JSON content.
    """

    def __init__(self, model: str = JUDGE_MODEL):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        logger.info(f"NvidiaLLMClient initialized with model: {self.model}")

    async def stream(self, prompt: str, temperature: float = 0.0, max_tokens: int = 4096):
        """
        Stream from the Nvidia API.
        Returns (reasoning: str, content: str) tuple.
        reasoning is the model's internal chain-of-thought (may be empty).
        content is the model's final reply.
        """
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                top_p=1 if temperature == 0 else 0.9,
                max_tokens=max_tokens,
                stream=True,
            )

            reasoning_chunks = []
            content_chunks   = []

            async for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                r = getattr(delta, "reasoning_content", None)
                c = getattr(delta, "content", None)
                if r:
                    reasoning_chunks.append(r)
                if c:
                    content_chunks.append(c)

            reasoning = "".join(reasoning_chunks).strip()
            content   = "".join(content_chunks).strip()

            if not content:
                logger.warning(f"[NvidiaLLMClient:{self.model}] Stream returned empty content.")
                return reasoning, "NONE"

            return reasoning, content

        except Exception as e:
            logger.error(f"[NvidiaLLMClient:{self.model}] API call failed: {e}")
            return "", "NONE"

    async def complete(self, prompt: str, max_tokens: int = 4096) -> str:
        """
        Legacy compatibility: accumulate BOTH reasoning + content into one string.
        Used by skill_normalizer where we feed the full text to the regex parser.
        """
        reasoning, content = await self.stream(prompt, max_tokens=max_tokens)
        combined = (reasoning + "\n" + content).strip() if reasoning else content
        return combined if combined else "NONE"


# ── Singletons ────────────────────────────────────────────────────────────────

# Used by skill_normalizer for O*NET judge + coining (logic-focused, temperature=0)
nvidia_llm_client = NvidiaLLMClient(model=JUDGE_MODEL)

# Used by orchestrator for JD extraction + team context (needs reasoning depth)
orchestrator_llm_client = NvidiaLLMClient(model=ORCHESTRATOR_MODEL)
