"""Pinecone integration — per-session client-card upsert + semantic query.

Запись (`upsert_client_card_vector`): кладём embedding карточки клиента в
namespace `client-cards` (по умолчанию из settings) с vector_id = session_id и
метаданными {client_id, session_id, date, sentiment?, topics?}.

Чтение (`query_similar_sessions`): natural-language семантический поиск по тому
же namespace для Phase 3 analytics (`/find`, `/ask`). Возвращает плоские
словари {session_id, client_id, score, metadata} — удобно для последующего
JOIN с Supabase в `services.analytics`.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any, TypedDict

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


class PineconeMatch(TypedDict):
    session_id: str
    client_id: int | None
    score: float
    metadata: dict[str, Any]


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


async def query_similar_sessions(
    *,
    vector: list[float],
    top_k: int = 20,
    index_name: str | None = None,
    namespace: str | None = None,
    metadata_filter: dict[str, Any] | None = None,
) -> list[PineconeMatch]:
    """Semantic search по client-cards. Возвращает top_k наиболее похожих
    session-vector'ов в виде плоских dict'ов.

    `metadata_filter` пробрасывается в Pinecone `filter` (например
    `{"sentiment": {"$eq": "negative"}}`), позволяя сузить поиск без отдельного
    SQL-уровня.
    """
    if len(vector) != VECTOR_DIM:
        raise ValueError(f"vector must have length {VECTOR_DIM}, got {len(vector)}")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(index_name or settings.pinecone_index)
    target_namespace = namespace or settings.pinecone_namespace

    def _do_query() -> Any:
        return index.query(
            vector=vector,
            top_k=top_k,
            namespace=target_namespace,
            include_metadata=True,
            filter=metadata_filter,
        )

    resp: Any = None
    async for attempt in _retrying():
        with attempt:
            resp = await asyncio.to_thread(_do_query)

    raw_matches: list[Any] = []
    if isinstance(resp, dict):
        raw_matches = list(resp.get("matches") or [])
    else:
        raw_matches = list(getattr(resp, "matches", None) or [])

    out: list[PineconeMatch] = []
    for m in raw_matches:
        md = (m.get("metadata") if isinstance(m, dict) else getattr(m, "metadata", None)) or {}
        score = m.get("score") if isinstance(m, dict) else getattr(m, "score", 0.0)
        vid = m.get("id") if isinstance(m, dict) else getattr(m, "id", "")
        session_id = str(md.get("session_id") or vid or "")
        client_id_raw = md.get("client_id")
        try:
            client_id = int(client_id_raw) if client_id_raw is not None else None
        except (TypeError, ValueError):
            client_id = None
        out.append(
            PineconeMatch(
                session_id=session_id,
                client_id=client_id,
                score=float(score or 0.0),
                metadata=dict(md),
            )
        )
    return out
