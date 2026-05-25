# agent.prompts.build_interview_prompts

## Назначение

Централизованная фабрика `ChatPromptTemplate` для всех агентских узлов: `analyze`, `select`, `extract`, `card`. Здесь хранится «тон» Need-eat (см. концепт-референс в [need-eat/]). Промпты — однострочные шаблоны для теста без LLM-вызовов.

## Сигнатура

```python
from langchain_core.prompts import ChatPromptTemplate

def build_analyze_prompt() -> ChatPromptTemplate: ...
def build_select_prompt() -> ChatPromptTemplate: ...
def build_extract_prompt() -> ChatPromptTemplate: ...
def build_card_prompt() -> ChatPromptTemplate: ...
```

Все возвращают `ChatPromptTemplate` с заранее определёнными placeholder'ами для `format_messages(**kwargs)`.

## Зависимости

- `langchain_core.prompts.ChatPromptTemplate`.

## Шаги реализации

`agent/prompts.py`:

```python
ANALYZE_SYSTEM = """Ты — помощник ресторана, который анализирует свободный отзыв гостя.
Выдели: краткое summary, общий sentiment (positive|neutral|negative), список topics, эмоциональный окрас.
Отвечай строго JSON-объектом."""

SELECT_SYSTEM = """Ты — помощник ресторана. По первоначальному отзыву гостя и доступному пулу вопросов
выбери 3–5 наиболее релевантных вопросов. Не задавай вопросы, чья метрика уже очевидна из отзыва."""

EXTRACT_SYSTEM = """Извлеки структурированное значение ответа гостя для метрики.
Тип ожидается: {expected_type}. Если ответ не даёт уверенности — верни null."""

CARD_SYSTEM = """Сформируй краткую карточку клиента (3-6 предложений) на основе отзыва,
извлечённых метрик и диалога. Текст пишется как «третьим лицом для аналитика»."""

def build_analyze_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", ANALYZE_SYSTEM),
        ("user", "Отзыв:\n{feedback_text}"),
    ])
# ... аналогично остальные
```

## Edge cases

- Тестируем структуру (placeholder'ы), не содержание.

## Тесты

- `test_analyze_prompt_has_feedback_placeholder`
- `test_select_prompt_has_pool_and_feedback`
- `test_extract_prompt_has_question_and_answer`
- `test_card_prompt_has_dialog`
- `test_format_messages_returns_two_messages` (system + user)

## /goal

> 4 prompt-builder функции в `agent/prompts.py`; тесты зелёные; коммит `feat(agent): implement interview prompts`.

## Команда

T1; `fn-agent-prompts`.

## Next

→ [agent_analyze_feedback.md](agent_analyze_feedback.md)
