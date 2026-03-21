"""
Nvidia LLM Client
=================
A unified client using the official Nvidia API endpoint:
https://integrate.api.nvidia.com/v1

Supports four purpose-built model roles:
  - JUDGE_MODEL        = openai/gpt-oss-20b          (skill normalisation judge/coining — no thinking)
  - ORCHESTRATOR_MODEL = stepfun-ai/step-3.5-flash        (JD extraction + team context)
  - RESUME_MODEL       = qwen/qwen3.5-122b-a10b           (resume extraction — thinking ON)
  - MASTERY_MODEL      = openai/gpt-oss-20b               (mastery scoring — thinking ON)

Thinking mode is model-aware:
  - gpt-oss-20b: extra_body chat_template_kwargs {"thinking": True}
    reasoning_content = CoT trace; content = final JSON answer (separate budgets)
  - qwen3.5-122b: chat_template_kwargs {"enable_thinking": True} (same split as gpt-oss-20b)
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
RESUME_MODEL       = "qwen/qwen3.5-122b-a10b"
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
                elif "qwen" in self.model.lower():
                    # qwen3.5-122b: uses enable_thinking (no clear_thinking key)
                    create_kwargs["extra_body"] = {
                        "chat_template_kwargs": {"enable_thinking": True}
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
        """ Legacy compatibility for the normalizer LLM judge.
            Returns only the final content, ignoring CoT reasoning.
        """
        reasoning, content = await self.stream(prompt, max_tokens=max_tokens)
        return content.strip() if content else "NONE"


# ── Singletons ────────────────────────────────────────────────────────────────

# Used by skill_normalizer for O*NET judge + coining
# enable_thinking=True so CoT goes to reasoning_content; content = clean "1"/"2"/"3"/"NONE"/coined name
judge_llm_client = NvidiaLLMClient(model=JUDGE_MODEL, enable_thinking=True)

# Legacy alias kept so any existing imports of nvidia_llm_client still work
nvidia_llm_client = judge_llm_client

# Used by employer/employee orchestrators for JD extraction + team context
orchestrator_llm_client = NvidiaLLMClient(model=ORCHESTRATOR_MODEL)

# Used by employee orchestrator for resume extraction
# qwen/qwen3.5-122b-a10b — thinking ON: reasoning_content = CoT, content = JSON answer
resume_llm_client = NvidiaLLMClient(model=RESUME_MODEL, enable_thinking=True)

# Used by employee orchestrator for mastery scoring
# gpt-oss-20b with thinking ON — reasoning_content = CoT, content = final JSON
mastery_llm_client = NvidiaLLMClient(model=MASTERY_MODEL, enable_thinking=True)

# Used by path generation for dependency resolution (thinking ON for DAG reasoning)
dependency_llm_client = NvidiaLLMClient(model=MASTERY_MODEL, enable_thinking=True)

# Used by Phase 11 — Journey Narration (thinking ON — highest quality)
narrator_llm_client = NvidiaLLMClient(model=RESUME_MODEL, enable_thinking=True)


# ── Nvidia Embedding Client ───────────────────────────────────────────────────

from openai import OpenAI as _OpenAI_Sync
from typing import List as _List

EMBEDDING_MODEL = "nvidia/llama-3.2-nemoretriever-300m-embed-v1"
EMBEDDING_DIM   = 2048


class NvidiaEmbeddingClient:
    """
    Synchronous embedding client using the Nvidia NemoRetriever API.
    Produces 1024-dimensional dense vectors.

    Two input types:
      - "passage" : for indexing documents into Qdrant (ingest time)
      - "query"   : for searching Qdrant at runtime (skill gap queries)

    Used exclusively for the `courses` Qdrant collection.
    The O*NET collection retains the local SentenceTransformer (384-dim).
    """

    def __init__(self):
        self.client = _OpenAI_Sync(
            api_key=settings.NVIDIA_API_KEY,
            base_url="https://integrate.api.nvidia.com/v1",
        )
        logger.info(f"NvidiaEmbeddingClient initialized | model={EMBEDDING_MODEL} | dim={EMBEDDING_DIM}")

    def embed_passages(self, texts: _List[str]) -> _List[_List[float]]:
        """
        Embed a batch of document passages for ingestion into Qdrant.
        input_type = "passage" tells NemoRetriever to optimise for indexing.
        """
        response = self.client.embeddings.create(
            input=texts,
            model=EMBEDDING_MODEL,
            encoding_format="float",
            extra_body={"input_type": "passage", "truncate": "END"},
        )
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> _List[float]:
        """
        Embed a single query string for ANN search in Qdrant.
        input_type = "query" tells NemoRetriever to optimise for retrieval.
        """
        response = self.client.embeddings.create(
            input=[text],
            model=EMBEDDING_MODEL,
            encoding_format="float",
            extra_body={"input_type": "query", "truncate": "END"},
        )
        return response.data[0].embedding


# Singleton — used by ingest_courses.py and path_generator.py
nvidia_embedding_client = NvidiaEmbeddingClient()
