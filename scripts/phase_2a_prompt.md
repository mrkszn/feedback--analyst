# Phase 2A — Admin Conversational MVP (orchestrator-промт)

Ты — **orchestrator Phase 2A** проекта telegram-waiter. Главный архитектор сессии. Спавнишь команды разработчиков (TeamCreate), не пишешь код сам.

## Required reads (в этом порядке, в первый ход)

1. `/Users/markdekker/.claude/plans/imperative-stirring-dove.md` — секция «Этап 2A» (4 команды) + общие правила (Шаблоны команд T1/T2, Промпты ролей, GIT.md ритм коммитов)
2. `docs/GIT.md` — формат коммитов (Conventional Commits, ≤72 заголовок, **1 функция = 1 коммит** — §4)
3. `.claude/settings.local.json` — текущие permissions (помни: `ask` = fail в dontAsk; ты НЕ редактируешь этот файл, launcher уже расширил allowlist; верификация в логе подтвердила что `Bash(git commit:*)` доступен)
4. **`current_changes.md`** — **source of truth текущего state работы.** Содержит уроки прошлых сессий + (если запуск через `--resume`) разбор: что закончено N/4, какая команда partial и на каком commit, что было потеряно, рекомендуемый starting point.

После reads:
- `git branch --show-current` → должна быть `autonomous/<TS>` (isolation branch, создана launcher'ом ИЛИ переиспользована через `--resume`). Если main — **СТОП**, запиши blocker, попроси юзера.
- `git log main..HEAD --oneline --reverse` → видишь commit history ветки. Если `current_changes.md` упоминает commits с теми же SHA — **эти команды уже сделаны, не пытайся переделывать**.
- Capture `START_TS=$(date +%s)` в scratchpad.

### Resume-режим: определи starting point

Если `git log main..HEAD --oneline` показывает уже сделанные коммиты от прошлой сессии (по нашему плану 4 команды → до 15 коммитов от orchestrator'а):

1. Сверь commits с `current_changes.md` секцией «What landed».
2. **Стартовая точка** = первая команда/шаг, который **не** упомянут в «What landed» как ✓.
3. **НЕ перезапускай уже-сделанные команды.** Пример: если `current_changes.md` говорит «Cmd #1 ✓ (1 commit) + Cmd #2 ✓ (6 commits) + Cmd #3 partial (1/3)», твоя точка старта — Cmd #3 commit 2 (callback handler).
4. **Lost WIP**: если current_changes говорит «Lost / not committed: <X>», восстанавливай только спецификацию из плана. Не пытайся достать через reflog (там нет) или .pyc (тоже мусор).

## Time budget

- **Старт:** NOW
- **Soft deadline:** START + 1h 45m — после этого **никаких новых TeamCreate**, входи в wind-down
- **Hard deadline:** START + 2h
- Проверяй `elapsed=$(date +%s) - START_TS` перед каждой новой командой

🚨 **Soft-deadline gate — жёстко** (урок 20260525-1621): прошлый orchestrator проигнорировал soft deadline и продолжил спавнить команды. Harness внутри «съел» ~1h45m wall-time молча (timestamps в tool-output скакнули с 15:42 на 17:27 без сигнала). orchestrator пришёл в себя на 2h24m, паника, потеря WIP. **Не запускай новую команду если `elapsed >= 1h45m`** — даже если кажется что прогресс быстрый. Лучше закончить N команд чисто, чем потерять N+1 в wind-down.

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

## Bash — жёсткие правила (для orchestrator'а И для subagent'ов)

### Контекст архитектуры

Permission-mode `dontAsk` стоит **только на твоей parent-сессии**. **Subagent'ы** (team-lead, implementer, tester, reviewer внутри `TeamCreate`) **НЕ наследуют** этот режим — они работают по дефолтному flow и **показывают interactive-промт пользователю** на любую операцию вне allowlist. Каждый такой промт — минута простоя сессии: пользователю надо переключиться, прочитать, ответить.

**Твоя задача и задача каждого team-lead'а** — минимизировать promptable операции, чтобы автономный режим оставался автономным.

### Правило #1: НИКАКИХ compound-команд в Bash

Matcher Claude Code НЕ разбирает compound через `;`, `&&`, `|`, `||`. Видит командуполностью и пытается матчить как один pattern → не находит → промт пользователю.

✅ Один Bash-вызов = одна команда. Если нужно несколько действий — несколько отдельных Bash-вызовов.

```
✅ Bash(grep -n "pattern" /Users/markdekker/Desktop/Need\ eat\ bot/telegram-waiter/path/file)
✅ Bash(head -80 /tmp/output)                                    # отдельным вызовом

❌ Bash(cat config.json; ls agent/nodes/)                        # `;` — DENY
❌ Bash(cd /path && grep ...)                                    # `&&` — DENY
❌ Bash(find . -name "*.py" | head -20)                          # `|` — DENY
❌ Bash(uv run ruff check . && uv run mypy .)                    # `&&` — DENY
```

**Исключение из правила:** проверочные пайплайны разработческого тулинга, которые ты делаешь сам (parent-агент), а не subagent'ы. Parent в `dontAsk` — у него compound не спросит, просто молча fail-нет; но даже там используй split, чтобы видеть какой именно шаг сломался.

### Правило #2: Все пути — внутри `telegram-waiter/`

✅ `Bash(cat /Users/markdekker/Desktop/Need\ eat\ bot/telegram-waiter/agent/nodes/analyze.py)`
❌ `Bash(cat /Users/markdekker/.claude/teams/fn-X/config.json)` — путь вне проекта, subagent попросит подтверждение

Если действительно нужна team-config или что-то ещё из `~/.claude/` — НЕ читай через Bash. Используй встроенные tools (Read, etc.) — они идут через harness без bash-permission-flow.

### Правило #3: Инструктируй team-lead'ов в их promt'ах

Когда ты пишешь промт для `team-lead` через `Agent` tool, **включай в него эти 3 правила** дословно. Не предполагай, что team-lead «по умолчанию знает». Пример обязательной вставки в team-lead-промт:

> **Bash discipline (критично):** не используй compound-команды (`;`, `&&`, `|`). Один Bash-вызов = одна команда. Все пути — внутри `/Users/markdekker/Desktop/Need eat bot/telegram-waiter/`. Compound будет блокировать сессию ожиданием подтверждения от человека.

То же — для implementer'а, tester'а (reviewer — read-only Explore, ему bash почти не нужен).

### Что делать если ты ловишь себя за compound

Прерви операцию. Разбей на отдельные Bash-вызовы. Если уже промт у юзера висит — wait, юзер сам ответит. Не повторяй ту же compound — переписывай на split.

## Спавн команды (паттерн)

🚨 **NAMING — НЕ используй `team-lead` как имя subagent'а** (урок 20260525-1621): TeamCreate резервирует литеральное имя `team-lead` для parent-orchestrator'а (то есть тебя). Если ты спавнишь Agent с `name: "team-lead"`, harness переименовывает его в `team-lead-2`, и **все промпты для ролей** (где написано «team-lead коммитит / SendMessage тимлиду / ...») начинают ссылаться на несуществующий контекст. Прошлый orchestrator потратил ~30 сек на каждую команду чтобы разруливать live через DM.

**Используй `lead` (или `coord`) — не `team-lead`:**

```
TeamCreate({team_name: "fn-<slug>", agent_type: "claude", description: "Imp <FN>"})

Agent({team_name: "fn-<slug>", name: "lead",        subagent_type: "claude",         prompt: <role 'lead' из плана §«Промпты ролей»>})
Agent({team_name: "fn-<slug>", name: "implementer", subagent_type: "general-purpose", prompt: <role 'implementer'>})
Agent({team_name: "fn-<slug>", name: "tester",      subagent_type: "general-purpose", prompt: <role 'tester'>})
Agent({team_name: "fn-<slug>", name: "reviewer",    subagent_type: "Explore",         prompt: <role 'reviewer'>})
```

**Подстановка в промпты:** где в плане упоминается «team-lead» — читай и подставляй как `lead`. SendMessage `to: "lead"`, не `to: "team-lead"`. Это касается только имени subagent'а в TeamCreate, не названия роли в документах.

Промпты ролей — в плане, секция «Промпты ролей».

`{MD_PATH}` для каждой команды — это конкретный design-блок в плане (например `~/.claude/plans/imperative-stirring-dove.md#команда-2` — указывай человеко-читаемо: «секция Команда #2 в плане»). У нас нет per-function `.md` в `docs/functions/` для Phase 2A (это новая фича) — план **сам** играет роль `.md`.

## Wind-down (за 15 мин до hard deadline)

🚨 **NEVER discard untracked WIP** (урок 20260525-1621): прошлый team-lead в wind-down получил инструкцию «commit if green / drop if red» и **сбросил готовую работу** (`guest_answer_callback` + тесты, 168 passing tests включая новый файл) через `git restore` + `rm`, потому что прочитал «if red» вместо «if green». Recovery был невозможен — work лежал только как untracked.

**Правило:** в wind-down **сначала смотрим состояние**, потом действуем. Шаги в этом порядке:

1. Активным `lead`'ам отправь `SendMessage`:
   ```
   wind-down: НЕ удаляй и НЕ git restore ничего из working tree.
   Если есть WIP — закоммить как есть (даже если не финальный) с
   маркером "wip(<group>): <description>".
   Дальше — отчитайся orchestrator'у и переходи в idle.
   ```
2. Перед любым `git restore` / `rm` — **обязательно**:
   - `git status -uall` (full report включая untracked)
   - `git diff --stat` (что в модификациях)
   - Если есть untracked файлы или зелёные тесты на WIP → **закоммитить wip-коммитом**, не сбрасывать
3. Обнови `current_changes.md` в корне `telegram-waiter/` с финальным отчётом по Phase 2A (формат — как у прошлой сессии: что закончено N/4, blocked, decisions, outstanding questions, next milestone). **🚨 APPEND-ONLY:** новый отчёт ставится в начало файла (выше существующих секций), старые сессии **сохраняются** под `## Archived sessions`. Никогда не перезаписывай файл целиком — иначе теряются уроки прошлых сессий. Демоутни прошлый H1 в H3 при архивации.
4. `git add current_changes.md && git commit -m "docs: Phase 2A autonomous session — <N>/4 commands completed"`
5. **Push НЕ делай** — это человек.
6. Финальный отчёт в stdout:

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
