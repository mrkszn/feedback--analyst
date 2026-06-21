"""Tests for core/agent/nodes/dig — structured guess-card generation.

`chat_completion` is mocked; the node's job is to translate (beat, score, tags,
context) into a stable-id'd list of guess dicts the storage layer can persist.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from core.agent.nodes.dig import Guess, GuessSet, dig_guesses_for_beat


def _two_guesses() -> GuessSet:
    return GuessSet(
        guesses=[
            Guess(text_uk="Холодна", text_en="Cold", emoji="🥶"),
            Guess(text_uk="Мала порція", text_en="Small portion", emoji="🍽️"),
        ]
    )


async def test_dig_returns_guesses_with_stable_ids() -> None:
    with patch(
        "core.agent.nodes.dig.chat_completion",
        new=AsyncMock(return_value=_two_guesses()),
    ) as m:
        result = await dig_guesses_for_beat(
            beat_label="Їжа",
            score=2,
            tags=["cold"],
            restaurant_context="ресторан",
        )
    m.assert_awaited_once()
    assert [g["id"] for g in result] == ["g1", "g2"]
    assert result[0]["text_uk"] == "Холодна"
    assert result[0]["emoji"] == "🥶"
    assert result[1]["text_en"] == "Small portion"


async def test_dig_passes_context_into_user_prompt() -> None:
    with patch(
        "core.agent.nodes.dig.chat_completion",
        new=AsyncMock(return_value=_two_guesses()),
    ) as m:
        await dig_guesses_for_beat(
            beat_label="Очікування",
            score=2,
            tags=["too_long"],
            restaurant_context="доставка еды",
        )
    assert m.await_args is not None
    sent = m.await_args.args[0]
    assert sent[0]["role"] == "system"
    user_text = sent[1]["content"]
    assert "Очікування" in user_text
    assert "2/5" in user_text
    assert "too_long" in user_text
    assert "доставка еды" in user_text


async def test_dig_with_empty_tags_shows_placeholder() -> None:
    with patch(
        "core.agent.nodes.dig.chat_completion",
        new=AsyncMock(return_value=_two_guesses()),
    ) as m:
        await dig_guesses_for_beat(
            beat_label="Їжа",
            score=2,
            tags=[],
            restaurant_context="",
        )
    assert m.await_args is not None
    user_text = m.await_args.args[0][1]["content"]
    assert "(тегов нет)" in user_text
    assert "(не задан)" in user_text


def test_guess_set_requires_min_two() -> None:
    with pytest.raises(ValidationError):
        GuessSet(guesses=[Guess(text_uk="A", text_en="A", emoji="🤷")])


def test_guess_set_rejects_more_than_three() -> None:
    with pytest.raises(ValidationError):
        GuessSet(
            guesses=[
                Guess(text_uk="A", text_en="A", emoji="🤷"),
                Guess(text_uk="B", text_en="B", emoji="🕒"),
                Guess(text_uk="C", text_en="C", emoji="🥶"),
                Guess(text_uk="D", text_en="D", emoji="🍽️"),
            ]
        )
