"""SQLite → Supabase Postgres one-shot migration (Sprint 7.1).

Idempotent and safe:
  • Doesn't touch the SQLite DB. Kept as backup.
  • Creates Postgres tables only if they don't exist.
  • If --reset is passed, DROPs every target table on Postgres first.
  • Refuses to overwrite a non-empty Postgres without --reset or --append.

Usage:
    # Dry-run — print plan + row counts, no writes
    python -m tools.migrate_to_postgres --dry-run

    # First migration (Postgres is empty)
    python -m tools.migrate_to_postgres

    # Re-migrate (DROPs Postgres tables first — destructive)
    python -m tools.migrate_to_postgres --reset

After this runs:
  • SQLite at data/seo.db is unchanged (keep as backup).
  • Postgres at SUPABASE_DATABASE_URL holds an exact copy of every row.
  • Next: refactor app/db.py to use Postgres going forward.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SQLITE_PATH = Path(os.getenv("SEO_DB_PATH", str(ROOT / "data" / "seo.db")))
PG_URL = os.getenv("SUPABASE_DATABASE_URL", "")

# =============================================================================
# Postgres DDL — derived from app/db.py's SQLite schema, translated to Postgres.
# Order matters: parents before children (projects before everything that has
# project_id, even though we don't add FK constraints).
# =============================================================================

PG_SCHEMA: List[Tuple[str, str]] = [
    ("projects", """
        CREATE TABLE IF NOT EXISTS projects (
            id              BIGSERIAL PRIMARY KEY,
            slug            TEXT NOT NULL UNIQUE,
            name            TEXT NOT NULL,
            domain          TEXT NOT NULL,
            target_url      TEXT NOT NULL,
            gsc_site        TEXT DEFAULT '',
            ga4_property_id TEXT DEFAULT '',
            claude_md       TEXT DEFAULT '',
            accent_color    TEXT DEFAULT '#3DDC97',
            status          TEXT NOT NULL DEFAULT 'active',
            is_default      INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects (slug);
        CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
    """),
    ("rank_history", """
        CREATE TABLE IF NOT EXISTS rank_history (
            id            BIGSERIAL PRIMARY KEY,
            ts            TEXT NOT NULL,
            keyword       TEXT NOT NULL,
            domain        TEXT NOT NULL,
            position      INTEGER,
            matched_url   TEXT,
            engine        TEXT NOT NULL DEFAULT 'duckduckgo',
            project_id    INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_rank_keyword_domain ON rank_history (keyword, domain);
        CREATE INDEX IF NOT EXISTS idx_rank_ts ON rank_history (ts);
        CREATE INDEX IF NOT EXISTS idx_rank_history_project_id ON rank_history (project_id);
    """),
    ("schedules", """
        CREATE TABLE IF NOT EXISTS schedules (
            id            BIGSERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            cron          TEXT NOT NULL,
            prompt        TEXT NOT NULL,
            skip_marketer INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL,
            enabled       INTEGER NOT NULL DEFAULT 1,
            project_id    INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_schedules_project_id ON schedules (project_id);
    """),
    ("scheduler_runs", """
        CREATE TABLE IF NOT EXISTS scheduler_runs (
            id            BIGSERIAL PRIMARY KEY,
            schedule_id   INTEGER NOT NULL,
            name          TEXT NOT NULL,
            started_at    TEXT NOT NULL,
            finished_at   TEXT,
            status        TEXT NOT NULL,
            duration_sec  DOUBLE PRECISION,
            report_path   TEXT,
            error_text    TEXT,
            cost_usd      DOUBLE PRECISION,
            input_tokens  INTEGER,
            output_tokens INTEGER,
            project_id    INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_sched_runs_id ON scheduler_runs (schedule_id);
        CREATE INDEX IF NOT EXISTS idx_sched_runs_started ON scheduler_runs (started_at);
        CREATE INDEX IF NOT EXISTS idx_scheduler_runs_project_id ON scheduler_runs (project_id);
    """),
    ("cost_log", """
        CREATE TABLE IF NOT EXISTS cost_log (
            id              BIGSERIAL PRIMARY KEY,
            ts              TEXT NOT NULL,
            agent           TEXT NOT NULL,
            run_id          TEXT,
            model           TEXT NOT NULL,
            input_tokens    INTEGER NOT NULL DEFAULT 0,
            output_tokens   INTEGER NOT NULL DEFAULT 0,
            cost_usd        DOUBLE PRECISION NOT NULL DEFAULT 0,
            prompt_label    TEXT,
            project_id      INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_cost_ts ON cost_log (ts);
        CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_log (agent);
        CREATE INDEX IF NOT EXISTS idx_cost_run ON cost_log (run_id);
        CREATE INDEX IF NOT EXISTS idx_cost_log_project_id ON cost_log (project_id);
    """),
    ("decisions", """
        CREATE TABLE IF NOT EXISTS decisions (
            id             BIGSERIAL PRIMARY KEY,
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            title          TEXT NOT NULL,
            detail         TEXT,
            source_report  TEXT,
            target_url     TEXT,
            target_keyword TEXT,
            effort         TEXT,
            impact         TEXT,
            status         TEXT NOT NULL DEFAULT 'open',
            status_note    TEXT,
            shipped_at     TEXT,
            project_id     INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_project_id ON decisions (project_id);
    """),
    ("outcomes", """
        CREATE TABLE IF NOT EXISTS outcomes (
            id              BIGSERIAL PRIMARY KEY,
            decision_id     INTEGER NOT NULL,
            measured_at     TEXT NOT NULL,
            window_days     INTEGER NOT NULL,
            metric_name     TEXT NOT NULL,
            metric_value    DOUBLE PRECISION,
            note            TEXT,
            project_id      INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_outcomes_project_id ON outcomes (project_id);
    """),
    ("outreach", """
        CREATE TABLE IF NOT EXISTS outreach (
            id              BIGSERIAL PRIMARY KEY,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            prospect_url    TEXT NOT NULL,
            prospect_name   TEXT,
            region          TEXT,
            angle           TEXT,
            pitch_template  TEXT,
            contact_email   TEXT,
            status          TEXT NOT NULL DEFAULT 'queued',
            status_note     TEXT,
            source_report   TEXT,
            contacted_at    TEXT,
            replied_at      TEXT,
            placed_at       TEXT,
            placed_url      TEXT,
            project_id      INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_outreach_project_id ON outreach (project_id);
    """),
    ("content_calendar", """
        CREATE TABLE IF NOT EXISTS content_calendar (
            id              BIGSERIAL PRIMARY KEY,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            title           TEXT NOT NULL,
            target_keyword  TEXT,
            intent          TEXT,
            content_type    TEXT,
            owner           TEXT,
            due_date        TEXT,
            target_url      TEXT,
            word_count      INTEGER,
            outline         TEXT,
            status          TEXT NOT NULL DEFAULT 'idea',
            status_note     TEXT,
            source_report   TEXT,
            publish_date    TEXT,
            project_id      INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_content_calendar_project_id ON content_calendar (project_id);
    """),
    ("aeo_citations", """
        CREATE TABLE IF NOT EXISTS aeo_citations (
            id              BIGSERIAL PRIMARY KEY,
            ts              TEXT NOT NULL,
            query           TEXT NOT NULL,
            engine          TEXT NOT NULL,
            cited           INTEGER NOT NULL DEFAULT 0,
            citation_count  INTEGER DEFAULT 0,
            response_text   TEXT,
            citations_json  TEXT,
            project_id      INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_citations_project_id ON aeo_citations (project_id);
    """),
    ("gsc_snapshots", """
        CREATE TABLE IF NOT EXISTS gsc_snapshots (
            id           BIGSERIAL PRIMARY KEY,
            ts           TEXT NOT NULL,
            site_url     TEXT NOT NULL,
            dimension    TEXT NOT NULL,
            key          TEXT NOT NULL,
            clicks       INTEGER,
            impressions  INTEGER,
            ctr          DOUBLE PRECISION,
            position     DOUBLE PRECISION,
            range_start  TEXT,
            range_end    TEXT,
            project_id   INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_gsc_snapshots_project_id ON gsc_snapshots (project_id);
        CREATE INDEX IF NOT EXISTS idx_gsc_dim_ts ON gsc_snapshots (dimension, ts);
    """),
    ("report_favorites", """
        CREATE TABLE IF NOT EXISTS report_favorites (
            id            BIGSERIAL PRIMARY KEY,
            report_name   TEXT NOT NULL,
            favorited_at  TEXT NOT NULL,
            note          TEXT DEFAULT '',
            project_id    INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_report_favorites_project_id ON report_favorites (project_id);
    """),
    ("app_meta", """
        CREATE TABLE IF NOT EXISTS app_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """),
    ("agent_notes", """
        CREATE TABLE IF NOT EXISTS agent_notes (
            id          BIGSERIAL PRIMARY KEY,
            project_id  INTEGER,
            agent_key   TEXT NOT NULL,
            notes_md    TEXT NOT NULL DEFAULT '',
            updated_at  TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_agent_notes_pid_key
            ON agent_notes (COALESCE(project_id, -1), agent_key);
        CREATE INDEX IF NOT EXISTS idx_agent_notes_pid_key
            ON agent_notes (project_id, agent_key);
    """),
    ("agent_rejections", """
        CREATE TABLE IF NOT EXISTS agent_rejections (
            id           BIGSERIAL PRIMARY KEY,
            project_id   INTEGER,
            agent_key    TEXT NOT NULL,
            report_name  TEXT,
            reason       TEXT NOT NULL,
            rejected_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_agent_rejections_pid_key
            ON agent_rejections (project_id, agent_key);
        CREATE INDEX IF NOT EXISTS idx_agent_rejections_when
            ON agent_rejections (rejected_at);
    """),
]

# Tables NOT to migrate (sqlite-internal stuff)
_SKIP = {"sqlite_sequence"}

# =============================================================================
# Migration
# =============================================================================

def list_sqlite_tables(c: sqlite3.Connection) -> List[str]:
    rows = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in _SKIP]


def list_pg_tables(cur) -> List[str]:
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )
    return [r[0] for r in cur.fetchall()]


def sqlite_columns(c: sqlite3.Connection, table: str) -> List[str]:
    rows = c.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def pg_columns(cur, table: str) -> List[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s "
        "ORDER BY ordinal_position",
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def drop_all(cur, tables: List[str]) -> None:
    for t in tables:
        # CASCADE so we don't have to worry about ordering even without FKs
        cur.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')


def create_schema(cur, dry: bool = False) -> None:
    for name, ddl in PG_SCHEMA:
        if dry:
            print(f"  [dry-run] would CREATE TABLE {name}")
            continue
        cur.execute(ddl)


def copy_table(sql_c: sqlite3.Connection, pg_cur, table: str,
               dry: bool = False, append: bool = False) -> int:
    """Copy every row from SQLite `table` to Postgres `table`.
    Returns the number of rows copied."""
    src_cols = sqlite_columns(sql_c, table)
    if not src_cols:
        return 0

    # In dry-run the tables don't exist yet in Postgres, so we can't compute
    # the intersection — assume every SQLite column maps to a Postgres column.
    # In the real run, fall back to all SQLite columns if Postgres reports
    # none (shouldn't happen but defensive).
    if dry:
        common = src_cols
    else:
        dst_cols = pg_columns(pg_cur, table)
        if not dst_cols:
            print(f"  ⚠ {table}: Postgres table missing — did CREATE TABLE fail?")
            return 0
        common = [c for c in src_cols if c in dst_cols]
        if not common:
            print(f"  ⚠ {table}: no common columns — skipping")
            return 0

    rows = sql_c.execute(
        f"SELECT {','.join(common)} FROM {table}"
    ).fetchall()
    n = len(rows)
    if n == 0:
        return 0
    if dry:
        return n

    if not append:
        # Truncate to keep idempotent on re-runs without --reset
        pg_cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

    placeholders = ", ".join(["%s"] * len(common))
    cols_str = ", ".join(f'"{c}"' for c in common)
    sql = f'INSERT INTO "{table}" ({cols_str}) VALUES ({placeholders})'

    psycopg2.extras.execute_batch(pg_cur, sql, rows, page_size=500)
    return n


def reset_sequences(pg_cur, table: str) -> None:
    """For each BIGSERIAL column, set the sequence past the highest id."""
    pg_cur.execute(
        """
        SELECT c.column_name, pg_get_serial_sequence(quote_ident(t.table_name), c.column_name)
        FROM information_schema.tables t
        JOIN information_schema.columns c
          ON c.table_name = t.table_name AND c.table_schema = t.table_schema
        WHERE t.table_schema = 'public' AND t.table_name = %s
          AND pg_get_serial_sequence(quote_ident(t.table_name), c.column_name) IS NOT NULL
        """,
        (table,),
    )
    for col, seq in pg_cur.fetchall():
        if not seq:
            continue
        pg_cur.execute(f'SELECT COALESCE(MAX("{col}"), 0) FROM "{table}"')
        max_id = pg_cur.fetchone()[0] or 0
        if max_id > 0:
            pg_cur.execute("SELECT setval(%s, %s, true)", (seq, max_id))


def run(args) -> int:
    if not PG_URL:
        print("❌ SUPABASE_DATABASE_URL is not set in .env"); return 1
    if not SQLITE_PATH.exists():
        print(f"❌ SQLite DB not found at {SQLITE_PATH}"); return 1

    print(f"Source: {SQLITE_PATH} ({SQLITE_PATH.stat().st_size:,} bytes)")
    print(f"Target: {PG_URL.split('@')[1].split('/')[0]}")
    print()

    sql_conn = sqlite3.connect(str(SQLITE_PATH))
    sql_conn.row_factory = None  # we want tuples, not dicts, for execute_batch
    pg_conn = psycopg2.connect(PG_URL, sslmode="require", connect_timeout=20)
    pg_conn.autocommit = False

    try:
        pg_cur = pg_conn.cursor()

        # Step 1: figure out what's already on Postgres
        existing = list_pg_tables(pg_cur)
        print(f"Postgres has {len(existing)} existing public table(s): "
              f"{existing or '(none)'}")

        if existing and not args.reset and not args.append and not args.dry_run:
            print()
            print("❌ Postgres already has tables. Refusing to overwrite.")
            print("   • To replace everything: --reset (DROPs all target tables)")
            print("   • To insert without truncating: --append")
            return 1

        if args.reset and not args.dry_run:
            print("⚠ --reset: dropping every target table on Postgres ...")
            drop_all(pg_cur, [t for t, _ in PG_SCHEMA])
            pg_conn.commit()

        # Step 2: create schema
        print("Creating Postgres schema ...")
        create_schema(pg_cur, dry=args.dry_run)
        if not args.dry_run:
            pg_conn.commit()

        # Step 3: copy data table by table, in schema order
        print()
        print(f"{'Table':<22} {'Rows':>8}  Status")
        print("-" * 60)
        total_rows = 0
        sql_tables = set(list_sqlite_tables(sql_conn))
        for table, _ddl in PG_SCHEMA:
            if table not in sql_tables:
                print(f"{table:<22} {'—':>8}  (not in SQLite — fresh table)")
                continue
            n = copy_table(sql_conn, pg_cur, table,
                           dry=args.dry_run, append=args.append)
            total_rows += n
            status = "DRY-RUN" if args.dry_run else "copied"
            print(f"{table:<22} {n:>8}  {status}")
            if not args.dry_run and n > 0:
                reset_sequences(pg_cur, table)

        if args.dry_run:
            print()
            print(f"Dry-run complete. {total_rows} rows would be copied.")
            pg_conn.rollback()
            return 0

        pg_conn.commit()
        print()
        print(f"✅ Migration complete. {total_rows} rows in {len(sql_tables)} table(s).")

        # Step 4: verification
        print()
        print("Verification (SQLite vs Postgres row counts):")
        all_match = True
        for table, _ in PG_SCHEMA:
            if table not in sql_tables:
                continue
            sl = sql_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            pg_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            pg = pg_cur.fetchone()[0]
            ok = "✓" if sl == pg else "✗"
            if sl != pg:
                all_match = False
            print(f"  {ok} {table:<22} sqlite={sl}  postgres={pg}")

        if not all_match:
            print()
            print("⚠ Row counts don't match. Investigate before refactoring db.py.")
            return 1
        print()
        print("All row counts match. SQLite kept intact as backup.")
        return 0
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        pg_conn.close(); sql_conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print plan + row counts, write nothing")
    p.add_argument("--reset", action="store_true",
                   help="DROP every target table on Postgres first (destructive)")
    p.add_argument("--append", action="store_true",
                   help="Insert without truncating existing rows (rare)")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
