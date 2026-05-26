"""Catch-all admin handler — routes free-text to one of two LLM agents.

Registered LAST in `bot_admin/__main__.py` so slash commands, reply-keyboard
button matches, mode toggle, and active FSM states win first. Anything that
reaches here is free-form text from an admin outside any FSM flow.

Routing depends on the `admin_mode` FSM data:

- `admin` (default) — `bot_admin.handlers.admin_agent.reply_via_agent`
  (questions-CRUD via `tools/admin_question_tools.py`).
- `analytics` — `agent.nodes.admin_ask.answer_admin_question`
  (live analytics via `services.analytics`).
"""

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from agent.nodes.admin_ask import answer_admin_question
from bot_admin.handlers.admin_agent import reply_via_agent
from bot_admin.handlers.questions import require_admin

router = Router(name="admin_fallback")


async def reply_via_admin_ask(message: Message) -> None:
    """Send analytics-agent reply with typing indicator + optional chart block."""
    if not message.text:
        return
    bot = getattr(message, "bot", None)
    if bot is not None:
        async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
            answer = await answer_admin_question(message.text)
    else:
        answer = await answer_admin_question(message.text)
    text = (answer.answer_text or "").strip() or "Готов помочь дальше."
    if answer.chart_text:
        await message.answer(f"{text}\n\n```\n{answer.chart_text}\n```", parse_mode="Markdown")
    else:
        await message.answer(text)


@router.message(StateFilter(None))
async def admin_handle_freetext_fallback(message: Message, state: FSMContext) -> None:
    if not await require_admin(message):
        return
    if not message.text:
        return
    data = await state.get_data()
    mode = data.get("admin_mode", "admin")
    if mode == "analytics":
        await reply_via_admin_ask(message)
    else:
        await reply_via_agent(message)
