"""Centralised user-facing copy for the guest bot.

These strings used to live inline across feedback.py / dialogue.py /
survey_consent.py and had already drifted (three slightly different
goodbyes). Keeping them here means the warm close + survey offer can't
diverge again, and the "next time" bridge that turns a one-and-done form
into a returnable loop lives in exactly one place.
"""

from __future__ import annotations

# Warm close — not a dead-end "Хорошего дня". Reinforces that the owner
# actually reads feedback (the non-monetary "you're heard" hook) and bridges
# to the next order so the loop feels ongoing. Keeps "Спасибо большое" + 🙏.
GUEST_GOODBYE = (
    "Спасибо большое! 🙏 Владелец читает каждый отзыв — твой точно увидит. До следующего заказа! 🙌"
)

# Shown when we offer the structured survey after the dialogue. NO discount
# promise here — v1 has no reward mechanism, so promising one would be the
# same broken promise we're removing.
SURVEY_OFFER = (
    "Спасибо за разговор! 🙏 У сервиса есть пара коротких вопросов "
    "специально под твой отзыв — займут минутку. Поможешь?"
)
