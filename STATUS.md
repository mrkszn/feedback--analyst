# STATUS — M1 Refactor

> Live-обновляемый статус-файл. Куратор читает СЮДА, не в SendMessage-поток.
> Все агенты команды обязаны обновлять соответствующий раздел при изменении состояния.

**Last update:** 2026-06-04 11:20 UTC

---

## Phase progress

| Фаза | Статус | SHA | Длительность | Файлов | +/- | Тестов |
|---|---|---|---|---|---|---|
| R1: layered structure | ✅ committed | `fa62669` | ~45 мин | 137 | +957 / -489 | 462 |
| R2: StorageAdapter Protocol | ✅ committed | `64231ac` | ~25 мин | 17 | +1179 / -442 | 462 |
| **R3: template loader + tg-restaurant** | 🟢 gate green, READY TO COMMIT | (awaiting curator) | — | 16 (14 new + pyproject/uv.lock) | — | 475 |
| R4: docs + tg-clinic stub | ⏸ pending | — | — | — | — | — |

**Gate baseline (main = `64231ac`):**
- pytest -q → 462 passed
- ruff check → clean
- ruff format → 140 files formatted
- mypy → Success, 140 source files

---

## R3 — current focus

**Goal:** template loader + извлечение текущего setup как `templates/tg-restaurant/` + `clients/_example/` config.

### Sub-tasks (live — grouped into 4 TaskCreate'ов)

Task IDs in team task list; ⏳ = in_progress, ⛔ = blocked (waiting on dep), ✅ = done.

- [x] ✅ **Task #1 → implementer** — bootstrap package DONE: `core/bootstrap/{__init__,loader,context,__main__,registry}.py`. `load_client(client_dir) -> AppContext`; run() reuses existing entry-point main()s. registry.py = channel→main() lookup (reviewer to confirm not over-engineered).
- [x] ✅ **Task #2 → implementer** — `templates/tg-restaurant/` DONE: config.yaml + prompts/{dialogue,analyze,card}.txt (files-only extraction, prompts.py NOT rewired) + question_seed.json + README.
- [x] ✅ **Task #3 → implementer** — `clients/_example/` DONE: config.yaml + .env.example.
- [x] ✅ **Task #4 → tester** (DONE — gate GREEN post-#5; secret-free smoke passes) — validation gate.
- [x] ✅ **Task #5 → implementer** — load_client secret-free (factory-based lazy adapters). Verified by team-lead (runtime, empty creds → no raise).

**Implementer self-reported gate (pre-tester):** 462 passed, ruff/format/mypy clean, 14 files. Tester re-verifies independently.

