#!/usr/bin/env bash
# Запускает автономную 2-часовую сессию разработки в tmux.
#
# Слои защиты:
#   1) Pre-session git tag    — точка для аварийного отката (`pre-autonomous-<TS>`)
#   2) Isolation branch       — claude работает в ветке `autonomous/<TS>`, не на main
#   3) --permission-mode dontAsk + расширенный allowlist (см. _autonomous_inner.sh)
#   4) trap: settings.local.json восстанавливается на любом выходе
#   5) Hard timeout 2h15m в headless режиме
#
# Использование:
#   ./scripts/run_autonomous.sh --interactive    (рекомендуется)
#   ./scripts/run_autonomous.sh --headless
#
# Управление:
#   tmux attach -t waiter-auto
#   tmux kill-session -t waiter-auto

set -euo pipefail

MODE="${1:-}"
if [[ "$MODE" != "--headless" && "$MODE" != "--interactive" && "$MODE" != "--smoke" && "$MODE" != "--phase-2a" ]]; then
    cat <<EOF
Usage: $0 [--interactive | --headless | --smoke | --phase-2a]
  --interactive  → 2h автономной сессии (generic v1 промт), в tmux
  --headless     → 2h автономной сессии через claude -p, выходит после отчёта
  --smoke        → короткий wet-run (5 мин) для проверки инфры
  --phase-2a     → Phase 2A: orchestrator-промт для 4 команд (Admin Conversational MVP)
EOF
    exit 1
fi

PROJECT_ROOT="/Users/markdekker/Desktop/Need eat bot/telegram-waiter"
case "$MODE" in
    --smoke)
        PROMPT_FILE="$PROJECT_ROOT/scripts/_smoke_prompt.md"
        ;;
    --phase-2a)
        PROMPT_FILE="$PROJECT_ROOT/scripts/phase_2a_prompt.md"
        # Phase 2A — это interactive по природе (4 команды + wind-down + ожидание).
        # Внутрь inner.sh летит MODE=--interactive, чтобы там сработала ветка claude (не -p).
        MODE="--interactive"
        ;;
    *)
        PROMPT_FILE="$PROJECT_ROOT/scripts/autonomous_session.md"
        ;;
esac
INNER_SCRIPT="$PROJECT_ROOT/scripts/_autonomous_inner.sh"
SESSION="waiter-auto"

# --- Sanity ---
[[ -f "$PROMPT_FILE" ]]  || { echo "ERROR: prompt not found at $PROMPT_FILE"; exit 1; }
[[ -x "$INNER_SCRIPT" ]] || chmod +x "$INNER_SCRIPT"
command -v jq   >/dev/null || { echo "ERROR: jq не установлен (brew install jq)"; exit 1; }
command -v tmux >/dev/null || { echo "ERROR: tmux не установлен (brew install tmux)"; exit 1; }

cd "$PROJECT_ROOT"

# --- Git pre-flight ---
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "ERROR: не git-репозиторий"
    exit 1
fi

if ! git diff-index --quiet HEAD -- || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    echo "ERROR: есть незакоммиченные изменения или untracked файлы."
    echo "Состояние:"
    git status --short
    echo
    echo "Закоммить или stash перед автономной сессией:"
    echo "  git add . && git commit -m 'chore: pre-autonomous checkpoint'"
    echo "  # или:  git stash"
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "ERROR: ты сейчас на ветке '$CURRENT_BRANCH', а нужна main."
    echo "Переключись и попробуй снова: git checkout main"
    exit 1
fi

# --- Settings bak check ---
if [[ -f ".claude/settings.local.json.session-bak" ]]; then
    echo "ERROR: settings.local.json.session-bak существует — прошлая сессия не восстановила permissions."
    echo "Восстанови вручную:"
    echo "  mv .claude/settings.local.json.session-bak .claude/settings.local.json"
    exit 1
fi

# --- Создать checkpoint и isolation-ветку ---
SESSION_TS=$(date +%Y%m%d-%H%M)
PRE_TAG="pre-autonomous-$SESSION_TS"
AUTO_BRANCH="autonomous/$SESSION_TS"

