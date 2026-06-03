#!/usr/bin/env bash
# Watcher для автономной tmux-сессии 'waiter-auto'.
#
# Использование:
#   ./scripts/watch_autonomous.sh           # одноразовый снимок
#   ./scripts/watch_autonomous.sh --loop    # обновлять каждые 30 сек
#
# Если хочешь полный live-view — лучше:
#   tmux attach -t waiter-auto

set -euo pipefail

SESSION="waiter-auto"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOOP="${1:-}"

snapshot() {
    cd "$PROJECT_ROOT"
    # Очистить экран (graceful если TERM не задан, например в pipe)
    if [[ -t 1 && -n "${TERM:-}" ]]; then
        clear
    else
        printf "\n\n"
    fi
    echo "════════════════════════════════════════════════════════════════════════"
    echo " AUTONOMOUS SESSION WATCHER — $(date +%H:%M:%S)"
    echo "════════════════════════════════════════════════════════════════════════"

    # Tmux session alive?
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "❌ tmux session '$SESSION' НЕ РАБОТАЕТ"
        echo "   Возможно завершилась штатно или была убита."
        return
    fi
    echo "✅ tmux session жива"

    # Branch
    BRANCH=$(git branch --list 'autonomous/*' --format='%(refname:short)' | head -1)
    if [[ -z "$BRANCH" ]]; then
        echo "⚠️  ветка autonomous/* не найдена"
    else
        echo "🌿 Ветка: $BRANCH"
        AHEAD=$(git rev-list --count "main..$BRANCH" 2>/dev/null || echo "0")
        echo "📊 Коммитов сверх main: $AHEAD"
    fi

    # Recent commits
    echo ""
    echo "── Последние коммиты в ветке ─────────────────────────────────"
    if [[ -n "$BRANCH" ]]; then
        git log "main..$BRANCH" --oneline -10 2>/dev/null || echo "(пока нет)"
    fi

    # Latest pane content (last 30 lines)
    echo ""
    echo "── Последние 30 строк tmux pane ──────────────────────────────"
    tmux capture-pane -t "$SESSION" -p | tail -30

    # Check for final report
    PANE_ALL=$(tmux capture-pane -t "$SESSION" -p -S -)
    if echo "$PANE_ALL" | grep -q "AUTONOMOUS SESSION REPORT"; then
        echo ""
        echo "════════════════════════════════════════════════════════════════════════"
        echo "🎉 ФИНАЛЬНЫЙ ОТЧЁТ ОБНАРУЖЕН — агент завершил основную работу"
        echo "════════════════════════════════════════════════════════════════════════"
    fi
}

if [[ "$LOOP" == "--loop" ]]; then
    while true; do
        snapshot
        echo ""
        echo "(обновление через 30 сек, Ctrl+C для выхода)"
        sleep 30
    done
else
    snapshot
fi
