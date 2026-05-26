# Phase 2A.6 — Admin UX revamp + guest finalize UX (autonomous orchestrator)

Ты — **orchestrator Phase 2A.6** проекта telegram-waiter. Главный архитектор сессии. Спавнишь команды разработчиков через TeamCreate, **не пишешь код сам**. Если в твоём харнессе TeamCreate/Agent недоступны (как было в одном из предыдущих запусков) — fallback: пишешь код напрямую через Read/Edit/Write/Bash, по тем же 7 коммитам, **одну итерацию за раз, коммит-перед-следующим**.

## Required reads (в первый ход)

1. `/Users/markdekker/.claude/plans/imperative-stirring-dove.md` — секция **«Phase 2A.6 — Admin UX revamp + guest freeze fix»** (~строки 854–940). Это твой авторитетный спек. Плюс §«Архитектурный инвариант данных» — НЕ нарушать.
2. `docs/GIT.md` — Conventional Commits, ≤72 в заголовке, 1 logical step = 1 commit.
3. `bot_admin/handlers/auth.py`, `bot_admin/handlers/questions.py`, `bot_admin/handlers/fallback.py`, `bot_admin/__main__.py`, `bot_admin/keyboards.py` — текущий admin bot wiring (commit #1 уже сделан, см. ниже).
4. `services/questions.py` — service layer.
5. `bot_common/fsm/states.py` — FSM (AdminFlow + GuestFlow).
6. `bot_guest/handlers/feedback.py` строки 195–366 — finalize path (`_ask_next_question`, `_finalize_with_state`, `_finalize_session`).
7. `agent/prompts.py`, `agent/nodes/dialogue.py` — tone reference для нового `admin_assistant`.

## Текущее состояние (стартовая точка)

- Ветка: `autonomous/phase-2a-6` (НЕ main; launcher переиспользовал через `--resume`).
- Phase 2A.5 (natural dialogue) уже в `main` — это база.
- **Commit #1 уже сделан** (`85f0260` — `feat(bot-admin): persistent reply-keyboard + warmer /start`, 4 файла, 198 тестов зелёные). НЕ переделывай — начинай с #2.
- `git log main..HEAD --oneline` покажет 1 коммит — это и есть #1.

## Time budget

- Старт: NOW
- Soft deadline: START + 1h 45m — после этого новых TeamCreate нет, wind-down
- Hard deadline: START + 2h
- `START_TS=$(date +%s)` в scratchpad, проверяй elapsed перед каждой новой командой/коммитом

🚨 **Soft-deadline gate** (урок 20260525-1621): прошлый orchestrator проигнорировал и потерял WIP. Лучше N чистых коммитов чем N+1 в панике.

## Жёсткое правило коммитов

**Запрещено** двигаться на шаг N+1 пока шаг N не закоммичен. Если git commit фейлится — СТОП, запиши blocker в `current_changes.md` под "🚨 Blocker for the human".

## Goal

Завершить **commits #2–#7** на ветке `autonomous/phase-2a-6` (commit #1 уже там). Все зелёные: `ruff`, `mypy`, `pytest`. Архитектурный инвариант сохранён (free convo → vector, structured → SQL).

## Sub-tasks (= commits) — продолжаем со #2

### #2 — `feat(bot-admin): readable /questions with inline edit/delete`

- Переписать `admin_questions_list` в `bot_admin/handlers/questions.py`: numbered list, БЕЗ UUID в видимом тексте, БЕЗ `[metric_key, type]` тэгов inline. Пример: `1. Понравилась ли еда? (boolean)`
- Per-item inline keyboard: `[✏️ Изменить] [🗑 Удалить]`, callback_data `qedit:{uuid}` / `qdel:{uuid}`
- Footer inline: `[🗑 Удалить все]` → callback `qdelall`
- Confirmation flow для single-delete (`[✅ Да] [✖️ Отмена]`)
- Тесты

### #3 — `feat(services): deactivate_all_questions + admin handler`

- `services/questions.py::deactivate_all_questions(restaurant_id: UUID | None = None) -> int` — soft-delete (`is_active=false`), возвращает count
- Handler `qdelall` callback → confirm `[✅ Да] [✖️ Отмена]` → on yes service call, report «Все N вопросов скрыты»
- Тесты сервиса + хендлера

### #4 — `feat(bot-admin): in-dialog AI-assisted question creation`

- `agent/nodes/admin_assistant.py` (new): `draft_question_from_nl(description: str) -> QuestionDraft` — pydantic с `text`, `metric_key`, `expected_type`, optional `enum_values`. LLM structured output.
- `bot_admin/handlers/admin_question_dialog.py` (new): третий режим `/add_question` рядом с текст/голос. Flow:
  1. Admin → `[💬 В диалоге]` → state `AWAITING_NL_DESCRIPTION`
  2. Admin типает/голос → `draft_question_from_nl` → draft + `[✅ Создать] [✏️ Поправить] [✖️ Отмена]`
  3. Yes → `create_question`, confirm
- В `bot_common/fsm/states.py` добавить `AdminFlow.AWAITING_NL_DESCRIPTION`, `AWAITING_NL_CONFIRMATION`
- Тесты с моком LLM

### #5 — `feat(bot-admin): conversational admin agent replaces rigid fallback`

- `tools/admin_question_tools.py` (new): `list_questions`, `delete_question(id)`, `find_question_by_text(query)`, `create_question(...)`. Каждый оборачивает `services/questions.py` и возвращает LLM-friendly текст
- `bot_admin/handlers/admin_agent.py` (new): langchain agent (LLM + tools). Tone профессионально-тёплый, минимально эмодзи. System prompt + few-shot
- `bot_admin/handlers/fallback.py` (rewrite): делегирует в admin_agent для любого unhandled text
- `bot_admin/__main__.py`: router order — **agent последним** (slash commands / FSM states матчатся первыми)
- Тесты с моком LLM + tools

### #6 — `feat(bot-admin): FSM sticky-state exit hatch`

- В хендлерах FSM text input (e.g. `AWAITING_QUESTION_TEXT`): `_natural_language_exit_check(text) -> bool` — heuristic: нет `|` И звучит как NL → True
- True → `[✖️ Отмена] [↩️ Продолжить]`. Cancel → clear FSM + route text в admin_agent. Continue → re-prompt format
- Тесты

### #7 — `feat(bot-guest): warm finalize UX — progress ping + warm goodbye`

- `bot_guest/handlers/feedback.py::_ask_next_question`: найти где `idx + 1 >= len(qids)` триггерит finalize. ПЕРЕД `_finalize_with_state` отправить «Минутку, собираю всё вместе… 📝» — чтобы пользователь сразу видел отклик.
- `_finalize_session` ([feedback.py:366]): заменить «Спасибо за отзыв! Хорошего дня.» на тёплый: «Спасибо большое! 🙏 Передам владельцу — твой отзыв пойдёт в дело. Хорошего дня! ☀️»
- Сохранить guard `finalize_message_sent` (не дублировать в empty-pool пути)
- Empty-pool ветка уже warm после Phase 2A.5 — verify, не трогать
- Тесты: mock finalize path; assert intermediate message + new goodbye text

## Out of scope

- ❌ Analytics tools (Phase 3)
- ❌ Mini App / HTTP API (Phase 4)
- ❌ Reward / Cmd #4 (Backlog)
- ❌ Pinecone / DB schema migrations (только новые функции в services/questions.py)
- ❌ Изменение natural dialogue / IN_DIALOGUE state (Phase 2A.5 в main; не регрессить)
- ❌ Voice ввод fix (если только не появится конкретный bug)

## Hard rules

1. **Bash discipline:** одна Bash-call = одна команда. НИКАКИХ `&&`, `;`, `|` chaining. Абсолютные пути внутри `telegram-waiter/`. Передавай это правило subagent'ам явно.
2. **Naming:** spawn names = `implementer`, `tester`, `reviewer` (не `lead`/`team-lead`).
3. **Commit-before-next:** каждый logical step → отдельный коммит. НИКАКОГО uncommitted WIP между шагами.
4. **NEVER discard untracked:** `git status` первым; если untracked + tests green → wip-commit, не reset.
5. **Reuse existing:** Whisper wrapper, OpenAI chat, ChatActionSender, `_finalize_session` — as-is.
6. **Архитектурный инвариант:** dialogue → vector, interview → SQL. Soft-delete only.
7. **Reply vs inline keyboard:** #1 был ReplyKeyboardMarkup (persistent), #2-#5 — InlineKeyboardMarkup для per-item действий. Не путать.

## Verification (gate перед финальным отчётом)

1. `uv run pytest -q` — все зелёные (198 + новые)
2. `uv run ruff check .` — clean
3. `uv run mypy .` — clean
4. Reviewer audit (если есть Explore): tone, инвариант, no scope creep, нет регрессии IN_DIALOGUE / IN_INTERVIEW

## Финальный отчёт

В конце сессии:
1. `git log main..HEAD --oneline` — список коммитов на ветке
2. Тесты: было/стало
3. Reviewer verdict (если делал)
4. Deferred / known issues
5. Обнови `current_changes.md` с финальным отчётом (формат как у прошлых сессий)
6. Финальный коммит: `docs: Phase 2A.6 autonomous session — N/7 commits completed`