**Tester independent gate — FINAL (2026-06-04, post-#5, ALL GREEN):**
- `tests/test_bootstrap_loader.py` — **13 tests pass**. Realigned 3 to the new factory contract (build_storage/vector return the adapter class; AppContext.storage/vector None pre-run, storage_factory/vector_factory hold the classes) + added `test_load_client_is_secret_free` (monkeypatch settings creds to '', assert load returns AppContext, storage None — regression lock for the #5 blocker).
- 🟢 **secret-free smoke PASSES** — `SUPABASE_URL='' SUPABASE_SERVICE_ROLE_KEY='' PINECONE_API_KEY=''` → `load_client(clients/_example)` returns AppContext, storage=None, storage_factory=SupabaseStorage, vector_factory=PineconeVectorStore, NO raise.
- `uv run pytest -q` → **475 passed** (462 baseline + 13 bootstrap), 1 pre-existing JWT warning, no regressions.
- `uv run ruff check .` → All checks passed. `uv run ruff format --check .` → 146 files formatted. `uv run mypy .` → Success, 146 source files.
- Backward-compat entry points (guest_bot / telegram_admin / http_api `__main__`) still import OK after the #5 context.py/loader.py change.
- question_seed.json → valid JSON, 7 entries, all have text/metric_key/expected_type; 4 enum entries carry non-empty enum_values (create_question-compatible).
- CLI `python -m core.bootstrap <bogus-dir>` → fails loud (FileNotFoundError, reaches load_client). ✓
- **Gate verdict: GREEN. #4 completed. R3 ready to commit.**

### Commit plan for curator (R3 — 2 commits per plan, or 1 atomic)

Per REFACTOR_M1_PLAN.md R3 acceptance #7, R3 may be 1 or 2 commits. Suggested split:

**Commit A — bootstrap fundament + dep:**
- `pyproject.toml`, `uv.lock` (pyyaml>=6.0.3)
- `core/bootstrap/{__init__,loader,context,registry,__main__}.py`
- `tests/test_bootstrap_loader.py`
- msg: `refactor(bootstrap): R3 — template loader + config schema + secret-free AppContext`

**Commit B — template + example client extraction:**
- `templates/tg-restaurant/{config.yaml,README.md,question_seed.json,prompts/*.txt}`
- `clients/_example/{config.yaml,.env.example}`
- msg: `refactor(bootstrap): R3 — extract tg-restaurant template + _example client`

(Or one atomic commit covering all 16 files — curator's call.) NOTE: `clients/` is currently untracked and NOT gitignored — `clients/_example/` will be tracked as intended (the committed reference); future real client dirs would be gitignored separately. STATUS.md + docs/REFACTOR_M1_PLAN.md are process docs — curator decides whether to include in the R3 commit or keep separate.

---

## Open questions / decisions for curator

- ✅ **pyyaml dep**: approved + DONE. `pyyaml>=6.0.3` declared in pyproject.toml (line 21), `uv lock --check` passes — implementer already executed `uv add`. No further action.
- ✅ **Design note: prompt extraction scope** (ratified by curator): R3 prompt extraction = files-only, no live load. `core/agent/prompts.py` constants untouched; .txt files are documentation + future-ready override hook. Live override (prompts.py reads template/prompts/*.txt) = separate feature, post-R4 / Phase 5 follow-up.
- ✅ **registry.py vs inline dict** (reviewer verdict: KEEP as-is): team-lead reviewed `core/bootstrap/registry.py`. It reuses the legacy `main()`s (no router/dispatcher duplication — satisfies the thin-wrapper invariant) and the http_api runner has real logic (programmatic `uvicorn.Server`). Inlining would just relocate identical code into context.py. Not over-engineered. No change.
- ✅ **BLOCKER RESOLVED (#5) — `load_client` now secret-free.** Fix verified by team-lead against live files + runtime: `build_storage`/`build_vector` (loader.py:44-59) now return a zero-arg factory (the adapter class), validate type at load, still fail-loud on unknown type; `load_client` builds factories not adapters (loader.py:74-75); `AppContext.storage`/`vector` are `init=False`/default None, populated in `run()` (context.py:27-47). Runtime check with empty SUPABASE/PINECONE creds → `load_client(clients/_example)` returns AppContext, storage=None, factory=SupabaseStorage, NO raise. PineconeVectorStore stays lazy. Contract change is the right design.
- ✅ **3 stale-contract tests realigned (tester, #4) — RESOLVED.** Tester updated the 3 asserts to the new factory contract + added `test_load_client_is_secret_free` regression lock. All green (475 passed).

---

## Recent events (newest first)

- 2026-06-04 11:20 — team-lead: R3 GATE GREEN. Re-verified independently from main loop: secret-free smoke OK, pytest 475 passed, ruff/format/mypy all clean. All 5 tasks completed. Sent curator sign-off. **R3 ready to commit (curator commits from main loop).**
- 2026-06-04 11:08 — team-lead: #5 fix VERIFIED (loader.py factories + AppContext init=False adapters; runtime empty-creds load → no raise). Blocker cleared. Handed tester 3 stale-contract test realigns (their zone) + re-run gate. R3 commit unblocks once #4 flips green.
- 2026-06-04 10:52 — team-lead REVIEW: read bootstrap package. registry.py = KEEP (not over-engineered). Found 🔴 BLOCKER — load_client eagerly builds SupabaseStorage → requires SUPABASE creds at load (verified: SupabaseException on empty creds). Violates acceptance #5 (load must be secret-free). Local pass is a false-green from .env. Sent fix to implementer (lazy adapter construction); held R3 commit + warned tester.
- 2026-06-04 10:40 — team-lead: #1-#3 all completed (14 files, implementer self-gate green). Ratified prompt-extraction = files-only (Phase 5 follow-up for live load). Confirmed pyyaml already in pyproject+lock (uv lock --check ✓). Dispatching tester for #4 (independent gate).
- 2026-06-04 10:24 — team-lead: Task #1 completed (bootstrap package, all 5 files). #2 in_progress (tg-restaurant template). Tester correctly holding #4 (deps not met — coord rule #7).
- 2026-06-04 10:12 — team-lead: 4 tasks created + assigned (impl #1→#2→#3 chained, tester #4). Implementer started on #1 (bootstrap). pyyaml=`uv add` confirmed in task #1.
- 2026-06-04 09:58 — R3 dispatched, team `feat-m1-r3` spawned (curator)
- 2026-06-04 09:58 — Previous team `feat-m1-refactor` disconnected (team-lead-2 unreachable)
- 2026-06-04 ~09:48 — R2 committed `64231ac` (curator, 462 passed)
- 2026-06-04 ~09:40 — R2 implementer flagged 3 deviations (backward-compat db param, get_supabase patch-target retained, data-access Protocol granularity), all ratified by curator
- 2026-06-04 ~09:30 — R1 committed `fa62669` (curator)
- 2026-06-04 ~09:24 — R1 patch-target sweep done (254 string literals across test files)
- 2026-06-04 ~09:18 — R1 implementation done (78 renames, 137 files)

---

## Lessons baked from R1/R2 (apply to R3+)

1. **`pytest --collect-only` ≠ `pytest -q`.** Collect catches import errors; full run catches runtime errors (e.g. string-literal patch targets). Always `pytest -q` before claiming done.
2. **Patch-target sweep covers 4 call forms:** `patch("...")`, `patch.object("...", ...)`, `mocker.patch("...")`, `monkeypatch.setattr("...", ...)`. Import-grep alone misses these.
3. **Backward-compat retention is OK** when it preserves existing tests without forcing massive fixture rewrites. Document the trade-off in commit body.
4. **Curator commits from main loop.** Subagents hit permission denial on `git commit`; don't loop on retries — escalate to curator.
5. **Idle notifications are normal**, not blockers. Don't react to them unless they impact your work.
6. **Stale task-assignment messages can arrive after a task is completed.** Verify live task state before acting on a "start work" message.
7. **Use STATUS.md** for curator communication, not SendMessage spam.
