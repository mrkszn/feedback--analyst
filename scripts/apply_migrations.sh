#!/usr/bin/env bash
# Apply pending SQL migrations from core/storage/migrations/ to the database
# pointed at by $SUPABASE_DB_URL.
#
# Tracking: applied files are recorded in public.app_migrations (one row per
# filename). Only files not yet recorded are applied, in filename order
# (0001_, 0002_, ...). Each migration runs in a single transaction; the first
# failure aborts the whole run (ON_ERROR_STOP).
#
# Idempotency: every migration uses `create ... if not exists` / `create or
# replace` / `enable row level security`, so even a first run against an
# already-provisioned database only re-asserts existing objects and records
# them — no data is touched. New migrations are the only ones with real effect.
#
# Usage:
#   SUPABASE_DB_URL='postgresql://...' scripts/apply_migrations.sh            # apply
#   SUPABASE_DB_URL='postgresql://...' scripts/apply_migrations.sh --dry-run  # preview
set -euo pipefail

MIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../core/storage/migrations" && pwd)"
: "${SUPABASE_DB_URL:?SUPABASE_DB_URL is required}"
DRY_RUN="${1:-}"

psql_db() { psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 "$@"; }

# Tracking table — created up front so a fresh database bootstraps cleanly.
psql_db -q -c "create table if not exists public.app_migrations (
    filename   text primary key,
    applied_at timestamptz not null default now()
);"

shopt -s nullglob
applied=0
for path in "$MIG_DIR"/[0-9]*.sql; do
  name="$(basename "$path")"
  exists="$(psql_db -tAc "select 1 from public.app_migrations where filename = '${name}'")"
  if [ "$exists" = "1" ]; then
    echo "• skip   ${name} (already applied)"
    continue
  fi
  if [ "$DRY_RUN" = "--dry-run" ]; then
    echo "• would apply ${name}"
    continue
  fi
  echo "• apply  ${name}"
  psql_db -1 -f "$path"
  psql_db -q -c "insert into public.app_migrations (filename) values ('${name}')"
  applied=$((applied + 1))
done

if [ "$DRY_RUN" = "--dry-run" ]; then
  echo "dry-run complete — no changes made"
else
  echo "done — applied ${applied} new migration(s)"
fi
