# bot_guest.handlers.feedback.guest_answer

## Назначение

Принимает текстовый ответ гостя на текущий вопрос интервью (состояние `IN_INTERVIEW`). Извлекает метрику, сохраняет в `session_answers`, двигает курсор `question_index`. Когда вопросы кончились — `_finalize_session`.

## Шаги

1. Извлечь текущий вопрос из FSM `questions_map[question_ids[question_index]]`.
2. `append_session_message(role="user")`.
3. `extract_metric_from_answer(question=q, answer_text=text)` → `marked`.
4. `save_answer_with_metric(...)`.
5. Сохранить в FSM `answers` (для дальнейшего `build_client_card`).
6. Инкремент `question_index`, `_ask_next_question`.
7. Если `idx >= len(qids)` — `_finalize_with_state` → `_finalize_session`.

`_finalize_session`:
1. Перейти в `FINALIZING`.
2. `build_client_card(summary, answers)` → `ClientCard`.
3. `embed_text(card.summary_text)` → vector.
4. `upsert_client_card_vector(...)` → vector_id.
5. `save_client_card(...)`.
6. `end_session(session_id)`.
7. `state.clear()`, благодарность гостю.

## /goal

Полный цикл собирает все ответы, финализирует, пишет client_card и в Supabase, и в Pinecone.

## Next

→ [guest_handle_cancel.md](guest_handle_cancel.md)
