#!/usr/bin/env bash
# Inner script — выполняется ВНУТРИ tmux-сессии.
# 1) Бэкапит .claude/settings.local.json
# 2) Расширяет allow на безопасные операции (только то, что нужно автономному
#    режиму помимо текущего allowlist — см. EXTRA_ALLOW ниже).
# 3) Запускает claude с --permission-mode dontAsk.
# 4) При ЛЮБОМ выходе (claude exit / SIGINT / SIGTERM) — восстанавливает settings.
#
# Запускать НЕ напрямую — только через scripts/run_autonomous.sh.

set -euo pipefail

: "${PROJECT_ROOT:?PROJECT_ROOT must be set}"
: "${MODE:?MODE must be set (--headless | --interactive)}"

cd "$PROJECT_ROOT"

SETTINGS=".claude/settings.local.json"
SETTINGS_BAK=".claude/settings.local.json.session-bak"

# -----------------------------------------------------------------------------
# Безопасные расширения allowlist для автономной сессии.
# Что НЕ добавлено намеренно (см. docs/GIT.md, scripts/autonomous_session.md):
#   rm:*           → используй `find ... -delete`
#   git push:*     → push инициирует только человек
#   git reset/checkout/rebase → история main не редактируется
#   supabase CLI   → используй MCP
#   curl/wget/fly/npx/npm  → не нужны
#   mcp__supabase__apply_migration / execute_sql → миграции — решение человека
# -----------------------------------------------------------------------------
declare -a EXTRA_ALLOW=(
    # --- Git ---
    "Bash(git commit:*)"

    # --- Pre-commit ---
    "Bash(pre-commit:*)"

    # --- Утилиты shell (часто нужны в pipelines) ---
    "Bash(cd:*)"
    "Bash(date:*)"
    "Bash(jq:*)"
    "Bash(head:*)"
    "Bash(tail:*)"
    "Bash(wc:*)"
    "Bash(sort:*)"
    "Bash(uniq:*)"
    "Bash(awk:*)"
    "Bash(sed:*)"
    "Bash(xargs:*)"
    "Bash(test:*)"

    # --- Спавн агентов и задач ---
    # TeamCreate создаёт команду; TeamDelete КРИТИЧНО для последовательных команд:
    # один parent-агент = одна active team одновременно, нужен TeamDelete перед
    # созданием следующей. Урок autonomous session 20260525-1621.
    "Agent"
    "TeamCreate"
    "TeamDelete"
    "TaskOutput"
    "TaskStop"

    # --- Supabase MCP — только read-only ---
    "mcp__supabase__list_projects"
    "mcp__supabase__list_tables"
    "mcp__supabase__list_migrations"
    "mcp__supabase__list_extensions"
    "mcp__supabase__list_organizations"
    "mcp__supabase__get_advisors"
    "mcp__supabase__get_logs"
    "mcp__supabase__get_project"
    "mcp__supabase__get_project_url"
    "mcp__supabase__get_organization"
    "mcp__supabase__search_docs"

    # --- Pinecone MCP — только read-only ---
    "mcp__plugin_pinecone_pinecone__list-indexes"
    "mcp__plugin_pinecone_pinecone__describe-index"
    "mcp__plugin_pinecone_pinecone__describe-index-stats"
    "mcp__plugin_pinecone_pinecone__search-docs"
)

# --- Safety: если бэкап уже существует, значит прошлая сессия упала ---
if [[ -f "$SETTINGS_BAK" ]]; then
    echo "ERROR: $SETTINGS_BAK уже существует — предыдущая сессия не восстановила settings."
    echo "Проверь содержимое вручную:"
    echo "  diff $SETTINGS $SETTINGS_BAK"
    echo "Восстановить из бэкапа:  mv $SETTINGS_BAK $SETTINGS"
    exit 1
fi

# --- Backup + expand allowlist ---
cp "$SETTINGS" "$SETTINGS_BAK"

# Превратить bash-массив в JSON array через jq
EXTRA_JSON=$(printf '%s\n' "${EXTRA_ALLOW[@]}" | jq -R . | jq -s .)

