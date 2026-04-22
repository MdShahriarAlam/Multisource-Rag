"""OpenAI embedding generation — token-aware batching, retries, timeouts."""
from __future__ import annotations

import logging
from typing import List, Optional

import tiktoken
from openai import APIError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from ..config import settings
from ..errors import EmbeddingError
from .chunker import DocumentChunk

log = logging.getLogger(__name__)

_RETRYABLE = (RateLimitError, APITimeoutError, APIError)


class OpenAIEmbedder:
    """Generate embeddings using OpenAI's embedding API."""

    # Hard OpenAI limits: 2048 inputs per request, 8191 tokens per input,
    # 300k tokens per request for text-embedding-3-*.
    MAX_INPUTS_PER_BATCH = 2048
    ENCODING_FALLBACK = "cl100k_base"

    def __init__(self, model: Optional[str] = None):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_request_timeout,
        )
        self.model = model or settings.openai_embedding_model
        try:
            self._encoder = tiktoken.encoding_for_model(self.model)
        except (KeyError, ValueError):
            self._encoder = tiktoken.get_encoding(self.ENCODING_FALLBACK)

    def _token_count(self, text: str) -> int:
        return len(self._encoder.encode(text, disallowed_special=()))

    def _build_batches(self, texts: List[str]) -> List[List[int]]:
        """Group indices into batches under ``embedder_batch_token_limit`` tokens."""
        limit = settings.embedder_batch_token_limit
        batches: List[List[int]] = []
        current: List[int] = []
        current_tokens = 0
        for i, text in enumerate(texts):
            tokens = self._token_count(text)
            if tokens > limit:
                # Single oversized input — let OpenAI reject or truncate upstream
                if current:
                    batches.append(current)
                    current, current_tokens = [], 0
                batches.append([i])
                continue
            if (
                current
                and (current_tokens + tokens > limit
                     or len(current) >= self.MAX_INPUTS_PER_BATCH)
            ):
                batches.append(current)
                current, current_tokens = [], 0
            current.append(i)
            current_tokens += tokens
        if current:
            batches.append(current)
        return batches

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        for batch_indices in self._build_batches(texts):
            batch_texts = [texts[i] for i in batch_indices]
            vectors = await self._embed_batch(batch_texts)
            for idx, vec in zip(batch_indices, vectors):
                embeddings[idx] = vec
        # All slots filled by construction
        return [v for v in embeddings if v is not None]

    async def embed_chunks(self, chunks: List[DocumentChunk]) -> List[List[float]]:
        return await self.embed_texts([c.text for c in chunks])

    async def embed_query(self, query: str) -> List[float]:
        result = await self.embed_texts([query])
        if not result:
            raise EmbeddingError("Empty embedding result")
        return result[0]

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch with retries + exponential backoff + jitter."""
        attempt_no = {"n": 0}

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.embedder_max_retries),
            wait=wait_random_exponential(multiplier=1, max=20),
            retry=retry_if_exception_type(_RETRYABLE),
            reraise=True,
        ):
            with attempt:
                attempt_no["n"] += 1
                try:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=texts,
                    )
                except APIStatusError as e:
                    # 4xx: don't retry — configuration / input error
                    if 400 <= e.status_code < 500 and e.status_code != 429:
                        raise EmbeddingError(
                            f"OpenAI rejected embedding request: {e.status_code}",
                            details={"status": e.status_code, "message": str(e)},
                        ) from e
                    raise
                return [item.embedding for item in response.data]

        # Unreachable — reraise=True propagates the last error
        raise EmbeddingError("Embedding retries exhausted")
