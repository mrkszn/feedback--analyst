"""HTTP API (Phase 4A) — тонкая обёртка над core/services/* и core/agent/*.

channels/* и presentations/* — независимые entry points: оба зовут одни и те же
core/services через прямой Python-import. Никакой бизнес-логики тут нет.
"""
