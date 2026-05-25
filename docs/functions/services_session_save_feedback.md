# services.sessions.save_feedback_summary

## Назначение

После того как агент проанализировал `feedback_raw_text`, записать обратно в `sessions`:
- `feedback_raw_text` — оригинал
- `feedback_source` — `text`|`voice`
- `feedback_summary` — JSON `{summary, sentiment, topics[], emotion}`
- `language` — детектированный

## Сигнатура

```python
from typing import Literal, TypedDict

class FeedbackSummary(TypedDict):
    summary: str
    sentiment: str
    topics: list[str]
    emotion: str

async def save_feedback_summary(
    session_id: str | UUID,
    *,
    raw_text: str,
    source: Literal["text", "voice"],
    summary: FeedbackSummary,
    language: str | None = None,
    db: Client | None = None,
) -> None: ...
```

## Шаги реализации

1. Валидация: `source in {"text","voice"}`, `raw_text` непустой.
2. `payload = {"feedback_raw_text": raw_text, "feedback_source": source, "feedback_summary": summary, "language": language}`.
3. `db.table("sessions").update(payload).eq("id", str(session_id)).execute()` через `asyncio.to_thread`.

## Edge cases

- **Невалидный source** → `ValueError`.
- **Сессия не найдена** → resp.data пустой; пробрасываем `LookupError`.

## Тесты

- `test_saves_text_feedback`
- `test_saves_voice_feedback`
- `test_session_not_found_raises`
- `test_invalid_source_raises`

## /goal

> `save_feedback_summary` в `services/sessions.py`; коммит `feat(services): implement save_feedback_summary`.

## Команда

T1; `fn-svc-session-fb`.

## Next

→ [services_session_end.md](services_session_end.md)
