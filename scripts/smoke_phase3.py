"""Phase 3 analytics smoke — exercises services/analytics against the live
dev DB (Supabase + Pinecone + OpenAI).

Запуск:
    uv run python scripts/smoke_phase3.py

Делает read-only вызовы каждой функции аналитики. Печатает ✅/❌ + краткий
результат (без полного дампа). Empty-DB случай — это OK (нули/пустые
списки), функция считается работающей если не падает с исключением.

Exit code:
    0 — все функции отработали (даже с пустыми данными)
    1 — хотя бы одна упала с exception
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.analytics import (
    aggregate_metric,
    client_profile,
    semantic_search,
    summary_overview,
    topic_histogram,
)


def _truncate(s: str, n: int = 200) -> str:
    return s if len(s) <= n else s[:n] + "…"


async def _check(name: str, coro):
    try:
        result = await coro
        if isinstance(result, list):
            info = f"list[{len(result)}]" + (f" sample={result[0]!r}" if result else " (empty)")
        elif isinstance(result, dict):
            info = f"dict keys={sorted(result.keys())}"
        else:
            info = repr(result)
        print(f"✅ {name:30s} {_truncate(info, 220)}")
        return True
    except Exception as e:
        print(f"❌ {name:30s} {_truncate(repr(e), 220)}")
        return False


async def main() -> int:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    print(f"Window: {month_ago.date()} → {now.date()} (last 30d) + 7d slices\n")

    checks = [
        ("summary_overview(7d)", summary_overview(week_ago, now)),
        ("summary_overview(30d)", summary_overview(month_ago, now)),
        (
            "aggregate_metric(food_quality,30d,day)",
            aggregate_metric("food_quality", month_ago, now, group_by="day"),
        ),
        (
            "aggregate_metric(service,30d,week)",
            aggregate_metric("service", month_ago, now, group_by="week"),
        ),
        ("topic_histogram(30d,all)", topic_histogram(month_ago, now, sentiment_filter=None)),
        (
            "topic_histogram(30d,negative)",
            topic_histogram(month_ago, now, sentiment_filter="negative"),
        ),
        ("semantic_search('качество еды', top_k=5)", semantic_search("качество еды", top_k=5)),
    ]

    results = []
    for name, coro in checks:
        ok = await _check(name, coro)
        results.append(ok)

    # client_profile: использовать реальный client_id из semantic_search,
    # если нашёлся; иначе ожидать LookupError для 0.
    try:
        hits = await semantic_search("еда", top_k=1)
        sample_client = hits[0]["client_id"] if hits else 0
    except Exception:
        sample_client = 0

    if sample_client:
        results.append(
            await _check(f"client_profile({sample_client})", client_profile(sample_client))
        )
    else:
        try:
            await client_profile(0)
            print(f"❌ {'client_profile(0)  # expected LookupError':30s} returned without raising")
            results.append(False)
        except LookupError as e:
            print(f"✅ {'client_profile(0)  # expected LookupError':30s} {e!r}")
            results.append(True)

    print()
    failures = sum(1 for ok in results if not ok)
    total = len(results)
    if failures:
        print(f"❌ {failures}/{total} failed")
        return 1
    print(f"✅ Все {total} analytics-функций отработали (data может быть пустой — это OK).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
