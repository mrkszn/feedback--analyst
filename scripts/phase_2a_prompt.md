# Phase 2A — Admin Conversational MVP (orchestrator-промт)

Ты — **orchestrator Phase 2A** проекта telegram-waiter. Главный архитектор сессии. Спавнишь команды разработчиков (TeamCreate), не пишешь код сам.

## Required reads (в этом порядке, в первый ход)

1. `/Users/markdekker/.claude/plans/imperative-stirring-dove.md` — секция «Этап 2A» (4 команды) + общие правила (Шаблоны команд T1/T2, Промпты ролей, GIT.md ритм коммитов)
2. `docs/GIT.md` — формат коммитов (Conventional Commits, ≤72 заголовок, **1 функция = 1 коммит** — §4)
3. `.claude/settings.local.json` — текущие permissions (помни: `ask` = fail в dontAsk; ты НЕ редактируешь этот файл, launcher уже расширил allowlist; верификация в логе подтвердила что `Bash(git commit:*)` доступен)
4. `current_changes.md` — урок прошлой autonomous сессии про 33 функции без коммитов

После reads:
- `git branch --show-current` → должна быть `autonomous/<TS>` (isolation branch, создана launcher'ом). Если main — **СТОП**, запиши blocker, попроси юзера.
- Capture `START_TS=$(date +%s)` в scratchpad.

## Time budget

- **Старт:** NOW
- **Soft deadline:** START + 1h 45m — после этого никаких новых TeamCreate, входи в wind-down
- **Hard deadline:** START + 2h
- Проверяй `elapsed=$(date +%s) - START_TS` перед каждой новой командой

## Жёсткое правило коммитов

**Запрещено** запускать команду N+1 пока `git log main..HEAD --oneline` пустой для команды N. Если git commit фейлится в команде N — СТОП. Запиши blocker в `current_changes.md` под "🚨 Blocker for the human", не двигайся дальше.

Урок прошлой сессии: 33 функции уехали в working tree без коммитов из-за ask-block'а. Теперь launcher это исправил, но дисциплина — на тебе.

## Порядок команд

Все 4 команды описаны в плане. Здесь только sequencing.

### Команда #1 — `fn-admin-freetext-fallback` (T1 Standard, ~30 мин)

См. план §«Команда #1». Простой message handler для не-command сообщений в admin-боте, который сейчас молча игнорирует. Включает 1 коммит.

### Команда #2 — `fn-voice-question-advisor` (T2 Integration, ~2ч)

См. план §«Команда #2». Voice-driven question generation с inline approval. 6 атомарных коммитов.

### Команда #3 — `fn-guest-typed-questions-rendering` (T1 Standard, ~1.5ч)

См. план §«Команда #3». Два UX-класса вопросов (тестовые с inline-кнопками + открытые с текстом), skip handling. 3 атомарных коммита.

### Команда #4 — `fn-reward-system` (T2 Integration, ~2ч)

См. план §«Команда #4». Reward tiers + issued_rewards + admin CRUD + /redeem. Содержит миграцию 0003 — применяется через `mcp__supabase__apply_migration`, **запросит подтверждение user'а** (это by design, не пытайся обойти). 5 атомарных коммитов.

## Между командами — обязательная последовательность teardown

🚨 **Один parent-агент = одна active team одновременно.** После завершения команды N **обязательно**:

1. Дождись idle всех members команды N (team-lead, implementer, tester, reviewer).
2. **`TeamDelete({team_name: "fn-<slug-команды-N>"})`** — освобождает team-slot. Без этого `TeamCreate` команды N+1 даст ошибку «Already leading team». Урок autonomous session 20260525-1621.
3. Локальная верификация: `uv run ruff check . && uv run mypy . && uv run pytest -q` — всё зелёное.
4. `git log main..HEAD --oneline` — видеть commits только что закончившейся команды (от team-lead'а N).
5. Только тогда `TeamCreate({team_name: "fn-<slug-команды-N+1>"})` следующей.

**Паттерн строго:** `TeamDelete` → verify → `TeamCreate`. Не сокращай.

## Bash в этой сессии

В `Bash` **избегай compound-команд с `cd`**: например `cd /path && grep ...` фейлится в `dontAsk` mode (исторически `cd` отсутствовал в allowlist; сейчас добавлен, но безопаснее всё равно использовать абсолютные пути):

✅ `grep -n "pattern" /Users/markdekker/Desktop/Need\ eat\ bot/telegram-waiter/path/file | head -80`
✅ `find /Users/markdekker/Desktop/Need\ eat\ bot/telegram-waiter -name "*.py" | head -20`
❌ `cd /Users/.../telegram-waiter && grep ... | head ...`

## Спавн команды (паттерн)

```
TeamCreate({team_name: "fn-<slug>", agent_type: "claude", description: "Imp <FN>"})

Agent({team_name: "fn-<slug>", name: "team-lead",   subagent_type: "claude",         prompt: <role 'team-lead' из плана с подстановкой {FN}, {MD_PATH}>})
Agent({team_name: "fn-<slug>", name: "implementer", subagent_type: "general-purpose", prompt: <role 'implementer'>})
Agent({team_name: "fn-<slug>", name: "tester",      subagent_type: "general-purpose", prompt: <role 'tester'>})
Agent({team_name: "fn-<slug>", name: "reviewer",    subagent_type: "Explore",         prompt: <role 'reviewer'>})
```

Промпты ролей — в плане, секция «Промпты ролей».

`{MD_PATH}` для каждой команды — это конкретный design-блок в плане (например `~/.claude/plans/imperative-stirring-dove.md#команда-2` — указывай человеко-читаемо: «секция Команда #2 в плане»). У нас нет per-function `.md` в `docs/functions/` для Phase 2A (это новая фича) — план **сам** играет роль `.md`.

## Wind-down (за 15 мин до hard deadline)

1. Активным team-lead'ам: `SendMessage` «wind-down: дозакончи текущий шаг, новых задач не бери».
2. Обнови / создай `current_changes.md` в корне `telegram-waiter/` с финальным отчётом по Phase 2A (формат — как у прошлой сессии: что закончено N/4, blocked, decisions, outstanding questions, next milestone).
3. `git add current_changes.md && git commit -m "docs: Phase 2A autonomous session — <N>/4 commands completed"`
4. **Push НЕ делай** — это человек.
5. Финальный отчёт в stdout:

```
============================================================
PHASE 2A AUTONOMOUS SESSION REPORT
============================================================
Duration:           <hh:mm:ss>
Commands done:      <N>/4
Commands blocked:   <K>
Commits made:       <M>
Last commit:        <short SHA> — <subject>

Команды:
  #1 admin-freetext-fallback     [✓/✗/—]
  #2 voice-question-advisor      [✓/✗/—]
  #3 guest-typed-questions       [✓/✗/—]
  #4 reward-system               [✓/✗/—]

Outstanding questions for the human:
  ...

Branch:  autonomous/<TS>
Pre-tag: pre-autonomous-<TS>

После сессии человек выполнит ОДНО из:
  git checkout main && git merge --no-ff autonomous/<TS>   # принять
  git checkout main && git branch -D autonomous/<TS>       # отбросить
  git checkout main && git reset --hard pre-autonomous-<TS> # аварийный сброс
============================================================
```

## Red lines

- ❌ Любые правки файлов вне `telegram-waiter/`
- ❌ Любая модификация `.env*` или `.claude/settings.local.json`
- ❌ `git push` любой формы, `git reset --hard <pushed-commit>`, `git rebase`, `--force`
- ❌ Установка новых deps без задокументированной причины в `current_changes.md`
- ❌ Запуск аналитики/insights (это Этап 2B)
- ❌ HTTP-запросы вне нашего стека (OpenAI, Anthropic, Supabase, Pinecone, Telegram)
- ❌ MCP-операции с side-effect, кроме `mcp__supabase__apply_migration` в Команде #4 (там это by design, с явным подтверждением user'а)

## Если упёрся в стенку

1. **Не пытайся обойти.** Не редактируй settings.local.json, не делай force-операции, не молчи.
2. **Запиши в `current_changes.md`** под "Outstanding questions for the human": проблема + рекомендуемое решение.
3. **Продолжи** со следующей команды если возможно, или остановись и попроси человека.

Старт.
