"""Unit-тесты для bot_guest.keyboards.build_question_keyboard."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from aiogram.types import InlineKeyboardMarkup

from bot_guest.keyboards import build_question_keyboard


def _q(
    expected_type: Any,
    *,
    metric_key: str = "m1",
    text: str = "Q?",
    enum_values: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "text": text,
        "metric_key": metric_key,
        "expected_type": expected_type,
        "enum_values": enum_values,
    }


# ----------------------------- boolean ------------------------------------ #


def test_boolean_keyboard_structure() -> None:
    kb = build_question_keyboard(_q("boolean"))
    assert isinstance(kb, InlineKeyboardMarkup)
    rows = kb.inline_keyboard
    assert len(rows) == 1
    assert len(rows[0]) == 3
    texts = [b.text for b in rows[0]]
    cbs = [b.callback_data for b in rows[0]]
    assert texts == ["✅ Да", "❌ Нет", "⏭ Пропустить"]
    assert cbs == ["ans:yes", "ans:no", "ans:skip"]


# ----------------------------- number ------------------------------------- #


def test_number_keyboard_structure() -> None:
    kb = build_question_keyboard(_q("number"))
    assert isinstance(kb, InlineKeyboardMarkup)
    rows = kb.inline_keyboard
    assert len(rows) == 1
    assert len(rows[0]) == 6
    cbs = [b.callback_data for b in rows[0]]
    assert cbs == ["ans:1", "ans:2", "ans:3", "ans:4", "ans:5", "ans:skip"]
    # цифровые кнопки = сами цифры 1..5
    assert [b.text for b in rows[0][:5]] == ["1", "2", "3", "4", "5"]
    # последняя — skip
    assert "⏭" in rows[0][5].text


# ----------------------------- enum --------------------------------------- #


def test_enum_keyboard_odd_values() -> None:
    """3 значения → 3 ряда: [A,B], [C], [skip]."""
    kb = build_question_keyboard(_q("enum", enum_values=["A", "B", "C"]))
    assert isinstance(kb, InlineKeyboardMarkup)
    rows = kb.inline_keyboard
    assert len(rows) == 3
    assert [b.text for b in rows[0]] == ["A", "B"]
    assert [b.callback_data for b in rows[0]] == ["ans:A", "ans:B"]
    assert [b.text for b in rows[1]] == ["C"]
    assert [b.callback_data for b in rows[1]] == ["ans:C"]
    assert len(rows[2]) == 1
    assert rows[2][0].callback_data == "ans:skip"
    assert "⏭" in rows[2][0].text


def test_enum_keyboard_even_values() -> None:
    """4 значения → 3 ряда: [A,B], [C,D], [skip]."""
    kb = build_question_keyboard(_q("enum", enum_values=["A", "B", "C", "D"]))
    assert isinstance(kb, InlineKeyboardMarkup)
    rows = kb.inline_keyboard
    assert len(rows) == 3
    assert [b.text for b in rows[0]] == ["A", "B"]
    assert [b.text for b in rows[1]] == ["C", "D"]
    assert [b.callback_data for b in rows[0]] == ["ans:A", "ans:B"]
    assert [b.callback_data for b in rows[1]] == ["ans:C", "ans:D"]
    assert rows[2][0].callback_data == "ans:skip"


@pytest.mark.parametrize(
    "values,expected_cbs",
    [
        (["x"], [["ans:x"], ["ans:skip"]]),
        (
            ["a", "b", "c", "d", "e"],
            [["ans:a", "ans:b"], ["ans:c", "ans:d"], ["ans:e"], ["ans:skip"]],
        ),
    ],
)
def test_enum_keyboard_pairing_extra(values: list[str], expected_cbs: list[list[str]]) -> None:
    kb = build_question_keyboard(_q("enum", enum_values=values))
    assert isinstance(kb, InlineKeyboardMarkup)
    rows = kb.inline_keyboard
    assert [[b.callback_data for b in row] for row in rows] == expected_cbs


# ----------------------------- text --------------------------------------- #


def test_text_returns_none() -> None:
    assert build_question_keyboard(_q("text")) is None


# ----------------------------- enum empty / fallback ---------------------- #


@pytest.mark.parametrize("empty", [None, []])
def test_enum_empty_returns_none_and_logs_warning(
    empty: list[str] | None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="bot_guest.keyboards")
    result = build_question_keyboard(_q("enum", metric_key="topic_choice", enum_values=empty))
    assert result is None
    assert any(
        rec.levelno == logging.WARNING and "topic_choice" in rec.getMessage()
        for rec in caplog.records
    ), f"expected WARNING with metric_key, got: {caplog.records}"


# ----------------------------- unknown type ------------------------------- #


@pytest.mark.parametrize("bad_type", ["unknown", "rating", "BOOLEAN", None])
def test_unknown_type_raises_valueerror(bad_type: Any) -> None:
    with pytest.raises(ValueError):
        build_question_keyboard(_q(bad_type))
