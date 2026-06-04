from unittest.mock import MagicMock

import pytest

from core.services.admin_auth import claim_admin, is_admin


def _mk_db_select(data: list[dict], count: int | None = None) -> MagicMock:
    db = MagicMock()
    chain = db.table.return_value.select.return_value.eq.return_value.limit.return_value
    chain.execute.return_value.data = data
    chain.execute.return_value.count = count
    return db


def _mk_db_count(count: int) -> MagicMock:
    db = MagicMock()
    chain = db.table.return_value.select.return_value.limit.return_value
    chain.execute.return_value.count = count
    chain.execute.return_value.data = []
    db.table.return_value.insert.return_value.execute.return_value.data = [{"telegram_id": 1}]
    return db


async def test_is_admin_true_when_row_exists() -> None:
    db = _mk_db_select([{"telegram_id": 42}])
    assert await is_admin(42, db=db) is True


async def test_is_admin_false_when_no_row() -> None:
    db = _mk_db_select([])
    assert await is_admin(42, db=db) is False


async def test_claim_admin_rejects_empty_bootstrap_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "admin_bootstrap_token", "")
    db = _mk_db_count(0)
    assert await claim_admin(42, "any-token", db=db) is False


async def test_claim_admin_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "admin_bootstrap_token", "secret")
    db = _mk_db_count(0)
    assert await claim_admin(42, "wrong", db=db) is False


async def test_claim_admin_rejects_when_table_not_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "admin_bootstrap_token", "secret")
    db = _mk_db_count(1)
    assert await claim_admin(42, "secret", db=db) is False


async def test_claim_admin_success_on_empty_table(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "admin_bootstrap_token", "secret")
    db = _mk_db_count(0)
    assert await claim_admin(42, "secret", name="Alice", db=db) is True
    db.table.return_value.insert.assert_called_once_with({"telegram_id": 42, "name": "Alice"})


async def test_claim_admin_recovers_from_race_unique_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from config import settings

    monkeypatch.setattr(settings, "admin_bootstrap_token", "secret")
    db = _mk_db_count(0)
    db.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
        "duplicate key value violates unique constraint (23505)"
    )
    assert await claim_admin(42, "secret", db=db) is False