# Если случайный тег уже есть (запускали два раза в одну минуту) — отказ
if git rev-parse "$PRE_TAG" >/dev/null 2>&1; then
    echo "ERROR: тег '$PRE_TAG' уже существует. Подожди минуту или удали вручную."
    exit 1
fi
if git show-ref --verify --quiet "refs/heads/$AUTO_BRANCH"; then
    echo "ERROR: ветка '$AUTO_BRANCH' уже существует. Подожди минуту или удали вручную."
    exit 1
fi

git tag "$PRE_TAG"
git checkout -b "$AUTO_BRANCH"

echo
echo ">>> Pre-session checkpoint:"
echo ">>>   tag:    $PRE_TAG  (на main)"
echo ">>>   branch: $AUTO_BRANCH  (текущая; на ней будут коммиты claude'а)"

# --- Собрать session-aware промт (static + dynamic context) ---
LOG_DIR="$PROJECT_ROOT/runs"
mkdir -p "$LOG_DIR"
SESSION_PROMPT="$LOG_DIR/prompt_${SESSION_TS}.md"
LOG_FILE="$LOG_DIR/auto_${SESSION_TS}.log"

cat "$PROMPT_FILE" > "$SESSION_PROMPT"
cat >> "$SESSION_PROMPT" <<EOF

---

## Session-specific context (auto-injected by launcher)

- **Session timestamp:** \`$SESSION_TS\`
- **Working branch:** \`$AUTO_BRANCH\` — ты НЕ на main, твои коммиты идут сюда
- **Pre-session tag:** \`$PRE_TAG\` (метка на main для отката)

В финальном отчёте **обязательно** включи блок:

\`\`\`
Branch:  $AUTO_BRANCH
Pre-tag: $PRE_TAG

После сессии человек выполнит ОДНО из:
  # принять работу:
  git checkout main && git merge --no-ff $AUTO_BRANCH

  # отбросить:
  git checkout main && git branch -D $AUTO_BRANCH && git tag -d $PRE_TAG

  # аварийный сброс main до состояния до сессии:
  git checkout main && git reset --hard $PRE_TAG
\`\`\`
EOF

# --- Прибить старую tmux-сессию ---
tmux kill-session -t "$SESSION" 2>/dev/null || true

# --- Запуск ---
ENV_PREFIX="PROJECT_ROOT='$PROJECT_ROOT' PROMPT_FILE='$SESSION_PROMPT' LOG_FILE='$LOG_FILE' MODE='$MODE' SESSION_BRANCH='$AUTO_BRANCH' PRE_TAG='$PRE_TAG'"

tmux new-session -d -s "$SESSION" -x 220 -y 50 \
    "$ENV_PREFIX bash '$INNER_SCRIPT'"

if [[ "$MODE" == "--interactive" ]]; then
    # Дать claude'у подняться, потом вставить промт
    sleep 5
    tmux load-buffer -b autosess "$SESSION_PROMPT"
    tmux paste-buffer -t "$SESSION" -b autosess
    tmux send-keys -t "$SESSION" Enter
fi

cat <<EOF

>>> Сессия 'waiter-auto' запущена в режиме $MODE.
>>> Промт сессии: $SESSION_PROMPT

Управление:
  tmux attach -t $SESSION       # подключиться (Ctrl+B затем D — отключиться)
  tmux kill-session -t $SESSION # прибить (permissions восстановятся автоматически)

────────────────────────────────────────────────────────────
ПОСЛЕ СЕССИИ — review и merge/discard
────────────────────────────────────────────────────────────

# Посмотреть, что добавлено в ветке:
git log main..$AUTO_BRANCH --oneline
git diff main..$AUTO_BRANCH --stat

# Если ОК — merge в main:
git checkout main
git merge --no-ff $AUTO_BRANCH

# Если не ОК — отбросить:
git checkout main
git branch -D $AUTO_BRANCH
git tag -d $PRE_TAG

# Аварийный сброс (откат main до состояния до сессии):
git checkout main
git reset --hard $PRE_TAG
────────────────────────────────────────────────────────────

EOF

if [[ "$MODE" == "--headless" ]]; then
    echo "Лог: $LOG_FILE"
fi
