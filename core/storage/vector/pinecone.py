"""PineconeVectorStore — the production VectorStore.

Thin adapter over `core/integrations/pinecone` (which owns the Pinecone SDK,
namespaces, and retry). Business logic depends on the VectorStore Protocol and
receives this; no Pinecone calls live outside this boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from core.integrations.pinecone import (
    query_similar_sessions,
    upsert_client_card_vector,
)
from core.storage.vector.protocol import VectorMatch


class PineconeVectorStore:
    async def upsert_card(
        self,
        *,
        session_id: str,
        client_id: int,
        vector: list[float],
        sentiment: str | None,
        topics: list[str] | None,
        date: datetime | None = None,
    ) -> str:
        return await upsert_client_card_vector(
            session_id=session_id,
            client_id=client_id,
            vector=vector,
            sentiment=sentiment,
            topics=topics,
            date=date,
        )

    async def query_similar(
        self,
        *,
        vector: list[float],
        top_k: int = 20,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        matches = await query_similar_sessions(
            vector=vector,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )
        return [cast(VectorMatch, m) for m in matches]
