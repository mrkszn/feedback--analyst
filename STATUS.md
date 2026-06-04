# STATUS — M1 Refactor

> Live-обновляемый статус-файл. Куратор читает СЮДА, не в SendMessage-поток.
> Все агенты команды обязаны обновлять соответствующий раздел при изменении состояния.

**Last update:** 2026-06-04 12:16 UTC

---

## Phase progress

| Фаза | Статус | SHA | Длительность | Файлов | +/- | Тестов |
|---|---|---|---|---|---|---|
| R1: layered structure | ✅ committed | `fa62669` | ~45 мин | 137 | +957 / -489 | 462 |
| R2: StorageAdapter Protocol | ✅ committed | `64231ac` | ~25 мин | 17 | +1179 / -442 | 462 |
| R3: template loader + tg-restaurant | ✅ committed | `6c20b70` | ~85 мин | 18 (15 new + pyproject/uv.lock/plan+status) | +746 / -0 | 475 |
| **R4: docs + tg-clinic stub** | 🟢 gate green, READY TO COMMIT | (awaiting curator) | — | 8 (3 docs + README + tg-clinic ×4 files) | — | 475 |

**Gate baseline (main = `64231ac`):**
- pytest -q → 462 passed
- ruff check → clean
- ruff format → 140 files formatted
- mypy → Success, 140 source files

---

## R4 — current focus

**Goal:** finalize M1 — architecture docs + onboarding/template-authoring guides + `tg-clinic` template stub (extraction proof) + root README. Pure docs + one template stub; no production-code changes, no new tests.

### Sub-tasks (live — 5 TaskCreate'ов)

Task IDs in team task list; ⏳ = in_progress, ⛔ = blocked, ✅ = done.

- [x] ✅ **R4 #1 → implementer** — `docs/ARCHITECTURE.md` DONE (layer diagram verified vs tree, what-changes table, R2 storage boundary, data flow, module inventory, R3 bootstrap flow, commit links, sibling-doc cross-links).
- [x] ✅ **R4 #2 → implementer** — `docs/ONBOARDING_CLIENT.md` + `docs/TEMPLATE_AUTHORING.md` DONE. _example forward-ref now satisfied.
- [x] ✅ **R4 #3 → implementer** — `templates/tg-clinic/` DONE: config.yaml (schema byte-identical to tg-restaurant) + prompts/{dialogue,analyze,card}.txt (clinic tone: calm, tactful, privacy-aware; placeholder kept as `{restaurant_context}` VERBATIM — final decision: forward-compatible with the post-R4 live-override builder, which fills `{restaurant_context}`; a rename would silently break that future fill) + question_seed.json (7 clinic Qs: wait_time, staff_attentiveness, cleanliness, explanation_clarity, nps, price_value, improvement_wish) + README. Implementer self-proved secret-free bootstrap load.
- [x] ✅ **R4 #4 → implementer** — root `README.md` DONE (created; M1 modular-architecture section + doc links).
- [x] ✅ **R4 #5 → tester** (DONE — gate GREEN) — validation gate. Placeholder diffs = informational. Extraction proof via TMP DIR. pytest stayed 475.

**Implementer self-gate (pre-tester):** pytest 475 passed (unchanged — docs/templates only), ruff clean, mypy 146 clean.

**Tester independent gate — R4 FINAL (2026-06-04, ALL GREEN):**
- All 10 deliverables exist + non-empty: docs/ARCHITECTURE.md (9.1k), ONBOARDING_CLIENT.md (4.0k), TEMPLATE_AUTHORING.md (5.3k), README.md (2.7k), templates/tg-clinic/{config.yaml, prompts/{dialogue,analyze,card}.txt, question_seed.json, README.md}.
- tg-clinic integrity: config top-level keys IDENTICAL to tg-restaurant (channels, name, presentations, prompts, question_seed, storage, version). question_seed.json valid JSON, 7 entries (wait_time, staff_attentiveness, cleanliness, explanation_clarity, nps, price_value, improvement_wish), all have text/metric_key/expected_type; 4 enum entries carry non-empty enum_values.
- 🟢 EXTRACTION PROOF: tmp-dir client (`template: tg-clinic`, no repo footprint) + empty creds → `load_client` returns AppContext, template_dir=tg-clinic, storage=None, channels/presentations populated. Proves R3 bootstrap extracts to a 2nd industry template. tmp cleaned up.
- Placeholder check (INFORMATIONAL): tg-clinic prompts use `{restaurant_context}` (implementer kept verbatim) — same token as tg-restaurant, braces balanced, no typo-tokens. Cosmetically odd name in a clinic template but harmless (prompts not live-loaded, R3 files-only). Not a blocker.
- Regression: `uv run pytest -q` → **475 passed** (exactly unchanged — docs-only phase added no tests), 1 pre-existing JWT warning. `uv run ruff check .` → clean. `uv run mypy .` → Success 146 files (unchanged → no .py added). `uv run ruff format --check .` → 146 files formatted.
- Markdown link sanity: all relative links across the 5 new docs resolve to existing files. ✓
- 🧹 Did NOT touch stray untracked `clients/_smoke_clinic/` and did not depend on it — used my own tmp dir.
- **Gate verdict: GREEN. #10 completed. R4 ready to commit (exclude clients/_smoke_clinic/ from the commit).**
- **Team-lead re-verified independently from main loop (12:16):** tg-clinic extraction proof OK (tmp client, empty creds → AppContext), pytest 475 passed, ruff clean, mypy 146 clean, question_seed 7 valid entries, `in_memory` adapter cited in ARCHITECTURE.md confirmed real. Matches tester numbers exactly.

