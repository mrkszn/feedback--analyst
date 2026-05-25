# bot_guest.handlers.feedback.guest_cancel

## Назначение

`/cancel` в любом состоянии — закрывает текущую сессию (если есть), чистит FSM, отвечает.

## Шаги

1. Извлечь `session_id` из FSM data (опционально).
2. Если есть — `end_session(session_id)` (ловим `LookupError`).
3. `state.clear()`.
4. Ответ.

## /goal

`/cancel` отрабатывает корректно даже при отсутствии активной сессии.

## Next

→ [admin_handle_claim.md](admin_handle_claim.md)
