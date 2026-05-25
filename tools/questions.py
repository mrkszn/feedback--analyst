from typing import Any

from supabase import Client

from services.questions import list_questions


async def get_active_questions(*, db: Client | None = None) -> list[dict[str, Any]]:
    rows = await list_questions(active_only=True, db=db)
    return [
        {
            "id": str(r["id"]),
            "text": r["text"],
            "metric_key": r["metric_key"],
            "expected_type": r["expected_type"],
            "enum_values": r.get("enum_values"),
        }
        for r in rows
    ]
