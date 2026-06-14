"""Unit-тесты для channels.telegram.guest_bot.intent.looks_like_greeting.

Главная инварианта: детектор консервативен. False-positive (принять
реальный отзыв за приветствие) дороже, чем false-negative — поэтому
проверяем обе стороны таблицей примеров.
"""

from __future__ import annotations

import pytest

from channels.telegram.guest_bot.intent import looks_like_greeting

# Голые приветствия / openers — должны вернуть True (бот только поздоровается).
GREETINGS = [
    "привет",
    "Привет",
    "ПРИВЕТ",
    "привет!",
    "Привет! 👋",
    "прив",
    "приветик",
    "ну привет",
    "здравствуйте",
    "Здравствуйте!",
    "здрасте",
    "добрый день",
    "Добрый день!",
    "доброе утро",
    "добрый вечер",
    "доброго времени суток",
    "хай",
    "ку",
    "салют",
    "старт",
    "начать",
    "поехали",
    "меню",
    "тест",
    "проверка",
    "hello",
    "Hi",
    "hey",
    "good morning",
    "👋",
    "!!!",
    "   ",
]

# Реальный (пусть и короткий) фидбэк — должен вернуть False (бот обработает).
FEEDBACK = [
    "привет, привезли холодную пиццу",
    "всё супер, спасибо",
    "долго ждал курьера",
    "еда вкусная но доставка опоздала",
    "норм",
    "ок",
    "хорошо",
    "плохо",
    "спасибо большое всё понравилось",
    "курьер нагрубил",
    "добрый день, заказ опоздал на час",
    "123",
    "доставка топ",
]


@pytest.mark.parametrize("text", GREETINGS)
def test_greetings_detected(text: str) -> None:
    assert looks_like_greeting(text) is True


@pytest.mark.parametrize("text", FEEDBACK)
def test_feedback_not_treated_as_greeting(text: str) -> None:
    assert looks_like_greeting(text) is False
