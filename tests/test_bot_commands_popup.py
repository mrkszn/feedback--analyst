"""Smoke-проверка popup-меню команд (BotFather-style) для обоих ботов.

Сами `set_my_commands` вызовы тестируются косвенно через структуру списков
команд — список должен содержать обязательные пункты и быть стабильным,
чтобы пользователи видели предсказуемое меню при `/`.
"""

from aiogram.types import BotCommand

from channels.telegram.guest_bot.__main__ import GUEST_COMMANDS
from presentations.telegram_admin.__main__ import ADMIN_COMMANDS


def _commands_dict(items: list[BotCommand]) -> dict[str, str]:
    return {c.command: c.description for c in items}


def test_guest_commands_minimal_set() -> None:
    cmds = _commands_dict(GUEST_COMMANDS)
    assert "start" in cmds
    assert "cancel" in cmds
    for desc in cmds.values():
        assert desc.strip(), "BotCommand description must not be empty"


def test_admin_commands_cover_phase_2a_baseline() -> None:
    cmds = _commands_dict(ADMIN_COMMANDS)
    for required in (
        "start",
        "claim",
        "questions",
        "add_question",
        "edit_question",
        "delete_question",
        "invite_admin",
    ):
        assert required in cmds, f"admin popup menu missing /{required}"


def test_admin_commands_include_analytics_surface() -> None:
    """После Phase-5 cleanup в popup-меню только /statistics + /topics.

    Старые /ask /insights /metric /find /clients убраны до редизайна агента.
    """
    cmds = _commands_dict(ADMIN_COMMANDS)
    for required in ("statistics", "topics", "settings"):
        assert required in cmds, f"admin popup menu missing /{required}"
    for removed in ("ask", "insights", "metric", "find", "clients"):
        assert removed not in cmds, f"/{removed} should be removed from popup"


def test_command_descriptions_under_telegram_limit() -> None:
    # Telegram limit: command description ≤ 256 chars; в UI помещается ~64.
    # Держим разумно коротко чтобы popup не сужался.
    for items in (GUEST_COMMANDS, ADMIN_COMMANDS):
        for c in items:
            assert len(c.description) <= 64, (
                f"/{c.command} description too long for popup: {c.description!r}"
            )
