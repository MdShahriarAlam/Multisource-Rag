"""OpenAI embedding generation for document chunks."""
import asyncio
import time
from typing import List

from openai import AsyncOpenAI

from ..config import settings
from .chunker import DocumentChunk


class OpenAIEmbedder:
    """Generate embeddings using OpenAI's embedding API."""

    MAX_BATCH_SIZE = 2048

    def __init__(self, model: str = None):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_embedding_model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts, handling batching and retries."""
        all_embeddings = []

        for i in range(0, len(texts), self.MAX_BATCH_SIZE):
            batch = texts[i : i + self.MAX_BATCH_SIZE]
            embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def embed_chunks(
        self, chunks: List[DocumentChunk]
    ) -> List[List[float]]:
        """Embed a list of DocumentChunks."""
        texts = [c.text for c in chunks]
        return await self.embed_texts(texts)

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        result = await self.embed_texts([query])
        return result[0]

    async def _embed_batch_with_retry(
        self, texts: List[str], max_retries: int = 3
    ) -> List[List[float]]:
        """Embed a batch with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                response = await self.client.embeddings.create(
                    model=self.model, input=texts
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                print(f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
