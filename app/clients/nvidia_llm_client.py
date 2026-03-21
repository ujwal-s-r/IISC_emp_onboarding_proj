"""
Nvidia LLM Client
=================
A unified client using the official Nvidia API endpoint:
https://integrate.api.nvidia.com/v1

Supports four purpose-built model roles:
  - JUDGE_MODEL        = openai/gpt-oss-20b          (skill normalisation judge/coining — no thinking)
  - ORCHESTRATOR_MODEL = stepfun-ai/step-3.5-flash   (JD extraction + team context)
  - RESUME_MODEL       = stepfun-ai/step-3.5-flash   (resume extraction — no thinking)
  - MASTERY_MODEL      = openai/gpt-oss-20b           (mastery scoring — thinking ON)

Thinking mode is model-aware:
  - gpt-oss-20b: extra_body chat_template_kwargs {"thinking": True}
    reasoning_content = CoT trace; content = final JSON answer (separate budgets)
  - GLM4.7 (legacy): chat_template_kwargs {enable_thinking, clear_thinking}

All models stream and return (reasoning, content) tuples.
"""
import sys
import os
from typing import Optional
from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import logger
from app.clients.redis_client import redis_client

# ── Terminal colour helpers (safe for non-TTY / CI) ──────────────────────────
_USE_COLOR     = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
_DIM_GREY      = "\033[90m" if _USE_COLOR else ""
_RESET         = "\033[0m"  if _USE_COLOR else ""

JUDGE_MODEL        = "openai/gpt-oss-20b"
ORCHESTRATOR_MODEL = "stepfun-ai/step-3.5-flash"
RESUME_MODEL       = "stepfun-ai/step-3.5-flash"
MASTERY_MODEL      = "openai/gpt-oss-20b"


class NvidiaLLMClient:
    """
    Generic Nvidia streaming LLM client.
    Returns (reasoning_str, content_str) so callers can log reasoning
    separately from the parsed JSON content.
    """

    def __init__(self, model: str = JUDGE_MODEL, enable_thinking: bool = False):
        self.model          = model
        self.enable_thinking = enable_thinking
        self.client = AsyncOpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        logger.info(f"NvidiaLLMClient initialized with model: {self.model} | thinking={self.enable_thinking}")

    async def stream(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 20000,
        role_id: Optional[str] = None,
        phase: Optional[str] = None,
        step_name: Optional[str] = "llm_streaming"
    ):
        """
        Stream from the Nvidia API.
        If role_id and phase are provided, emits live 'stream_chunk' events to Redis.
        Reasoning chunks are printed in dim grey; content chunks in normal colour.
        Returns (reasoning: str, content: str) tuple.
        """
        try:
            create_kwargs = dict(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                top_p=1 if temperature == 0 else 0.9,
                max_tokens=max_tokens,
                stream=True,
            )
            # Model-aware thinking params:
            #   gpt-oss-20b  → chat_template_kwargs {"thinking": True}
            #     reasoning_content = CoT trace; content = final answer (separate budgets)
            #   GLM4.7 (legacy) → chat_template_kwargs {enable_thinking, clear_thinking}
            if self.enable_thinking:
                if "glm" in self.model.lower():
                    create_kwargs["extra_body"] = {
                        "chat_template_kwargs": {
                            "enable_thinking": True,
                            "clear_thinking":  False,
                        }
                    }
                else:
                    # gpt-oss-20b and compatible models
                    create_kwargs["extra_body"] = {
                        "chat_template_kwargs": {"thinking": True}
                    }

            completion = await self.client.chat.completions.create(**create_kwargs)

            reasoning_chunks = []
            content_chunks   = []

            async for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                r = getattr(delta, "reasoning_content", None)
                c = getattr(delta, "content", None)

                if r:
                    reasoning_chunks.append(r)
                    # Print reasoning in dim grey so it's visually distinct
                    print(f"{_DIM_GREY}{r}{_RESET}", end="", flush=True)
                    if role_id and phase:
                        await redis_client.publish_event(
                            role_id=role_id, phase=phase, event_type="stream_chunk",
                            step=step_name, message="", model=self.model,
                            data={"chunk_type": "reasoning", "text": r}
                        )
                if c:
                    content_chunks.append(c)
                    # Print content in normal colour
                    print(c, end="", flush=True)
                    if role_id and phase:
                        await redis_client.publish_event(
                            role_id=role_id, phase=phase, event_type="stream_chunk",
                            step=step_name, message="", model=self.model,
                            data={"chunk_type": "content", "text": c}
                        )

            print()  # newline after streaming ends
            reasoning = "".join(reasoning_chunks).strip()
            content   = "".join(content_chunks).strip()

            if role_id and phase:
                await redis_client.publish_event(
                    role_id=role_id, phase=phase, event_type="stream_end",
                    step=step_name, message="Stream complete", model=self.model,
                    data={"reasoning_length": len(reasoning), "content_length": len(content)}
                )

            if not content:
                logger.warning(
                    f"[NvidiaLLMClient:{self.model}] Stream returned empty content "
                    f"(reasoning_length={len(reasoning)}). "
                    "This usually means max_tokens was exhausted by the reasoning trace."
                )
                return reasoning, "NONE"

            return reasoning, content

        except Exception as e:
            logger.error(f"[NvidiaLLMClient:{self.model}] API call failed: {e}")
            return "", "NONE"

    async def complete(self, prompt: str, max_tokens: int = 4096) -> str:
        """ Legacy compatibility for the normalizer LLM judge. """
        reasoning, content = await self.stream(prompt, max_tokens=max_tokens)
        combined = (reasoning + "\n" + content).strip() if reasoning else content
        return combined if combined else "NONE"


# ── Singletons ────────────────────────────────────────────────────────────────

# Used by skill_normalizer for O*NET judge + coining (no thinking, logic-focused)
nvidia_llm_client = NvidiaLLMClient(model=JUDGE_MODEL)

# Used by employer/employee orchestrators for JD extraction + team context
orchestrator_llm_client = NvidiaLLMClient(model=ORCHESTRATOR_MODEL)

# Used by employee orchestrator for resume extraction
# stepfun-ai/step-3.5-flash — no thinking, outputs JSON directly in content chunks
resume_llm_client = NvidiaLLMClient(model=RESUME_MODEL, enable_thinking=False)

# Used by employee orchestrator for mastery scoring
# gpt-oss-20b with thinking ON — reasoning_content = CoT, content = final JSON
mastery_llm_client = NvidiaLLMClient(model=MASTERY_MODEL, enable_thinking=True)
