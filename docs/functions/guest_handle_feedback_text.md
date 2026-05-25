# bot_guest.handlers.feedback.guest_feedback_text

## Назначение

Принимает текстовое сообщение в состоянии `AWAITING_FEEDBACK`, запускает агентский пайплайн через общий `_process_feedback`.

## Шаги

1. Извлечь `message.text`, strip.
2. Если пусто — попросить повторить.
3. Вызвать `_process_feedback(raw_text=text, source="text")`.

`_process_feedback`:
1. `create_or_get_client` → `start_session` → сохранение `session_id`/`client_id` в FSM data.
2. `append_session_message(role="user")`.
3. `analyze_feedback(text)` → `save_feedback_summary(summary, source, language)`.
4. `get_active_questions()` → `select_adaptive_questions(summary, pool)`.
5. Если пул пуст или selected пусто — сразу `_finalize_session`.
6. Иначе — сохранить selected/answers/questions_map в FSM, перейти в `IN_INTERVIEW`, задать первый вопрос.

## /goal

`guest_feedback_text` зарегистрирован в Router; пайплайн вызывает все нижние слои.

## Next

→ [guest_handle_feedback_voice.md](guest_handle_feedback_voice.md)
