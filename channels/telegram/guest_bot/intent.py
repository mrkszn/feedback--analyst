"""Lightweight intent check for the guest bot's first message.

A brand-new user who just types "привет" should be greeted and asked for
their feedback — NOT have "привет" run through the feedback pipeline as if
it were a delivery review (that double-messages them and opens a nonsense
session keyed on the greeting). This module answers the single question the
greeting handlers need: *is this message a bare opener, or real feedback?*

Intentionally a hand-rolled heuristic, no LLM call: the check runs on the
hot path before we've committed to a session, so it must be instant and
free. The rule is deliberately conservative — only a SHORT message made up
ENTIRELY of known opener words counts as a greeting — because a false
positive would drop a real review, which is worse than the occasional
greeting that slips through to the pipeline.
"""

from __future__ import annotations

import re

# Content-free openers a user might send instead of /start or actual
# feedback. Lowercase, punctuation-stripped. Includes the individual parts
# of the common two/three-word Russian day-greetings ("добрый день",
# "доброго времени суток") so the all-words-are-openers rule accepts them.
_GREETING_WORDS: frozenset[str] = frozenset(
    {
        # ru — hellos
        "привет",
        "приветик",
        "приветики",
        "прив",
        "превед",
        "здравствуй",
        "здравствуйте",
        "здрасте",
        "здрасьте",
        "здарова",
        "здарово",
        "здорово",
        "хай",
        "ку",
        "салют",
        "дратути",
        "ну",
        # ru — day-greeting parts
        "доброго",
        "добрый",
        "доброе",
        "день",
        "дня",
        "утро",
        "утра",
        "вечер",
        "вечера",
        "ночи",
        "времени",
        "суток",
        # ru — start/help openers typed as plain text (not the /command)
        "старт",
        "начать",
        "начнем",
        "начнём",
        "поехали",
        "меню",
        "помощь",
        "тест",
        "проверка",
        # en
        "hello",
        "hi",
        "hiya",
        "hey",
        "heya",
        "yo",
        "sup",
        "good",
        "morning",
        "evening",
        "afternoon",
        "greetings",
        "start",
        "test",
    }
)

# Longest accepted greeting is "доброго времени суток" (3 words); give one
# word of slack. Anything longer is treated as feedback no matter what.
_MAX_GREETING_WORDS = 4


def looks_like_greeting(text: str) -> bool:
    """True if `text` is a bare greeting/opener rather than real feedback.

    Conservative by design: returns True only for a short message whose
    every token is a known opener word (or a content-free emoji/punctuation
    blip). Examples::

        looks_like_greeting("привет")                  -> True
        looks_like_greeting("Привет! 👋")               -> True
        looks_like_greeting("ну привет")               -> True
        looks_like_greeting("добрый день")             -> True
        looks_like_greeting("👋")                       -> True
        looks_like_greeting("привет, пицца холодная")  -> False
        looks_like_greeting("всё супер, спасибо")       -> False
        looks_like_greeting("долго ждал курьера")       -> False
    """
    # Strip emoji/punctuation, keep word chars + whitespace, lowercase.
    cleaned = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE).lower()
    words = cleaned.split()
    if len(words) > _MAX_GREETING_WORDS:
        return False
    if not words:
        # Pure emoji / punctuation ("👋", "!!!") — content-free, not feedback.
        return True
    return all(word in _GREETING_WORDS for word in words)
