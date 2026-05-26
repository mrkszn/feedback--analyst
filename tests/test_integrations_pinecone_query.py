"""Unit-тесты для integrations.pinecone.query_similar_sessions.

Pinecone замокан через monkeypatch на `integrations.pinecone.Pinecone` — тот
же паттерн, что и для upsert-теста.
"""

from unittest.mock import MagicMock

import pytest

from integrations.pinecone import query_similar_sessions


def _mk_pinecone_mock(matches: list[dict]) -> tuple[MagicMock, MagicMock]:
    query_mock = MagicMock(return_value={"matches": matches})
    index_mock = MagicMock()
    index_mock.query = query_mock
    pc_instance = MagicMock()
    pc_instance.Index = MagicMock(return_value=index_mock)
    pinecone_class = MagicMock(return_value=pc_instance)
    return pinecone_class, query_mock


async def test_query_returns_flattened_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = [
        {
            "id": "sess-1",
            "score": 0.91,
            "metadata": {
                "session_id": "sess-1",
                "client_id": 42,
                "sentiment": "positive",
                "topics": ["food"],
            },
        },
        {
            "id": "sess-2",
            "score": 0.83,
            "metadata": {"session_id": "sess-2", "client_id": "7"},
        },
    ]
    pc_class, _q = _mk_pinecone_mock(matches)
    monkeypatch.setattr("integrations.pinecone.Pinecone", pc_class)

    out = await query_similar_sessions(vector=[0.0] * 1536, top_k=5)

    assert len(out) == 2
    assert out[0]["session_id"] == "sess-1"
    assert out[0]["client_id"] == 42
    assert out[0]["score"] == pytest.approx(0.91)
    assert out[0]["metadata"]["topics"] == ["food"]
    # client_id coerced from string
    assert out[1]["client_id"] == 7


async def test_query_invalid_vector_length_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, query_mock = _mk_pinecone_mock([])
    monkeypatch.setattr("integrations.pinecone.Pinecone", pc_class)

    with pytest.raises(ValueError):
        await query_similar_sessions(vector=[0.0] * 100)

    query_mock.assert_not_called()


async def test_query_top_k_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, _q = _mk_pinecone_mock([])
    monkeypatch.setattr("integrations.pinecone.Pinecone", pc_class)

    with pytest.raises(ValueError):
        await query_similar_sessions(vector=[0.0] * 1536, top_k=0)


async def test_query_passes_filter_and_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, query_mock = _mk_pinecone_mock([])
    monkeypatch.setattr("integrations.pinecone.Pinecone", pc_class)

    await query_similar_sessions(
        vector=[0.0] * 1536,
        top_k=3,
        namespace="custom-ns",
        metadata_filter={"sentiment": {"$eq": "negative"}},
    )

    kwargs = query_mock.call_args.kwargs
    assert kwargs["namespace"] == "custom-ns"
    assert kwargs["top_k"] == 3
    assert kwargs["filter"] == {"sentiment": {"$eq": "negative"}}
    assert kwargs["include_metadata"] is True


async def test_query_handles_object_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Older Pinecone client returns a QueryResponse object, not a dict."""

    class _Match:
        def __init__(self, **kw: object) -> None:
            self.__dict__.update(kw)

    class _Resp:
        def __init__(self, matches: list[_Match]) -> None:
            self.matches = matches

    resp = _Resp(
        [_Match(id="sess-9", score=0.77, metadata={"session_id": "sess-9", "client_id": 1})]
    )

    query_mock = MagicMock(return_value=resp)
    index_mock = MagicMock()
    index_mock.query = query_mock
    pc_instance = MagicMock()
    pc_instance.Index = MagicMock(return_value=index_mock)
    pinecone_class = MagicMock(return_value=pc_instance)
    monkeypatch.setattr("integrations.pinecone.Pinecone", pinecone_class)

    out = await query_similar_sessions(vector=[0.0] * 1536, top_k=1)

    assert len(out) == 1
    assert out[0]["session_id"] == "sess-9"
    assert out[0]["client_id"] == 1
    assert out[0]["score"] == pytest.approx(0.77)
