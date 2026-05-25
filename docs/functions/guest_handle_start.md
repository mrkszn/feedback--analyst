# bot_guest.handlers.start.guest_start

## Назначение

Хэндлер `/start` гостевого бота. Создаёт/находит клиента в `clients`, ставит FSM в `AWAITING_FEEDBACK`, шлёт приветствие.

## Сигнатура

```python
@router.message(CommandStart())
async def guest_start(message: Message, state: FSMContext) -> None: ...
```

## Шаги

1. `create_or_get_client(telegram_id=user.id, name=user.full_name)`.
2. `state.set_state(GuestFlow.AWAITING_FEEDBACK)`.
3. Ответ с приветствием.

## Edge

- `message.from_user is None` → silent return.

## Тесты

Integration через aiogram-test (не написаны: smoke в `test_handlers_import.py` подтверждает регистрацию).

## /goal

Создан handler в `bot_guest/handlers/start.py`, импортируется без ошибок, регистрируется в `Router`.

## Next

→ [guest_handle_feedback_text.md](guest_handle_feedback_text.md)
