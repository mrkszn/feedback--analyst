"""Catch-all admin handler — free-form text goes to the questions-CRUD agent.

Registered LAST in `bot_admin/__main__.py` so slash commands, reply-keyboard
button matches, and active FSM states win first. Anything that reaches here
is free-form text from an admin outside any FSM flow → routed to the
questions-CRUD agent (`tools/admin_question_tools.py`).

Analytics agent has been retired pending a redesign (see Phase 5 plan).
"""

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from bot_admin.handlers.admin_agent import reply_via_agent
from bot_admin.handlers.questions import require_admin

router = Router(name="admin_fallback")


@router.message(StateFilter(None))
async def admin_handle_freetext_fallback(message: Message) -> None:
    if not await require_admin(message):
        return
    if not message.text:
        return
    await reply_via_agent(message)
