"""Unit-тесты для agent.nodes.dialogue.continue_dialogue и схемы DialogueTurn.

Покрытие:
- t1: continue_dialogue возвращает валидный DialogueTurn с transition="continue";
- t2: при turn_count >= max_turns transition форсится в "offer_survey",
  даже если LLM вернул "continue";
- t3: pydantic-схема отвергает невалидный literal transition;
- t4: пустая history (первый ход) не падает и возвращает валидный объект.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.agent.nodes.dialogue import DialogueTurn, continue_dialogue


async def test_continue_dialogue_returns_valid_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = DialogueTurn(
        bot_reply="Расскажи подробнее про закуски! 🥗",
        transition="continue",
        insights={"topic": "food"},
    )

    async def fake_chat(messages, **kwargs):
        assert kwargs.get("response_model") is DialogueTurn
        return expected

    monkeypatch.setattr("core.agent.nodes.dialogue.chat_completion", fake_chat)

    result = await continue_dialogue(
        feedback_summary='{"summary":"x","sentiment":"positive","topics":["food"],"emotion":"joy"}',
        history=[{"role": "user", "content": "очень вкусно"}],
        restaurant_context="Кафе у моря",
        turn_count=1,
        max_turns=5,
    )

    assert isinstance(result, DialogueTurn)
    assert result.bot_reply == "Расскажи подробнее про закуски! 🥗"
    assert result.transition == "continue"
    assert isinstance(result.insights, dict)
    assert result.insights == {"topic": "food"}


async def test_continue_dialogue_forces_offer_survey_at_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hard cap: turn_count >= max_turns → transition форсится в offer_survey."""
    llm_wants_to_continue = DialogueTurn(
        bot_reply="Хочется поболтать ещё! 😊",
        transition="continue",
        insights={},
    )

    async def fake_chat(messages, **kwargs):
        return llm_wants_to_continue

    monkeypatch.setattr("core.agent.nodes.dialogue.chat_completion", fake_chat)

    result = await continue_dialogue(
        feedback_summary="{}",
        history=[{"role": "user", "content": "ok"}],
        restaurant_context="",
        turn_count=5,
        max_turns=5,
    )

    assert result.transition == "offer_survey", (
        "при turn_count >= max_turns transition должен быть форсирован"
    )
    # Bot_reply сохраняется — мы не подменяем сообщение, только маршрут.
    assert result.bot_reply == "Хочется поболтать ещё! 😊"


async def test_dialogue_turn_rejects_invalid_transition() -> None:
    """Pydantic Literal должен запрещать произвольные значения."""
    with pytest.raises(ValidationError):
        DialogueTurn(bot_reply="...", transition="bogus")  # type: ignore[arg-type]


async def test_continue_dialogue_empty_history_first_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Первый ход: history=[], turn_count=0 — не падает, возвращает валидный объект."""
    expected = DialogueTurn(
        bot_reply="Привет! Спасибо, что поделился отзывом 💛",
        transition="continue",
        insights={},
    )

    async def fake_chat(messages, **kwargs):
        return expected

    monkeypatch.setattr("core.agent.nodes.dialogue.chat_completion", fake_chat)

    result = await continue_dialogue(
        feedback_summary='{"summary":"good","sentiment":"positive","topics":[],"emotion":""}',
        history=[],
        restaurant_context="",
        turn_count=0,
        max_turns=5,
    )

    assert isinstance(result, DialogueTurn)
    assert result.transition == "continue"
    assert result.bot_reply.startswith("Привет")
