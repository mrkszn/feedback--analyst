# agent.nodes.build_client_card

## Назначение

Финальный узел: получает всю собранную информацию (отзыв, summary, ответы с метриками) → генерирует свободно-текстовую карточку клиента 3–6 предложений «третьим лицом». Эта карточка эмбеддится и идёт в Pinecone + параллельно в `client_cards.summary_text`.

## Сигнатура

```python
class ClientCard(BaseModel):
    summary_text: str
    sentiment: str  # переносим из FeedbackSummary, упрощает upsert metadata
    topics: list[str]

async def build_client_card(
    *,
    feedback_summary: FeedbackSummary,
    answers: list[dict],  # [{question_text, metric_key, answer_text, marked_value}]
) -> ClientCard: ...
```

## Зависимости

- `agent.prompts.build_card_prompt`.
- `integrations.openai_chat.chat_completion`.

## Шаги реализации

1. Сборка строкового представления ответов: список с метрикой и значением.
2. `prompt.format_messages(feedback_summary=..., dialog=...)`.
3. `result = await chat_completion(messages, response_model=ClientCard)`.
4. Защита: если `result.summary_text` короче 20 символов → `ValueError("card too short")`.
5. Прокинуть `sentiment` и `topics` из `feedback_summary` если LLM их не воспроизвёл.

## Edge cases

- **Нет ответов (`answers=[]`)** — допустимо, карточка строится только из `feedback_summary`.
- **Слишком короткая карточка** → `ValueError`.

## Тесты

- `test_build_card_with_answers`
- `test_build_card_no_answers`
- `test_short_card_raises`
- `test_passes_sentiment_topics_through`

## /goal

> `build_client_card` в `agent/nodes/card.py`; тесты зелёные; коммит `feat(agent): implement build_client_card`.

## Команда

T1; `fn-agent-card`.

## Next

→ [guest_handle_start.md](guest_handle_start.md)
