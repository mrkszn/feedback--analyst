"""Catch-all admin handler — free-form text goes to the analytics agent.

Registered LAST in `bot_admin/__main__.py` so slash commands, reply-keyboard
button matches, and active FSM states win first. Anything that reaches here
is free-form text from an admin outside any FSM flow → routed to the
analytics agent (`agent/analytics_agent/runner.py:answer_v2`).

Question-pool CRUD now lives behind explicit commands (/add_question,
/edit_question, /delete_question + their keyboards). The conversational CRUD
agent (`admin_agent.py`) is kept for reuse via the HTTP API but is no longer
wired to free text here.
"""

import re

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from core.agent.analytics_agent.runner import answer_v2
from presentations.telegram_admin.handlers.questions import require_admin

router = Router(name="admin_fallback")

_TEMPLATE_TAG_RE = re.compile(r"^\[template:[^\]]+\]\s*$")


def _chart_text_for_telegram(chart_text: str) -> str:
    """Telegram can't render Mini App chart templates, so drop the leading
    `[template:<id>]` tag and keep the title + data lines as plain text."""
    lines = chart_text.split("\n")
    if lines and _TEMPLATE_TAG_RE.match(lines[0].strip()):
        lines = lines[1:]
    return "\n".join(lines).strip()


@router.message(StateFilter(None))
async def admin_handle_freetext_fallback(message: Message) -> None:
    if not await require_admin(message):
        return
    if not message.text:
        return

    bot = message.bot
    if bot is not None:
        async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
            answer = await answer_v2(message.text, history=None)
    else:
        answer = await answer_v2(message.text, history=None)

    await message.answer(answer.answer_text or "Не получилось обработать запрос.")
    if answer.chart_text:
        chart = _chart_text_for_telegram(answer.chart_text)
        if chart:
            await message.answer(f"```text\n{chart}\n```", parse_mode="Markdown")