### Commit plan for curator (R4 — ONE atomic commit per plan)
- Stage: `docs/ARCHITECTURE.md`, `docs/ONBOARDING_CLIENT.md`, `docs/TEMPLATE_AUTHORING.md`, `README.md`, `templates/tg-clinic/` (config.yaml + prompts/{dialogue,analyze,card}.txt + question_seed.json + README.md).
- msg: `docs(architecture): R4 — M1 architecture docs + tg-clinic template stub`
- ⚠️ EXCLUDE stray untracked `clients/_smoke_clinic/` (don't `git add`, or delete). STATUS.md + docs/REFACTOR_M1_PLAN.md = process docs — curator's call whether to fold into this commit.

🧹 **CLEANUP for curator (R4 commit):** implementer left a stray untracked `clients/_smoke_clinic/config.yaml` (throwaway used to prove tg-clinic loads). It is NOT an R4 deliverable. Both implementer and team-lead hit permission-denial on `rm` (deletion needs main-loop approval). **Action: curator delete `clients/_smoke_clinic/` OR simply don't `git add` it** (it's untracked, so excluding it keeps the R4 commit clean). Real R4 deliverable in clients/ = none; only docs/ + templates/tg-clinic/ + README.md.

**R3 archived (committed `6c20b70`):** bootstrap package + tg-restaurant template + _example client + secret-free loader fix (#5). Final gate 475 passed, ruff/format/mypy clean. One blocker found+fixed (eager SupabaseStorage → factory-based lazy adapters). Detail in git history + "Open questions" ratifications below.

---

## Open questions / decisions for curator

- ✅ **pyyaml dep**: approved + DONE. `pyyaml>=6.0.3` declared in pyproject.toml (line 21), `uv lock --check` passes — implementer already executed `uv add`. No further action.
- ✅ **Design note: prompt extraction scope** (ratified by curator): R3 prompt extraction = files-only, no live load. `core/agent/prompts.py` constants untouched; .txt files are documentation + future-ready override hook. Live override (prompts.py reads template/prompts/*.txt) = separate feature, post-R4 / Phase 5 follow-up.
- ✅ **registry.py vs inline dict** (reviewer verdict: KEEP as-is): team-lead reviewed `core/bootstrap/registry.py`. It reuses the legacy `main()`s (no router/dispatcher duplication — satisfies the thin-wrapper invariant) and the http_api runner has real logic (programmatic `uvicorn.Server`). Inlining would just relocate identical code into context.py. Not over-engineered. No change.
- ✅ **BLOCKER RESOLVED (#5) — `load_client` now secret-free.** Fix verified by team-lead against live files + runtime: `build_storage`/`build_vector` (loader.py:44-59) now return a zero-arg factory (the adapter class), validate type at load, still fail-loud on unknown type; `load_client` builds factories not adapters (loader.py:74-75); `AppContext.storage`/`vector` are `init=False`/default None, populated in `run()` (context.py:27-47). Runtime check with empty SUPABASE/PINECONE creds → `load_client(clients/_example)` returns AppContext, storage=None, factory=SupabaseStorage, NO raise. PineconeVectorStore stays lazy. Contract change is the right design.
- ✅ **3 stale-contract tests realigned (tester, #4) — RESOLVED.** Tester updated the 3 asserts to the new factory contract + added `test_load_client_is_secret_free` regression lock. All green (475 passed).

---

## Recent events (newest first)

- 2026-06-04 12:16 — team-lead: R4 GATE GREEN. Tester #10 completed + team-lead re-verified from main loop (tg-clinic extraction proof, 475 passed, ruff/mypy clean). All 5 R4 tasks done. Commit plan posted. Sent curator sign-off. **R4 ready to commit (1 atomic, exclude _smoke_clinic).** After commit → final review + team closure.
- 2026-06-04 12:02 — team-lead: ALL R4 implementer tasks (#6-#9) done, self-gate green (475 passed, ruff/mypy clean). Dispatching tester for #10 gate. 🧹 Flagged stray untracked `clients/_smoke_clinic/` for curator cleanup (rm denied to subagents; exclude from commit or delete).
- 2026-06-04 11:50 — team-lead: R4 #6 (ARCHITECTURE.md) + #7 (ONBOARDING + TEMPLATE_AUTHORING) done, grounded in real tree/code. #8 (tg-clinic) in progress, #9 (README) next. Corrected #8: {clinic_context} rename OK (template .txt not live-loaded — grep core/agent/ = 0 refs). Extraction proof = tmp-dir, no committed _example_clinic.
- 2026-06-04 11:35 — team-lead: R3 committed `6c20b70` (curator). **GO R4.** 5 tasks created (4 docs/template → impl, 1 gate → tester). R4 = pure docs + tg-clinic stub, no prod-code/test changes. Dispatching implementer.
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
