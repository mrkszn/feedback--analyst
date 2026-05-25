from unittest.mock import MagicMock

from services.clients import create_or_get_client


def _mk_db(existing: list[dict], inserted: list[dict] | None = None) -> MagicMock:
    db = MagicMock()
    chain = db.table.return_value.select.return_value.eq.return_value.limit.return_value
    chain.execute.return_value.data = existing
    if inserted is not None:
        db.table.return_value.insert.return_value.execute.return_value.data = inserted
    return db


async def test_returns_existing_when_found() -> None:
    db = _mk_db(existing=[{"telegram_id": 42, "name": "A"}])
    result = await create_or_get_client(42, db=db)
    assert result["telegram_id"] == 42
    db.table.return_value.insert.assert_not_called()


async def test_creates_when_missing() -> None:
    db = _mk_db(existing=[], inserted=[{"telegram_id": 42, "name": "Bob"}])
    result = await create_or_get_client(42, name="Bob", db=db)
    assert result["name"] == "Bob"
    db.table.return_value.insert.assert_called_once_with({"telegram_id": 42, "name": "Bob"})


async def test_race_unique_violation_recovers() -> None:
    db = MagicMock()
    select_chain = db.table.return_value.select.return_value.eq.return_value.limit.return_value
    # First select: empty. Second select (recovery): finds the row.
    select_chain.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(data=[{"telegram_id": 42, "name": "X"}]),
    ]
    db.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "duplicate key (23505)"
    )

    result = await create_or_get_client(42, db=db)
    assert result["telegram_id"] == 42
