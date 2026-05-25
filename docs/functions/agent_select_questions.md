# agent.nodes.select_adaptive_questions

## Назначение

LangGraph node: получает `FeedbackSummary` + пул вопросов → возвращает упорядоченный список question_id (3–5 штук), наиболее релевантных контексту отзыва. Метрики, уже очевидные из отзыва, пропускаются.

## Сигнатура

```python
class SelectedQuestions(BaseModel):
    question_ids: list[str]  # 3..5
    reasoning: str  # для логов

async def select_adaptive_questions(
    summary: FeedbackSummary,
    pool: list[dict],  # из tools.get_active_questions
    *,
    min_questions: int = 3,
    max_questions: int = 5,
) -> SelectedQuestions: ...
```

## Зависимости

- `agent.prompts.build_select_prompt`.
- `integrations.openai_chat.chat_completion`.

## Шаги реализации

1. Если `pool` пустой → вернуть `SelectedQuestions(question_ids=[], reasoning="empty pool")`. Это сигнал caller'у пропустить интервью.
2. Сформировать строковое представление пула: `"\n".join(f"- {q['id']} [{q['metric_key']}]: {q['text']}" for q in pool)`.
3. `prompt.format_messages(feedback_summary=summary.model_dump_json(), pool=pool_str, min=min_questions, max=max_questions)`.
4. `result = await chat_completion(messages, response_model=SelectedQuestions)`.
5. Защита: отфильтровать `question_ids`, оставив только те, что реально есть в pool. Усечь до `max_questions`. Если < `min_questions` — взять первые `min_questions` из pool как fallback.
6. Вернуть.

## Edge cases

- **Пустой пул** → `SelectedQuestions(question_ids=[])`.
- **LLM вернул лишние id** — отфильтровываем.
- **LLM вернул дубликаты** — `list(dict.fromkeys(ids))`.
- **Меньше min** — добиваем из pool.

## Тесты

- `test_empty_pool_returns_empty`
- `test_filters_unknown_ids`
- `test_truncates_above_max`
- `test_pads_below_min_from_pool`
- `test_dedup_ids`

## /goal

> `select_adaptive_questions` в `agent/nodes/select.py`; тесты зелёные; коммит `feat(agent): implement select_adaptive_questions`.

## Команда

T1; `fn-agent-select`.

## Next

→ [agent_extract_metric.md](agent_extract_metric.md)
