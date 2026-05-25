from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.questions import (
    create_question,
    delete_question,
    list_questions,
    update_question,
)


def _mk_insert_db(row: dict) -> MagicMock:
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value.data = [row]
    return db


async def test_create_text_question() -> None:
    db = _mk_insert_db({"id": "1", "text": "q", "metric_key": "k", "expected_type": "text"})
    result = await create_question(text="q", metric_key="k", expected_type="text", db=db)
    assert result["metric_key"] == "k"


async def test_create_enum_requires_values() -> None:
    with pytest.raises(ValueError):
        await create_question(text="q", metric_key="k", expected_type="enum", db=MagicMock())


async def test_create_enum_with_values() -> None:
    db = _mk_insert_db({"id": "1", "enum_values": ["a", "b"]})
    result = await create_question(
        text="q", metric_key="k", expected_type="enum", enum_values=["a", "b"], db=db
    )
    assert result["enum_values"] == ["a", "b"]


async def test_create_duplicate_metric_key_raises() -> None:
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "duplicate (23505)"
    )
    with pytest.raises(ValueError, match="already exists"):
        await create_question(text="q", metric_key="k", expected_type="text", db=db)


async def test_create_empty_text_raises() -> None:
    with pytest.raises(ValueError):
        await create_question(text="  ", metric_key="k", expected_type="text", db=MagicMock())


async def test_update_partial() -> None:
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "1", "text": "new"}
    ]
    result = await update_question(uuid4(), text="new", db=db)
    assert result["text"] == "new"


async def test_update_empty_patch_raises() -> None:
    with pytest.raises(ValueError, match="nothing to update"):
        await update_question(uuid4(), db=MagicMock())


async def test_update_not_found_raises() -> None:
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    with pytest.raises(LookupError):
        await update_question(uuid4(), text="x", db=db)


async def test_delete_marks_inactive() -> None:
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "1", "is_active": False}
    ]
    await delete_question(uuid4(), db=db)
    args, _ = db.table.return_value.update.call_args
    assert args[0] == {"is_active": False}


async def test_list_all() -> None:
    db = MagicMock()
    chain = db.table.return_value.select.return_value.order.return_value
    chain.execute.return_value.data = [{"id": "1"}, {"id": "2"}]
    result = await list_questions(db=db)
    assert len(result) == 2


async def test_list_active_only() -> None:
    db = MagicMock()
    chain = db.table.return_value.select.return_value.eq.return_value.order.return_value
    chain.execute.return_value.data = [{"id": "1", "is_active": True}]
    result = await list_questions(active_only=True, db=db)
    assert len(result) == 1
    db.table.return_value.select.return_value.eq.assert_called_once_with("is_active", True)
