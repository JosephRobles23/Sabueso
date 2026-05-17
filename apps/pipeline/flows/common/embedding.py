"""Embeddings con text-embedding-3-small.

Routing: por defecto via OpenRouter (proxy compatible con OpenAI). Si
EMBEDDING_API_BASE/EMBEDDING_API_KEY apuntan a otro endpoint compatible OpenAI
(p.ej. OpenAI directo) se usa eso. El cliente reintenta hasta 3 veces con
exponential backoff y trunca por límite de tokens.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Sequence

from openai import APIError, AsyncOpenAI, RateLimitError

from .logging import get_logger

log = get_logger("sabueso.pipeline.embedding")

DEFAULT_MODEL = "openai/text-embedding-3-small"
DEFAULT_DIM = 1536
MAX_INPUT_CHARS = 32_000  # safety bound; ~8K tokens en español


def _make_client() -> AsyncOpenAI:
    base_url = os.environ.get("EMBEDDING_API_BASE", "https://openrouter.ai/api/v1")
    api_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("EMBEDDING_API_KEY u OPENROUTER_API_KEY no definidas")
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


_client: AsyncOpenAI | None = None


def _client_singleton() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= MAX_INPUT_CHARS:
        return text
    return text[:MAX_INPUT_CHARS]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def embed_batch(
    texts: Sequence[str],
    *,
    model: str | None = None,
    max_retries: int = 3,
) -> list[list[float]]:
    """Devuelve un embedding por entrada (mismo orden). Texto vacío → vector cero."""
    if not texts:
        return []
    model = model or os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
    client = _client_singleton()

    payload = [_truncate(t) for t in texts]
    # Si todas vacías evitamos llamada
    nonempty_idx = [i for i, t in enumerate(payload) if t]
    if not nonempty_idx:
        return [[0.0] * DEFAULT_DIM for _ in texts]

    nonempty_texts = [payload[i] for i in nonempty_idx]

    attempt = 0
    while True:
        try:
            resp = await client.embeddings.create(model=model, input=nonempty_texts)
            break
        except (RateLimitError, APIError) as e:
            attempt += 1
            if attempt > max_retries:
                log.error("embedding.failed", error=str(e), attempt=attempt)
                raise
            wait = 2 ** attempt
            log.warning("embedding.retry", error=str(e), wait_s=wait, attempt=attempt)
            await asyncio.sleep(wait)

    embeddings_by_idx = {nonempty_idx[i]: d.embedding for i, d in enumerate(resp.data)}
    return [embeddings_by_idx.get(i, [0.0] * DEFAULT_DIM) for i in range(len(texts))]


async def embed_one(text: str, *, model: str | None = None) -> list[float]:
    out = await embed_batch([text], model=model)
    return out[0]
