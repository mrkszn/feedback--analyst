"""Unit-тесты для integrations.pinecone.upsert_client_card_vector.

Сетевые вызовы Pinecone замоканы через patch на `integrations.pinecone.Pinecone`:
конструктор возвращает MagicMock, у которого `.Index(...)` — тоже MagicMock,
а `.upsert(...)` — обычный sync-мок (вызывается через asyncio.to_thread).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from core.integrations.pinecone import upsert_client_card_vector


def _make_pinecone_mock() -> tuple[MagicMock, MagicMock]:
    """Возвращает (Pinecone_class_mock, upsert_mock)."""
    upsert_mock = MagicMock(return_value=None)
    index_mock = MagicMock()
    index_mock.upsert = upsert_mock
    pc_instance = MagicMock()
    pc_instance.Index = MagicMock(return_value=index_mock)
    pinecone_class = MagicMock(return_value=pc_instance)
    return pinecone_class, upsert_mock


async def test_upsert_returns_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, _upsert = _make_pinecone_mock()
    monkeypatch.setattr("core.integrations.pinecone.Pinecone", pc_class)

    result = await upsert_client_card_vector(
        session_id="sess-1",
        client_id=42,
        vector=[0.1] * 1536,
        sentiment="positive",
        topics=["service", "food"],
    )

    assert result == "sess-1"


async def test_invalid_vector_length_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, upsert = _make_pinecone_mock()
    monkeypatch.setattr("core.integrations.pinecone.Pinecone", pc_class)

    with pytest.raises(ValueError):
        await upsert_client_card_vector(
            session_id="sess-1",
            client_id=42,
            vector=[0.0] * 100,
            sentiment=None,
            topics=None,
        )

    upsert.assert_not_called()


async def test_metadata_includes_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, upsert = _make_pinecone_mock()
    monkeypatch.setattr("core.integrations.pinecone.Pinecone", pc_class)
    fixed_date = datetime(2026, 5, 25, 12, 0, 0, tzinfo=UTC)

    await upsert_client_card_vector(
        session_id="sess-meta",
        client_id=7,
        vector=[0.0] * 1536,
        sentiment="neutral",
        topics=["a"],
        date=fixed_date,
    )

    kwargs = upsert.call_args.kwargs
    vectors = kwargs["vectors"]
    assert len(vectors) == 1
    md = vectors[0]["metadata"]
    assert md["client_id"] == 7
    assert md["session_id"] == "sess-meta"
    assert md["date"] == fixed_date.isoformat()
    assert md["sentiment"] == "neutral"
    assert md["topics"] == ["a"]
    assert vectors[0]["id"] == "sess-meta"
    assert vectors[0]["values"] == [0.0] * 1536


async def test_empty_topics_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, upsert = _make_pinecone_mock()
    monkeypatch.setattr("core.integrations.pinecone.Pinecone", pc_class)

    await upsert_client_card_vector(
        session_id="sess-empty",
        client_id=1,
        vector=[0.0] * 1536,
        sentiment=None,
        topics=[],
    )

    md = upsert.call_args.kwargs["vectors"][0]["metadata"]
    assert "topics" not in md
    assert "sentiment" not in md


async def test_default_namespace_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, upsert = _make_pinecone_mock()
    monkeypatch.setattr("core.integrations.pinecone.Pinecone", pc_class)

    from config import settings

    monkeypatch.setattr(settings, "pinecone_namespace", "custom-ns")
    monkeypatch.setattr(settings, "pinecone_index", "custom-idx")

    await upsert_client_card_vector(
        session_id="sess-ns",
        client_id=2,
        vector=[0.0] * 1536,
        sentiment=None,
        topics=None,
    )

    assert upsert.call_args.kwargs["namespace"] == "custom-ns"
    pc_instance = pc_class.return_value
    pc_instance.Index.assert_called_once_with("custom-idx")


async def test_overrides_take_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, upsert = _make_pinecone_mock()
    monkeypatch.setattr("core.integrations.pinecone.Pinecone", pc_class)

    await upsert_client_card_vector(
        session_id="sess-ov",
        client_id=3,
        vector=[0.0] * 1536,
        sentiment=None,
        topics=None,
        index_name="override-idx",
        namespace="override-ns",
    )

    assert upsert.call_args.kwargs["namespace"] == "override-ns"
    pc_class.return_value.Index.assert_called_once_with("override-idx")


async def test_default_date_uses_now_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    pc_class, upsert = _make_pinecone_mock()
    monkeypatch.setattr("core.integrations.pinecone.Pinecone", pc_class)

    before = datetime.now(UTC)
    await upsert_client_card_vector(
        session_id="sess-date",
        client_id=4,
        vector=[0.0] * 1536,
        sentiment=None,
        topics=None,
    )
    after = datetime.now(UTC)

    md = upsert.call_args.kwargs["vectors"][0]["metadata"]
    parsed = datetime.fromisoformat(md["date"])
    assert before <= parsed <= after
    assert parsed.tzinfo is not None