# Слить с существующим allow + дедуп + сортировка.
# КРИТИЧНО: в `dontAsk` mode правило в `ask` побеждает над таким же в `allow`.
# Поэтому для каждой extra-permission нужно ТАКЖЕ удалить её из `ask`
# (если она там была), иначе git commit и др. ask-операции продолжат
# фейлиться. Урок autonomous session 20260525-1200 (см. current_changes.md).
jq --argjson extra "$EXTRA_JSON" '
    .permissions.allow = ((.permissions.allow + $extra) | unique | sort)
    | .permissions.ask  = ((.permissions.ask // []) - $extra | unique | sort)
' "$SETTINGS_BAK" > "$SETTINGS"

echo ">>> [autonomous] allowlist расширен на ${#EXTRA_ALLOW[@]} разрешений"
echo ">>> [autonomous] бэкап: $SETTINGS_BAK"
echo ">>> [autonomous] git branch: ${SESSION_BRANCH:-?}"
echo ">>> [autonomous] pre-tag:    ${PRE_TAG:-?}"

# --- Verify: критичные permissions доступны (защита от регрессии swap-логики) ---
# Если что-то пошло не так на swap — лучше упасть СЕЙЧАС, а не на середине сессии
# когда команды агентов натыкаются на permission denied на каждый commit.
_check_perm() {
    local perm="$1"
    if ! jq -e --arg p "$perm" '.permissions.allow | index($p)' "$SETTINGS" >/dev/null; then
        echo "FATAL: '$perm' отсутствует в allow после swap. Восстанавливаю настройки."
        mv "$SETTINGS_BAK" "$SETTINGS"
        exit 1
    fi
    if jq -e --arg p "$perm" '.permissions.ask // [] | index($p)' "$SETTINGS" >/dev/null; then
        echo "FATAL: '$perm' остался в ask после swap (в dontAsk это hard-deny!). Восстанавливаю."
        mv "$SETTINGS_BAK" "$SETTINGS"
        exit 1
    fi
}
_check_perm "Bash(git commit:*)"
_check_perm "Bash(git add:*)"
echo ">>> [autonomous] verify: Bash(git commit:*) ✓ allow, ✗ ask — team-lead'ы смогут коммитить в feature-branch"

# --- Backup ~/.claude/ для защиты от случайных правок globals ---
GLOBAL_CLAUDE_BAK=""
if [[ -d "$HOME/.claude" ]]; then
    GLOBAL_CLAUDE_BAK="$HOME/.claude.autonomous-bak-$(date +%Y%m%d-%H%M%S)"
    cp -R "$HOME/.claude" "$GLOBAL_CLAUDE_BAK"
    echo ">>> [autonomous] backup ~/.claude/ → $GLOBAL_CLAUDE_BAK"
fi

# --- Cleanup on ANY exit ---
on_exit() {
    if [[ -f "$SETTINGS_BAK" ]]; then
        mv "$SETTINGS_BAK" "$SETTINGS"
        echo ">>> [autonomous] permissions восстановлены"
    fi

    # Если ~/.claude/ изменился — НЕ перезаписываем автоматически (опасно),
    # просто предупреждаем человека и оставляем бэкап.
    if [[ -n "$GLOBAL_CLAUDE_BAK" && -d "$GLOBAL_CLAUDE_BAK" ]]; then
        if diff -rq "$HOME/.claude" "$GLOBAL_CLAUDE_BAK" >/dev/null 2>&1; then
            # Нет изменений — бэкап не нужен, удаляем
            rm -rf "$GLOBAL_CLAUDE_BAK"
            echo ">>> [autonomous] ~/.claude/ не изменён, бэкап удалён"
        else
            echo ">>> [autonomous] !!! ~/.claude/ ИЗМЕНЁН за сессию. Бэкап оставлен:"
            echo ">>>     $GLOBAL_CLAUDE_BAK"
            echo ">>> Проверь: diff -rq ~/.claude $GLOBAL_CLAUDE_BAK"
            echo ">>> Восстановить (если правки нежелательны):"
            echo ">>>     rm -rf ~/.claude && mv $GLOBAL_CLAUDE_BAK ~/.claude"
        fi
    fi
}
trap on_exit EXIT INT TERM

# --- Resolve timeout binary (macOS: gtimeout from coreutils; Linux: timeout) ---
# Если ни того, ни другого нет — работаем БЕЗ wall-clock cap, полагаясь на claude --max-turns.
TIMEOUT_BIN=""
TIMEOUT_ARGS=""
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_BIN="gtimeout"
else
    echo ">>> [autonomous] WARNING: ни timeout, ни gtimeout не найден."
    echo ">>> [autonomous]   Install: brew install coreutils (даст gtimeout)"
    echo ">>> [autonomous]   Сейчас работаем БЕЗ wall-clock cap, только --max-turns."
fi

# --- Run claude ---
case "$MODE" in
    --headless)
        : "${PROMPT_FILE:?PROMPT_FILE must be set}"
        : "${LOG_FILE:?LOG_FILE must be set}"
        if [[ -n "$TIMEOUT_BIN" ]]; then
            TIMEOUT_ARGS="--kill-after=10m 2h15m"
            echo ">>> [autonomous] headless claude -p ($TIMEOUT_BIN $TIMEOUT_ARGS, max-turns 800)"
        else
            echo ">>> [autonomous] headless claude -p (без timeout, max-turns 800)"
        fi
        $TIMEOUT_BIN $TIMEOUT_ARGS \
            claude -p "$(cat "$PROMPT_FILE")" \
                --permission-mode dontAsk \
                --max-turns 800 \
                --verbose \
                --output-format stream-json 2>&1 | tee "$LOG_FILE"
        ;;
    --smoke)
        : "${PROMPT_FILE:?PROMPT_FILE must be set}"
        : "${LOG_FILE:?LOG_FILE must be set}"
        if [[ -n "$TIMEOUT_BIN" ]]; then
            TIMEOUT_ARGS="--kill-after=1m 6m"
            echo ">>> [smoke] claude -p ($TIMEOUT_BIN $TIMEOUT_ARGS, max-turns 30)"
        else
            echo ">>> [smoke] claude -p (без timeout, max-turns 30)"
        fi
        $TIMEOUT_BIN $TIMEOUT_ARGS \
            claude -p "$(cat "$PROMPT_FILE")" \
                --permission-mode dontAsk \
                --max-turns 30 \
                --verbose \
                --output-format stream-json 2>&1 | tee "$LOG_FILE"
        ;;
    --interactive)
        echo ">>> [autonomous] стартую интерактивный claude (dontAsk mode)"
        # Промт вставит outer-скрипт через tmux paste-buffer после `sleep 5`
        # wall-clock cap у interactive нет — рассчитываем на self-discipline из промта
        claude --permission-mode dontAsk
        ;;
    *)
        echo "ERROR: unknown MODE='$MODE'"
        exit 1
        ;;
esac
