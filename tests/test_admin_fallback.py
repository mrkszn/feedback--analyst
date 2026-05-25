"""Unit-тесты для bot_admin.handlers.fallback.

Проверяем:
- router имеет правильное имя и зарегистрированный handler;
- admin-путь (is_admin → True): handler отвечает help-текстом со списком команд;
- non-admin-путь (is_admin → False): handler не отправляет help-текст;
  вместо этого срабатывает gate `require_admin` и отвечает «Доступ только для админов…».
"""

from unittest.mock import AsyncMock, MagicMock, patch

from bot_admin.handlers.fallback import admin_handle_freetext_fallback, router


def test_fallback_router_smoke() -> None:
    """Router'у дано правильное имя и есть зарегистрированный message-handler."""
    assert router.name == "admin_fallback"
    assert len(router.message.handlers) >= 1


async def test_admin_path_returns_help_text() -> None:
    """is_admin → True: handler отвечает help-текстом со списком всех 5 команд."""
    message = MagicMock()
    message.from_user = MagicMock(id=42)
    message.answer = AsyncMock()

    with patch(
        "bot_admin.handlers.questions.is_admin",
        new=AsyncMock(return_value=True),
    ):
        await admin_handle_freetext_fallback(message)

    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert text.startswith("Я понимаю только команды")
    for cmd in (
        "/questions",
        "/add_question",
        "/edit_question",
        "/delete_question",
        "/invite_admin",
    ):
        assert cmd in text, f"help-текст должен упоминать {cmd}"


async def test_non_admin_path_hits_admin_gate() -> None:
    """is_admin → False: help-текст НЕ отправляется; gate `require_admin` отвечает access-denied."""
    message = MagicMock()
    message.from_user = MagicMock(id=99)
    message.answer = AsyncMock()

    with patch(
        "bot_admin.handlers.questions.is_admin",
        new=AsyncMock(return_value=False),
    ):
        await admin_handle_freetext_fallback(message)

    # message.answer вызван один раз — но не help-текстом, а access-denied от gate'а.
    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "Доступ только для админов" in text
    assert "/claim" in text
    # help-текст НЕ должен быть отправлен.
    assert not text.startswith("Я понимаю только команды")


async def test_non_admin_no_from_user_silent() -> None:
    """Если message.from_user is None — gate сразу возвращает False, ничего не отвечает."""
    message = MagicMock()
    message.from_user = None
    message.answer = AsyncMock()

    await admin_handle_freetext_fallback(message)

    message.answer.assert_not_called()
