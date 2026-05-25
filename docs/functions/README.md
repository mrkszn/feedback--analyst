# docs/functions — индекс runtime-функций

Каждый файл в этой папке описывает **одну** runtime-функцию проекта (handler, tool, service, integration или узел LangGraph) по единому шаблону:

- **Назначение** — что делает, когда вызывается
- **Сигнатура** — Python-сигнатура + типы
- **Зависимости** — модули / таблицы / внешние API
- **Шаги реализации**
- **Edge cases**
- **Тесты** (unit / интеграция / ручной)
- **/goal** — done-критерий функции
- **Команда (TeamCreate)** — шаблон T1/T2 + состав + ссылки на промпты ролей
- **Permissions** — наследуются из `.claude/settings.local.json`
- **Next** — ссылка на следующую функцию в handoff-цепочке

Подробное описание шаблона, промпты ролей, схемы команд — в [плане](../../../../.claude/plans/imperative-stirring-dove.md), документ доступен агентам через путь, известный тимлиду.

## Принцип работы

Под каждую функцию **создаётся отдельная команда** через `TeamCreate({team_name: "fn-<slug>"})`. Тимлид читает соответствующий `.md`, дробит на подзадачи через TaskCreate/TaskUpdate, ведёт implementer + tester + reviewer. По достижении `/goal` отправляет handoff команде следующей функции (см. `Next`).

Файл в этой папке появляется **в момент**, когда команда стартует над функцией. Отсутствие файла = работы по нему ещё не было.

---

## Handoff-цепочка (33 функции v1)

### A. Utils & Integrations
1. [utils_voice_download.md](utils_voice_download.md) — `download_voice_to_tmp`
2. [integrations_openai_chat.md](integrations_openai_chat.md) — `chat_completion` (GPT-5.x, function calling)
3. [integrations_whisper_transcribe.md](integrations_whisper_transcribe.md) — `transcribe_voice`
4. [integrations_openai_embed.md](integrations_openai_embed.md) — `embed_text`
5. [integrations_pinecone_upsert.md](integrations_pinecone_upsert.md) — `upsert_client_card_vector`

### B. Services
6. [services_admin_auth.md](services_admin_auth.md) — `is_admin` + `claim_admin`
7. [services_client_upsert.md](services_client_upsert.md) — `create_or_get_client`
8. [services_session_start.md](services_session_start.md) — `start_session`
9. [services_session_append_message.md](services_session_append_message.md) — `append_session_message`
10. [services_session_save_feedback.md](services_session_save_feedback.md) — `save_feedback_summary`
11. [services_session_end.md](services_session_end.md) — `end_session`
12. [services_questions_crud.md](services_questions_crud.md) — `create/update/delete/list_questions`

### C. Tools (вызовы внутри LangGraph-узлов)
13. [tools_get_questions_pool.md](tools_get_questions_pool.md) — `get_active_questions`
14. [tools_save_answer_metric.md](tools_save_answer_metric.md) — `save_answer_with_metric`
15. [tools_save_client_card.md](tools_save_client_card.md) — `save_client_card`

### D. Agent layer (LangGraph nodes)
16. [agent_build_interview_prompt.md](agent_build_interview_prompt.md) — `ChatPromptTemplate` set
17. [agent_analyze_feedback.md](agent_analyze_feedback.md) — `analyze_feedback_node`
18. [agent_select_questions.md](agent_select_questions.md) — `select_adaptive_questions_node`
19. [agent_extract_metric.md](agent_extract_metric.md) — `extract_metric_node`
20. [agent_build_client_card.md](agent_build_client_card.md) — `build_client_card_node`

### E. Guest bot handlers
21. [guest_handle_start.md](guest_handle_start.md) — `guest_start`
22. [guest_handle_feedback_text.md](guest_handle_feedback_text.md) — `guest_feedback_text`
23. [guest_handle_feedback_voice.md](guest_handle_feedback_voice.md) — `guest_feedback_voice`
24. [guest_handle_answer.md](guest_handle_answer.md) — `guest_answer`
25. [guest_handle_cancel.md](guest_handle_cancel.md) — `guest_cancel`

### F. Admin bot handlers
26. [admin_handle_claim.md](admin_handle_claim.md) — `admin_claim` (разовая регистрация первого админа)
27. [admin_handle_start.md](admin_handle_start.md) — `admin_start`
28. [admin_handle_questions_list.md](admin_handle_questions_list.md) — `admin_questions_list`
29. [admin_handle_question_add.md](admin_handle_question_add.md) — `admin_question_add`
30. [admin_handle_question_edit.md](admin_handle_question_edit.md) — `admin_question_edit`
31. [admin_handle_question_delete.md](admin_handle_question_delete.md) — `admin_question_delete`
32. [admin_handle_invite_admin.md](admin_handle_invite_admin.md) — `admin_invite_admin`

### G. API
33. [api_health.md](api_health.md) — `GET /health` *(конец цепочки v1)*

---

## Параллелизация

Функции в одной группе без взаимных зависимостей могут стартовать параллельно. Реальные «развилки»:
- **Группа A (1–5):** все 5 функций независимы между собой → можно гнать параллельно 5 команд.
- **Группа B (6–12):** последовательно (B.7 зависит от B.6, и т.д.).
- **Группы E и F:** параллельно (разные боты, разные FSM, общая БД).
- **G:** после E и F.

Тимлиды координируются между собой через `SendMessage` по имени `fn-<slug>-team-lead`.
