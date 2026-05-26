"""HTTP API (Phase 4A) — тонкая обёртка над services/* и agent/*.

bot/ и api/ — два независимых entry points: оба зовут одни и те же services
через прямой Python-import. Никакой бизнес-логики тут нет.
"""
