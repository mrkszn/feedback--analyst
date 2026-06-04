"""VectorStore Protocol — the boundary for semantic vector storage.

Business logic (analytics semantic search, guest-bot card upsert) depends on
this Protocol instead of importing Pinecone directly. `PineconeVectorStore` is
the production implementation; it wraps the low-level `core/integrations/pinecone`
functions (which own the Pinecone SDK + retry).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypedDict


class VectorMatch(TypedDict):
    session_id: str
    client_id: int | None
    score: float
    metadata: dict[str, Any]


class VectorStore(Protocol):
    async def upsert_card(
        self,
        *,
        session_id: str,
        client_id: int,
        vector: list[float],
        sentiment: str | None,
        topics: list[str] | None,
        date: datetime | None = None,
    ) -> str: ...

    async def query_similar(
        self,
        *,
        vector: list[float],
        top_k: int = 20,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]: ...
