"""Pinecone integration — per-session client-card upsert.

Единственная точка записи в Pinecone в v1: кладём embedding карточки клиента
в namespace `client-cards` (по умолчанию из settings) с vector_id = session_id
и метаданными {client_id, session_id, date, sentiment?, topics?}.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from pinecone import Pinecone
from pinecone.exceptions import PineconeApiException
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings

VECTOR_DIM = 1536


def _retrying() -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(PineconeApiException),
        reraise=True,
    )


async def upsert_client_card_vector(
    *,
    session_id: str,
    client_id: int,
    vector: list[float],
    sentiment: str | None,
    topics: list[str] | None,
    date: datetime | None = None,
    index_name: str | None = None,
    namespace: str | None = None,
) -> str:
    if len(vector) != VECTOR_DIM:
        raise ValueError(f"vector must have length {VECTOR_DIM}, got {len(vector)}")

    date_iso = (date or datetime.now(UTC)).isoformat()

    metadata: dict[str, Any] = {
        "client_id": client_id,
        "session_id": session_id,
        "date": date_iso,
    }
    if sentiment:
        metadata["sentiment"] = sentiment
    if topics:
        metadata["topics"] = topics

    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(index_name or settings.pinecone_index)

    target_namespace = namespace or settings.pinecone_namespace
    vectors = [{"id": session_id, "values": vector, "metadata": metadata}]

    async for attempt in _retrying():
        with attempt:
            await asyncio.to_thread(
                index.upsert,
                vectors=vectors,
                namespace=target_namespace,
            )

    return session_id
