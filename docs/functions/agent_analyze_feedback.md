# agent.nodes.analyze_feedback

## Назначение

LangGraph node: принимает `feedback_text` гостя → возвращает structured `FeedbackSummary` через GPT-5.x. Используется как первый узел после получения отзыва.

## Сигнатура

```python
from pydantic import BaseModel
from typing import Literal

class FeedbackSummary(BaseModel):
    summary: str
    sentiment: Literal["positive", "neutral", "negative"]
    topics: list[str]
    emotion: str

async def analyze_feedback(feedback_text: str) -> FeedbackSummary: ...
```

## Зависимости

- `agent.prompts.build_analyze_prompt`.
- `integrations.openai_chat.chat_completion` (с `response_model=FeedbackSummary`).

## Шаги реализации

1. Валидация: `feedback_text.strip()` непустой → иначе `ValueError`.
2. `prompt = build_analyze_prompt()`.
3. `messages = prompt.format_messages(feedback_text=feedback_text)`.
4. Преобразовать к dict-формату ожидаемому `chat_completion`: `[{"role": m.type.replace("human","user"), "content": m.content} for m in messages]`.
5. `result = await chat_completion(messages, response_model=FeedbackSummary)`.
6. Вернуть `result`.

## Edge cases

- **Пустой текст** → `ValueError`.
- **LLM вернул невалидный JSON** → `pydantic.ValidationError` пробрасывается.

## Тесты

- `test_returns_feedback_summary` — мок `chat_completion` возвращает `FeedbackSummary(...)`, проверяем результат.
- `test_empty_text_raises`
- `test_uses_structured_output` — проверяем что вызов `chat_completion` был с `response_model=FeedbackSummary`.

## /goal

> `analyze_feedback` в `agent/nodes/analyze.py`; тесты зелёные; коммит `feat(agent): implement analyze_feedback`.

## Команда

T1; `fn-agent-analyze`.

## Next

→ [agent_select_questions.md](agent_select_questions.md)
