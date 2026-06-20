"""Tests for bot_admin.handlers.fallback — free-form admin text → analytics agent.

The fallback imports `answer_v2` directly, so we patch it at
`bot_admin.handlers.fallback.answer_v2`. Two reply branches are covered:
the always-sent `answer_text`, and the optional fenced `chart_text` block.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message

from core.agent.analytics_agent.types import AnalyticsAnswer
from presentations.telegram_admin.handlers.fallback import admin_handle_freetext_fallback


def _mk_message(text: str | None = "сколько отзывов за неделю?") -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.from_user = SimpleNamespace(id=1, full_name="Tester")
    msg.chat = SimpleNamespace(id=42)
    msg.text = text
    msg.answer = AsyncMock()
    msg.bot = None
    return msg


def _answer(
    answer_text: str = "За неделю 12 отзывов.", chart_text: str | None = None
) -> AnalyticsAnswer:
    return AnalyticsAnswer(answer_text=answer_text, chart_text=chart_text)


# --------------------------------------------------------------------------- #
# happy path


async def test_fallback_routes_text_to_answer_v2() -> None:
    msg = _mk_message()
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.fallback.answer_v2",
            new=AsyncMock(return_value=_answer("За неделю 12 отзывов.")),
        ) as m,
    ):
        await admin_handle_freetext_fallback(msg)
    m.assert_awaited_once()
    # вопрос передан как первый позиционный аргумент
    assert m.await_args is not None
    assert m.await_args.args[0] == "сколько отзывов за неделю?"
    msg.answer.assert_awaited_once_with("За неделю 12 отзывов.")


async def test_fallback_sends_chart_text_as_second_message() -> None:
    msg = _mk_message()
    chart = "[template:bar.distribution]\nЧастота заказов · 30 днів\nужин | 2\nбизнес | 1"
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.fallback.answer_v2",
            new=AsyncMock(return_value=_answer("Вот распределение:", chart_text=chart)),
        ),
    ):
        await admin_handle_freetext_fallback(msg)
    assert msg.answer.await_count == 2
    # первое — текст ответа
    assert msg.answer.await_args_list[0].args[0] == "Вот распределение:"
    # второе — chart обёрнут в ```text ...``` с Markdown parse_mode
    second_call = msg.answer.await_args_list[1]
    chart_msg = second_call.args[0]
    assert chart_msg.startswith("```text\n")
    assert chart_msg.endswith("\n```")
    # тег шаблона срезан (бот не рисует графики), заголовок и данные остались
    assert "[template:" not in chart_msg
    assert "Частота заказов · 30 днів" in chart_msg
    assert "ужин | 2" in chart_msg
    assert second_call.kwargs.get("parse_mode") == "Markdown"


async def test_fallback_untagged_chart_passes_through() -> None:
    msg = _mk_message()
    chart = "позитив | 65\nнегатив | 35"  # legacy/untagged — нечего срезать
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.fallback.answer_v2",
            new=AsyncMock(return_value=_answer("Вот доли:", chart_text=chart)),
        ),
    ):
        await admin_handle_freetext_fallback(msg)
    assert msg.answer.await_count == 2
    assert chart in msg.answer.await_args_list[1].args[0]


async def test_fallback_skips_empty_chart_after_tag_strip() -> None:
    msg = _mk_message()
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.fallback.answer_v2",
            new=AsyncMock(
                return_value=_answer("Только текст.", chart_text="[template:bar.distribution]")
            ),
        ),
    ):
        await admin_handle_freetext_fallback(msg)
    # тег без данных → после среза пусто → второе сообщение не шлём
    msg.answer.assert_awaited_once_with("Только текст.")


async def test_fallback_no_chart_sends_single_message() -> None:
    msg = _mk_message()
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.fallback.answer_v2",
            new=AsyncMock(return_value=_answer("Просто текст.", chart_text=None)),
        ),
    ):
        await admin_handle_freetext_fallback(msg)
    msg.answer.assert_awaited_once_with("Просто текст.")


async def test_fallback_empty_answer_text_uses_fallback_string() -> None:
    msg = _mk_message()
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "presentations.telegram_admin.handlers.fallback.answer_v2",
            new=AsyncMock(return_value=_answer("", chart_text=None)),
        ),
    ):
        await admin_handle_freetext_fallback(msg)
    msg.answer.assert_awaited_once_with("Не получилось обработать запрос.")


# --------------------------------------------------------------------------- #
# guards — no LLM call


async def test_fallback_non_admin_skips_agent() -> None:
    msg = _mk_message()
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=False),
        ),
        patch("presentations.telegram_admin.handlers.fallback.answer_v2", new=AsyncMock()) as m,
    ):
        await admin_handle_freetext_fallback(msg)
    m.assert_not_awaited()
    msg.answer.assert_not_awaited()


async def test_fallback_empty_text_skips_agent() -> None:
    msg = _mk_message(text=None)
    with (
        patch(
            "presentations.telegram_admin.handlers.fallback.require_admin",
            new=AsyncMock(return_value=True),
        ),
        patch("presentations.telegram_admin.handlers.fallback.answer_v2", new=AsyncMock()) as m,
    ):
        await admin_handle_freetext_fallback(msg)
    m.assert_not_awaited()
    msg.answer.assert_not_awaited()
