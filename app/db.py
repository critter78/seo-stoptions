"""Persistence layer for the SEO crew (Sprint 7 — hybrid backend).

Two backends:
  • **SQLite** (default) — all per-project data: rank_history, decisions, costs,
    schedules, AEO citations, etc. Local file at data/seo.db.
  • **Postgres** (when SUPABASE_DATABASE_URL is set) — the `projects` table
    only. Lives in Supabase so the Next.js admin at critterlabs.io/mgmt can
    read the project list and link into each project's Streamlit dashboard.

Project helpers (list_projects / get_project / add_project / update_project /
archive_project / set_default_project) auto-route to Postgres when available,
falling back to SQLite for local dev / installs without Supabase. Every other
function keeps using SQLite — same code path it always had.
"""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("SEO_DB_PATH", str(DATA_DIR / "seo.db")))

# --- Postgres backend (lazy-imported; only loaded if SUPABASE_DATABASE_URL set) ---
SUPABASE_DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL", "")
_USE_PG_FOR_PROJECTS = bool(SUPABASE_DATABASE_URL)


@contextmanager
def _pg_conn():
    """Yield a psycopg2 connection to the Supabase Postgres pooler.

    Used only by the project-table helpers. Raises a clear error if the
    driver isn't installed or the URL is missing.
    """
    if not SUPABASE_DATABASE_URL:
        raise RuntimeError(
            "SUPABASE_DATABASE_URL is not set. Either add it to .env or call "
            "the SQLite-only path of this helper."
        )
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as e:
        raise RuntimeError(
            "psycopg2 is required for Postgres backend. "
            "Run: pip install psycopg2-binary"
        ) from e
    c = psycopg2.connect(
        SUPABASE_DATABASE_URL, sslmode="require", connect_timeout=15,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS rank_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    keyword       TEXT NOT NULL,
    domain        TEXT NOT NULL,
    position      INTEGER,
    matched_url   TEXT,
    engine        TEXT NOT NULL DEFAULT 'duckduckgo'
);
CREATE INDEX IF NOT EXISTS idx_rank_keyword_domain ON rank_history (keyword, domain);
CREATE INDEX IF NOT EXISTS idx_rank_ts ON rank_history (ts);

CREATE TABLE IF NOT EXISTS schedules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    cron          TEXT NOT NULL,
    prompt        TEXT NOT NULL,
    skip_marketer INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS scheduler_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id   INTEGER NOT NULL,
    name          TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL,           -- running | success | error
    duration_sec  REAL,
    report_path   TEXT,
    error_text    TEXT,
    cost_usd      REAL,
    input_tokens  INTEGER,
    output_tokens INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sched_runs_id ON scheduler_runs (schedule_id);
CREATE INDEX IF NOT EXISTS idx_sched_runs_started ON scheduler_runs (started_at);

CREATE TABLE IF NOT EXISTS cost_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    agent           TEXT NOT NULL,        -- researcher | analyst | seo_marketer | pm | adhoc
    run_id          TEXT,                  -- groups calls from the same crew run
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        REAL NOT NULL DEFAULT 0,
    prompt_label    TEXT
);
CREATE INDEX IF NOT EXISTS idx_cost_ts ON cost_log (ts);
CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_log (agent);
CREATE INDEX IF NOT EXISTS idx_cost_run ON cost_log (run_id);

CREATE TABLE IF NOT EXISTS decisions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    title          TEXT NOT NULL,         -- short descriptive title
    detail         TEXT,
    source_report  TEXT,
    target_url     TEXT,
    target_keyword TEXT,
    effort         TEXT,                  -- S | M | L
    impact         TEXT,                  -- *, **, ***
    status         TEXT NOT NULL,         -- open | in_progress | done | wontfix | snoozed
    status_note    TEXT,
    shipped_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions (status);

CREATE TABLE IF NOT EXISTS outcomes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id    INTEGER NOT NULL,
    measured_at    TEXT NOT NULL,
    metric         TEXT NOT NULL,         -- rank | clicks | impressions | ctr | position | conversions
    before_value   REAL,
    after_value    REAL,
    delta          REAL,
    window_days    INTEGER,               -- 14 or 28
    note           TEXT,
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);
CREATE INDEX IF NOT EXISTS idx_outcomes_decision ON outcomes (decision_id);

CREATE TABLE IF NOT EXISTS content_calendar (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    title          TEXT NOT NULL,
    target_keyword TEXT,
    intent         TEXT,                   -- informational | commercial | navigational | transactional
    content_type   TEXT,                   -- blog | landing | guide | tool | comparison | listicle
    owner          TEXT,
    due_date       TEXT,
    publish_date   TEXT,
    target_url     TEXT,
    word_count     INTEGER,
    outline        TEXT,
    status         TEXT NOT NULL,          -- idea | brief | drafting | review | scheduled | published | archived
    status_note    TEXT,
    source_report  TEXT
);
CREATE INDEX IF NOT EXISTS idx_cal_status ON content_calendar (status);
CREATE INDEX IF NOT EXISTS idx_cal_due ON content_calendar (due_date);

CREATE TABLE IF NOT EXISTS aeo_citations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    query          TEXT NOT NULL,
    engine         TEXT NOT NULL,          -- claude | gemini | perplexity | chatgpt | google_ai_overview
    cited          INTEGER NOT NULL,       -- 0/1
    citation_count INTEGER,                -- N times the domain was cited
    response_text  TEXT,
    citations_json TEXT                    -- JSON list of source URLs
);
CREATE INDEX IF NOT EXISTS idx_aeo_query ON aeo_citations (query);
CREATE INDEX IF NOT EXISTS idx_aeo_engine ON aeo_citations (engine);
CREATE INDEX IF NOT EXISTS idx_aeo_ts ON aeo_citations (ts);

CREATE TABLE IF NOT EXISTS report_favorites (
    report_name    TEXT PRIMARY KEY,
    favorited_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outreach (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    prospect_url    TEXT NOT NULL,
    prospect_name   TEXT,
    region          TEXT,
    angle           TEXT,
    pitch_template  TEXT,
    contact_email   TEXT,
    status          TEXT NOT NULL,        -- queued | contacted | no_reply | replied | placed | declined
    status_note     TEXT,
    contacted_at    TEXT,
    replied_at      TEXT,
    placed_at       TEXT,
    placed_url      TEXT,
    source_report   TEXT
);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach (status);
CREATE INDEX IF NOT EXISTS idx_outreach_url ON outreach (prospect_url);

CREATE TABLE IF NOT EXISTS gsc_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,           -- when we pulled this snapshot
    site_url      TEXT NOT NULL,
    dimension     TEXT NOT NULL,           -- query | page | country | device
    key           TEXT NOT NULL,           -- the query/page/country/device value
    clicks        INTEGER,
    impressions   INTEGER,
    ctr           REAL,
    position      REAL,
    range_start   TEXT NOT NULL,
    range_end     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gsc_dim_key ON gsc_snapshots (dimension, key);
CREATE INDEX IF NOT EXISTS idx_gsc_ts ON gsc_snapshots (ts);
CREATE INDEX IF NOT EXISTS idx_gsc_site ON gsc_snapshots (site_url);
"""


@contextmanager
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript(SCHEMA)
    # Sprint 5: idempotent multi-project migration runs after base schema.
    _ensure_projects_schema()
    _migrate_add_project_id_columns()
    _seed_default_project_if_empty()


# =============================================================================
# Sprint 5 — Multi-project / multi-domain support
# =============================================================================
#
# Adds a `projects` table (one row per client / brand / domain) and a nullable
# `project_id` foreign key on every existing scoped table. Old single-project
# installs migrate cleanly: all NULL rows get backfilled to the seeded default
# project (`stoptions`).
#
# The "active project" is held in Streamlit session state (key:
# `active_project_id`). Helpers fall back to the default project when not set,
# so background tasks (cron, agent calls) that don't have session state still
# work correctly.

PROJECTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,        -- url-safe: 'stoptions'
    name            TEXT NOT NULL,                -- display: 'Stoptions.ai'
    domain          TEXT NOT NULL,                -- 'stoptions.ai'
    target_url      TEXT NOT NULL,                -- 'https://stoptions.ai/'
    gsc_site        TEXT DEFAULT '',              -- 'sc-domain:stoptions.ai'
    ga4_property_id TEXT DEFAULT '',              -- '538041737'
    claude_md       TEXT DEFAULT '',              -- per-project context override
    accent_color    TEXT DEFAULT '#3DDC97',       -- brand accent for future per-project theming
    status          TEXT NOT NULL DEFAULT 'active', -- active | archived
    is_default      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects (slug);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
"""

# Every table that holds per-project data. project_id is added as nullable
# during migration; rows with NULL get backfilled to the default project id.
_SCOPED_TABLES = [
    "rank_history",
    "schedules",
    "scheduler_runs",
    "cost_log",
    "decisions",
    "outcomes",
    "outreach",
    "content_calendar",
    "aeo_citations",
    "gsc_snapshots",
    "report_favorites",
]


def _ensure_projects_schema() -> None:
    with conn() as c:
        c.executescript(PROJECTS_SCHEMA)
    _ensure_learning_schema()
    _ensure_reports_pg_schema()


# =============================================================================
# Reports → Postgres (read by critterlabs.io Next.js admin)
# =============================================================================
# Cloud-deployed Streamlit's disk is ephemeral — markdown reports written to
# /reports/ vanish whenever the container restarts. Mirroring them to Supabase
# Postgres gives them a permanent home AND lets the Next.js admin read them
# in the Peek modal / Reports lens.

_REPORTS_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id            BIGSERIAL PRIMARY KEY,
    project_slug  TEXT NOT NULL,
    filename      TEXT NOT NULL,
    title         TEXT,
    body          TEXT NOT NULL,
    template      TEXT,
    author        TEXT,
    health_score  INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_project_slug ON reports (project_slug);
CREATE INDEX IF NOT EXISTS idx_reports_created_at  ON reports (created_at DESC);

CREATE TABLE IF NOT EXISTS cost_log (
    id              BIGSERIAL PRIMARY KEY,
    project_slug    TEXT,
    agent           TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10, 6) NOT NULL DEFAULT 0,
    run_id          TEXT,
    prompt_label    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cost_log_project_slug ON cost_log (project_slug);
CREATE INDEX IF NOT EXISTS idx_cost_log_created_at  ON cost_log (created_at DESC);
"""


def _ensure_reports_pg_schema() -> None:
    """Idempotent. No-ops if SUPABASE_DATABASE_URL isn't set (local-only dev)."""
    if not _USE_PG_FOR_PROJECTS:
        return
    try:
        with _pg_conn() as c:
            with c.cursor() as cur:
                cur.execute(_REPORTS_PG_SCHEMA)
    except Exception as e:
        # Don't crash the app if Postgres is unreachable at boot.
        print(f"[reports/cost schema] skipped: {e}")


def save_cost_to_pg(
    project_slug: str | None,
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    run_id: str = "",
    prompt_label: str = "",
) -> None:
    """Mirror a single cost_log entry to Postgres. Best-effort — failures
    are logged but never interrupt the SQLite write that already happened."""
    if not _USE_PG_FOR_PROJECTS:
        return
    try:
        with _pg_conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cost_log
                        (project_slug, agent, model, input_tokens, output_tokens,
                         cost_usd, run_id, prompt_label)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (project_slug, agent, model, input_tokens, output_tokens,
                     cost_usd, run_id, prompt_label),
                )
    except Exception as e:
        print(f"[save_cost_to_pg] {agent}/{model}: {e}")


def save_report_to_pg(
    project_slug: str,
    filename: str,
    body: str,
    title: str | None = None,
    template: str | None = None,
    author: str | None = None,
    health_score: int | None = None,
) -> None:
    """Persist a generated report's markdown to Supabase so the Next.js admin
    can render it. No-ops if Postgres isn't configured. Best-effort — any
    failure is logged but does not interrupt the caller."""
    if not _USE_PG_FOR_PROJECTS:
        return
    try:
        with _pg_conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reports
                        (project_slug, filename, title, body, template, author, health_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (project_slug, filename, title, body, template, author, health_score),
                )
    except Exception as e:
        print(f"[save_report_to_pg] {filename}: {e}")


# Sprint 6 — Smarter-over-time wiring: per-agent notes, rejection log,
# extended favorites for the few-shot vault.
LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER,
    agent_key   TEXT NOT NULL,
    notes_md    TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL,
    UNIQUE (project_id, agent_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_notes_pid_key
    ON agent_notes (project_id, agent_key);

CREATE TABLE IF NOT EXISTS agent_rejections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
"""


def _ensure_learning_schema() -> None:
    with conn() as c:
        c.executescript(LEARNING_SCHEMA)
        # Add 'note' column to report_favorites for the few-shot vault
        # (why is this report a good reference). Idempotent.
        if _table_exists(c, "report_favorites") and not _column_exists(
            c, "report_favorites", "note"
        ):
            c.execute("ALTER TABLE report_favorites ADD COLUMN note TEXT DEFAULT ''")


def _table_exists(c: sqlite3.Connection, name: str) -> bool:
    row = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _column_exists(c: sqlite3.Connection, table: str, col: str) -> bool:
    rows = c.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)


def _migrate_add_project_id_columns() -> None:
    """Idempotently add `project_id INTEGER` to every scoped table that lacks it."""
    with conn() as c:
        for table in _SCOPED_TABLES:
            if not _table_exists(c, table):
                continue
            if _column_exists(c, table, "project_id"):
                continue
            c.execute(f"ALTER TABLE {table} ADD COLUMN project_id INTEGER")
            c.execute(
                f"CREATE INDEX IF NOT EXISTS "
                f"idx_{table}_project_id ON {table} (project_id)"
            )


def _backfill_project_id(default_project_id: int) -> None:
    """Set project_id = default for every legacy NULL row."""
    with conn() as c:
        for table in _SCOPED_TABLES:
            if not _table_exists(c, table) or not _column_exists(c, table, "project_id"):
                continue
            c.execute(
                f"UPDATE {table} SET project_id = ? WHERE project_id IS NULL",
                (default_project_id,),
            )


def _seed_default_project_if_empty() -> None:
    """First-run helper — creates a 'stoptions' project from current env vars
    and backfills every existing row to point at it.

    When Postgres is in use, the default project already lives there (migrated
    from SQLite). We still seed SQLite's project table for legacy / fallback
    paths, but the project_id values must match Postgres so per-project scoping
    keeps working.
    """
    with conn() as c:
        existing = c.execute("SELECT COUNT(*) AS n FROM projects").fetchone()
    if existing["n"] > 0:
        # Even on already-seeded installs, ensure new tables get the backfill.
        default = _get_default_project_row()
        if default:
            _backfill_project_id(default["id"])
        return

    # Read current env vars as the seed defaults (lazy import to avoid cycles).
    try:
        from app.config import (
            DEFAULT_DOMAIN,
            DEFAULT_TARGET_URL,
            GSC_DEFAULT_SITE,
            GA4_PROPERTY_ID,
        )
    except Exception:
        DEFAULT_DOMAIN = "stoptions.ai"
        DEFAULT_TARGET_URL = "https://stoptions.ai/"
        GSC_DEFAULT_SITE = "sc-domain:stoptions.ai"
        GA4_PROPERTY_ID = ""

    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    slug = "stoptions"
    name = "Stoptions.ai"
    with conn() as c:
        c.execute(
            "INSERT INTO projects (slug, name, domain, target_url, gsc_site, "
            "ga4_property_id, status, is_default, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active', 1, ?, ?)",
            (slug, name, DEFAULT_DOMAIN, DEFAULT_TARGET_URL,
             GSC_DEFAULT_SITE, GA4_PROPERTY_ID, now, now),
        )
        new_id = c.execute(
            "SELECT id FROM projects WHERE slug = ?", (slug,)
        ).fetchone()["id"]

    _backfill_project_id(new_id)


def _get_default_project_row() -> Optional[dict]:
    """Default project — routes through Postgres when SUPABASE is set so the
    fallback in active_project_id() matches what Next.js sees."""
    if _USE_PG_FOR_PROJECTS:
        try:
            with _pg_conn() as c:
                cur = c.cursor()
                cur.execute(
                    "SELECT * FROM projects WHERE is_default = 1 LIMIT 1"
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        "SELECT * FROM projects WHERE status = 'active' "
                        "ORDER BY id LIMIT 1"
                    )
                    row = cur.fetchone()
                return _normalize_project_row(row) if row else None
        except Exception:
            # If Postgres is unreachable for any reason, fall through to SQLite
            # so the Streamlit app stays operational.
            pass

    with conn() as c:
        row = c.execute(
            "SELECT * FROM projects WHERE is_default = 1 LIMIT 1"
        ).fetchone()
        if not row:
            row = c.execute(
                "SELECT * FROM projects WHERE status = 'active' ORDER BY id LIMIT 1"
            ).fetchone()
    return dict(row) if row else None


# ---- Public project helpers --------------------------------------------------
#
# Sprint 7 — these auto-route to Postgres when SUPABASE_DATABASE_URL is set so
# the Next.js admin (critterlabs.io/mgmt) sees the same project list. Falls
# back to the SQLite path for local dev / installs without Supabase.


def _normalize_project_row(row: dict) -> dict:
    """Cast Postgres-native types into the same Python types the SQLite path
    has always returned. Keeps callers identical across backends."""
    if row is None:
        return None
    out = dict(row)
    # is_default returns as Python int on both, so no cast needed
    return out


def list_projects(include_archived: bool = False) -> List[dict]:
    if _USE_PG_FOR_PROJECTS:
        with _pg_conn() as c:
            cur = c.cursor()
            if include_archived:
                cur.execute(
                    "SELECT * FROM projects "
                    "ORDER BY is_default DESC, lower(name)"
                )
            else:
                cur.execute(
                    "SELECT * FROM projects WHERE status = 'active' "
                    "ORDER BY is_default DESC, lower(name)"
                )
            return [_normalize_project_row(r) for r in cur.fetchall()]

    # SQLite fallback (legacy / dev mode)
    init_db()
    with conn() as c:
        if include_archived:
            rows = c.execute(
                "SELECT * FROM projects ORDER BY is_default DESC, name COLLATE NOCASE"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM projects WHERE status = 'active' "
                "ORDER BY is_default DESC, name COLLATE NOCASE"
            ).fetchall()
    return [dict(r) for r in rows]


def get_project(id_or_slug) -> Optional[dict]:
    if _USE_PG_FOR_PROJECTS:
        with _pg_conn() as c:
            cur = c.cursor()
            if isinstance(id_or_slug, int) or (isinstance(id_or_slug, str)
                                                and id_or_slug.isdigit()):
                cur.execute("SELECT * FROM projects WHERE id = %s",
                            (int(id_or_slug),))
            else:
                cur.execute("SELECT * FROM projects WHERE slug = %s",
                            (id_or_slug,))
            row = cur.fetchone()
            return _normalize_project_row(row) if row else None

    init_db()
    with conn() as c:
        if isinstance(id_or_slug, int) or (isinstance(id_or_slug, str)
                                            and id_or_slug.isdigit()):
            row = c.execute(
                "SELECT * FROM projects WHERE id = ?", (int(id_or_slug),)
            ).fetchone()
        else:
            row = c.execute(
                "SELECT * FROM projects WHERE slug = ?", (id_or_slug,)
            ).fetchone()
    return dict(row) if row else None


def add_project(
    *,
    slug: str,
    name: str,
    domain: str,
    target_url: str,
    gsc_site: str = "",
    ga4_property_id: str = "",
    claude_md: str = "",
    accent_color: str = "#3DDC97",
) -> int:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    args = (slug.strip().lower(), name.strip(), domain.strip().lower(),
            target_url.strip(), gsc_site.strip(), ga4_property_id.strip(),
            claude_md, accent_color, now, now)

    if _USE_PG_FOR_PROJECTS:
        with _pg_conn() as c:
            cur = c.cursor()
            cur.execute(
                "INSERT INTO projects (slug, name, domain, target_url, gsc_site, "
                "ga4_property_id, claude_md, accent_color, status, is_default, "
                "created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', 0, %s, %s) "
                "RETURNING id",
                args,
            )
            return cur.fetchone()["id"]

    init_db()
    with conn() as c:
        cur = c.execute(
            "INSERT INTO projects (slug, name, domain, target_url, gsc_site, "
            "ga4_property_id, claude_md, accent_color, status, is_default, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, ?, ?)",
            args,
        )
        return cur.lastrowid


def update_project(project_id: int, **fields) -> None:
    """Update any whitelisted field. Unknown keys are ignored."""
    allowed = {"name", "domain", "target_url", "gsc_site", "ga4_property_id",
               "claude_md", "accent_color", "status"}
    cleaned = {k: v for k, v in fields.items() if k in allowed}
    if not cleaned:
        return
    cleaned["updated_at"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    if _USE_PG_FOR_PROJECTS:
        sets = ", ".join(f"{k} = %s" for k in cleaned)
        values = list(cleaned.values()) + [project_id]
        with _pg_conn() as c:
            cur = c.cursor()
            cur.execute(f"UPDATE projects SET {sets} WHERE id = %s", values)
        return

    init_db()
    sets = ", ".join(f"{k} = ?" for k in cleaned)
    values = list(cleaned.values()) + [project_id]
    with conn() as c:
        c.execute(f"UPDATE projects SET {sets} WHERE id = ?", values)


def archive_project(project_id: int) -> None:
    update_project(project_id, status="archived")


def set_default_project(project_id: int) -> None:
    if _USE_PG_FOR_PROJECTS:
        with _pg_conn() as c:
            cur = c.cursor()
            cur.execute("UPDATE projects SET is_default = 0")
            cur.execute("UPDATE projects SET is_default = 1 WHERE id = %s",
                        (project_id,))
        return

    init_db()
    with conn() as c:
        c.execute("UPDATE projects SET is_default = 0")
        c.execute("UPDATE projects SET is_default = 1 WHERE id = ?", (project_id,))


def active_project_id(default_to_seeded: bool = True) -> Optional[int]:
    """Return the currently-active project id.

    Looks at Streamlit session state first (`active_project_id`), then falls
    back to the default-flagged project, then the lowest-id active project.
    Returns None only if there are no projects at all (shouldn't happen post
    init_db).
    """
    try:
        import streamlit as st
        pid = st.session_state.get("active_project_id")
        if pid:
            return int(pid)
    except Exception:
        pass

    if not default_to_seeded:
        return None
    default = _get_default_project_row()
    return default["id"] if default else None


def active_project() -> Optional[dict]:
    pid = active_project_id()
    return get_project(pid) if pid else None


def _pid(project_id: Optional[int] = None) -> Optional[int]:
    """Resolve a project_id — explicit param > active project > None."""
    if project_id is not None:
        return int(project_id)
    return active_project_id()


def _pid_clause(alias: str = "") -> str:
    """Returns ' AND project_id = ?' (or ' AND alias.project_id = ?')."""
    if alias:
        return f" AND {alias}.project_id = ?"
    return " AND project_id = ?"


# --------------------------------------------------------------- rank_history
def log_rank(keyword: str, domain: str, position: Optional[int], matched_url: str = "", engine: str = "duckduckgo", project_id: Optional[int] = None) -> None:
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        c.execute(
            "INSERT INTO rank_history (ts, keyword, domain, position, matched_url, engine, project_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
             (keyword or "").strip(), (domain or "").strip().lower(), position, matched_url, engine, pid),
        )


def list_keywords(project_id: Optional[int] = None) -> List[str]:
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            rows = c.execute("SELECT DISTINCT keyword FROM rank_history ORDER BY keyword").fetchall()
        else:
            rows = c.execute(
                "SELECT DISTINCT keyword FROM rank_history WHERE project_id = ? ORDER BY keyword",
                (pid,),
            ).fetchall()
    return [r["keyword"] for r in rows]


def history_for(keyword: str, domain: Optional[str] = None, project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    sql = "SELECT ts, keyword, domain, position, matched_url, engine FROM rank_history WHERE keyword = ?"
    params: list = [keyword]
    if domain:
        sql += " AND domain = ?"
        params.append(domain.lower())
    if pid is not None:
        sql += " AND project_id = ?"
        params.append(pid)
    sql += " ORDER BY ts ASC"
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def all_history(limit: int = 1000, project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            rows = c.execute(
                "SELECT ts, keyword, domain, position, matched_url, engine FROM rank_history ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT ts, keyword, domain, position, matched_url, engine FROM rank_history WHERE project_id = ? ORDER BY ts DESC LIMIT ?",
                (pid, limit),
            ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------- gsc_snapshots
def log_gsc_snapshot(
    site_url: str, dimension: str, rows: list[dict],
    range_start: str, range_end: str, project_id: Optional[int] = None,
) -> int:
    if not rows:
        return 0
    init_db()
    pid = _pid(project_id)
    ts = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    n = 0
    with conn() as c:
        for r in rows:
            c.execute(
                "INSERT INTO gsc_snapshots "
                "(ts, site_url, dimension, key, clicks, impressions, ctr, position, range_start, range_end, project_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ts, site_url, dimension, r.get("key") or "",
                    r.get("clicks"), r.get("impressions"),
                    r.get("ctr"), r.get("position"),
                    range_start, range_end, pid,
                ),
            )
            n += 1
    return n


def gsc_recent_snapshots(dimension: str = "query", days: int = 14, project_id: Optional[int] = None) -> list[dict]:
    init_db()
    pid = _pid(project_id)
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat(timespec="seconds") + "Z"
    with conn() as c:
        if pid is None:
            rows = c.execute(
                "SELECT ts, site_url, dimension, key, clicks, impressions, ctr, position "
                "FROM gsc_snapshots WHERE dimension = ? AND ts >= ? ORDER BY ts ASC",
                (dimension, cutoff),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT ts, site_url, dimension, key, clicks, impressions, ctr, position "
                "FROM gsc_snapshots WHERE dimension = ? AND ts >= ? AND project_id = ? ORDER BY ts ASC",
                (dimension, cutoff, pid),
            ).fetchall()
    return [dict(r) for r in rows]


def gsc_two_snapshot_movers(dimension: str = "query", top_n: int = 10, project_id: Optional[int] = None) -> dict:
    """Compare the latest two distinct snapshot timestamps for movers per key.

    Returns {latest_ts, previous_ts, gainers, losers, dropped_out, new_in}.
    """
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        # Find the two most recent distinct timestamps for this dimension+project
        if pid is None:
            ts_rows = c.execute(
                "SELECT DISTINCT ts FROM gsc_snapshots WHERE dimension = ? "
                "ORDER BY ts DESC LIMIT 2",
                (dimension,),
            ).fetchall()
        else:
            ts_rows = c.execute(
                "SELECT DISTINCT ts FROM gsc_snapshots WHERE dimension = ? AND project_id = ? "
                "ORDER BY ts DESC LIMIT 2",
                (dimension, pid),
            ).fetchall()
    if len(ts_rows) < 2:
        return {"latest_ts": None, "previous_ts": None,
                "gainers": [], "losers": [], "dropped_out": [], "new_in": []}

    latest_ts, prev_ts = ts_rows[0]["ts"], ts_rows[1]["ts"]
    with conn() as c:
        def _snap(ts_):
            if pid is None:
                rows = c.execute(
                    "SELECT key, clicks, impressions, position "
                    "FROM gsc_snapshots WHERE ts = ? AND dimension = ?",
                    (ts_, dimension),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT key, clicks, impressions, position "
                    "FROM gsc_snapshots WHERE ts = ? AND dimension = ? AND project_id = ?",
                    (ts_, dimension, pid),
                ).fetchall()
            return {r["key"]: dict(r) for r in rows}

        latest = _snap(latest_ts)
        prev = _snap(prev_ts)

    movers = []
    dropped_out = []
    new_in = []

    for key in latest:
        if key not in prev:
            new_in.append({"key": key, **{k: latest[key].get(k) for k in
                          ("clicks", "impressions", "position")}})
            continue
        l_pos, p_pos = latest[key].get("position"), prev[key].get("position")
        if l_pos is None or p_pos is None:
            continue
        delta = p_pos - l_pos   # positive = improvement (lower position = better)
        movers.append({
            "key": key,
            "from": round(p_pos, 1),
            "to": round(l_pos, 1),
            "delta": round(delta, 1),
            "clicks_now": latest[key].get("clicks"),
            "impressions_now": latest[key].get("impressions"),
        })

    for key in prev:
        if key not in latest:
            dropped_out.append({"key": key,
                                "was_position": round(prev[key].get("position") or 0, 1),
                                "was_clicks": prev[key].get("clicks")})

    movers.sort(key=lambda m: abs(m["delta"]), reverse=True)
    gainers = [m for m in movers if m["delta"] > 0][:top_n]
    losers = [m for m in movers if m["delta"] < 0][:top_n]
    return {
        "latest_ts": latest_ts,
        "previous_ts": prev_ts,
        "gainers": gainers,
        "losers": losers,
        "dropped_out": dropped_out[:top_n],
        "new_in": new_in[:top_n],
    }


# ------------------------------------------------------------------ schedules
def add_schedule(name: str, cron: str, prompt: str, skip_marketer: bool = False, project_id: Optional[int] = None) -> int:
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        cur = c.execute(
            "INSERT INTO schedules (name, cron, prompt, skip_marketer, created_at, enabled, project_id) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (name, cron, prompt, 1 if skip_marketer else 0,
             dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", pid),
        )
        return cur.lastrowid


def list_schedules(project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            rows = c.execute(
                "SELECT id, name, cron, prompt, skip_marketer, created_at, enabled FROM schedules ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, name, cron, prompt, skip_marketer, created_at, enabled FROM schedules WHERE project_id = ? ORDER BY created_at DESC",
                (pid,),
            ).fetchall()
        return [dict(r) for r in rows]


def delete_schedule(schedule_id: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))


# ------------------------------------------------------------------ seeding
DAILY_KPI_SNAPSHOT_PROMPT = (
    "Run today's **Daily KPI Snapshot** for https://stoptions.ai/. **Lightning fast** — "
    "no full audit, no marketing artefacts. Just the vital signs. Skip the SEO Marketer.\n\n"
    "1. **Rankings** — `estimate_keyword_rank` for our priority keywords "
    "(AI options trading, AI stock trading, AI options strategies, "
    "AI option trade setups, AI stock trade setups, AI options analysis) "
    "against stoptions.ai, depth 30. Tool persists to SQLite so deltas are tracked.\n"
    "2. **GSC queries** — `gsc_top_queries` dimension='query', last 7 days, row_limit=50. "
    "Tool auto-diffs vs yesterday's snapshot. Surface top 3 gainers + top 3 losers.\n"
    "3. **GSC pages** — `gsc_top_queries` dimension='page', last 7 days. Flag any page "
    "that lost >20% clicks vs prior week.\n"
    "4. **GA4 (if configured)** — `ga4_top_pages` + `ga4_conversions` last 7 days vs prior 7. "
    "Surface traffic + conversion deltas. (Skip if tool unavailable.)\n"
    "5. **Critical-error spot check** — `fetch_url` on https://stoptions.ai/. "
    "If status != 200, FIRE. `fetch_robots_txt` — confirm not 404 and our sitemaps "
    "are still declared. `extract_structured_data` — confirm Article/Organization "
    "schema blocks are still present.\n"
    "6. **Skip** full on-page audit, PageSpeed, link signals, deep schema validation, "
    "URL inspection — those run weekly.\n\n"
    "## OUTPUT FORMAT (mandatory — keep it tight)\n\n"
    "```\n"
    "# Daily KPI Snapshot — {YYYY-MM-DD}\n\n"
    "**Health Score: XX/100**  (deduct 15 per critical, 3 per warning)\n\n"
    "## 🟢 Today's wins\n- rank gainers, click gainers, conversion lifts\n\n"
    "## 🟡 Watch\n- small drops, trending wrong\n\n"
    "## 🔴 Critical\n- only real fires (ranking collapse, 5xx, indexed wrong, schema gone)\n\n"
    "## Rankings (vs yesterday)\n| Keyword | Pos | Δ |\n|---|---|---|\n\n"
    "## GSC movers (last 7d vs prior)\n| Query | Pos Δ | Clicks Δ |\n|---|---|---|\n\n"
    "## GA4 (last 7d vs prior)\n| Page | Users Δ | Conversions Δ |\n|---|---|---|\n\n"
    "## One thing to do today\n→ specific, owned, shippable.\n"
    "```"
)

# Back-compat alias so existing code paths still work
DAILY_HEALTH_CHECK_PROMPT = DAILY_KPI_SNAPSHOT_PROMPT

WEEKLY_FULL_AUDIT_PROMPT = (
    "Run this week's **Full Audit** on https://stoptions.ai/. Cover all three layers:\n\n"
    "1. **Technical SEO** — robots.txt, sitemap coverage (top 50 URLs), "
    "Core Web Vitals on homepage + top 3 templates, schema implementation, "
    "canonical/hreflang chains, internal-link architecture and orphan pages.\n"
    "2. **On-page SEO** — title / meta / H1 hygiene, content depth, target-keyword "
    "density and semantic n-grams, E-E-A-T signals across the top 5 URLs.\n"
    "3. **Off-page SEO** — backlink profile (`find_backlink_signals`), unlinked "
    "mentions, competitive snapshot vs the top 3 organic competitors for "
    "the keywords 'AI options trading' and 'AI stock trade setups' (identify them "
    "from SERP analysis, don't assume).\n\n"
    "Deliver:\n"
    "- **Week-over-week summary** — what changed since last Sunday\n"
    "- **Top 10 prioritised actions** (What → Why → How → Effort → Impact)\n"
    "- **Maya's package** — outreach prospect list + content brief\n\n"
    "Save the full report."
)

SEED_SCHEDULES = [
    {
        "name": "Daily KPI Snapshot",
        "cron": "0 8 * * *",
        "prompt": DAILY_KPI_SNAPSHOT_PROMPT,
        "skip_marketer": True,
    },
    {
        "name": "Weekly Full Audit",
        "cron": "0 6 * * 0",
        "prompt": WEEKLY_FULL_AUDIT_PROMPT,
        "skip_marketer": False,
    },
]


# --------------------------------------------------------------- scheduler runs
def start_scheduler_run(schedule_id: int, name: str, project_id: Optional[int] = None) -> int:
    init_db()
    pid = _pid(project_id)
    if pid is None:
        # Inherit from the schedule row if we can
        with conn() as c:
            row = c.execute("SELECT project_id FROM schedules WHERE id = ?",
                            (schedule_id,)).fetchone()
            if row:
                pid = row["project_id"]
    with conn() as c:
        cur = c.execute(
            "INSERT INTO scheduler_runs (schedule_id, name, started_at, status, project_id) "
            "VALUES (?, ?, ?, 'running', ?)",
            (schedule_id, name, dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", pid),
        )
        return cur.lastrowid


def finish_scheduler_run(
    run_id: int, status: str, report_path: str = "", error_text: str = "",
    cost_usd: float = 0.0, input_tokens: int = 0, output_tokens: int = 0,
) -> None:
    with conn() as c:
        started_row = c.execute("SELECT started_at FROM scheduler_runs WHERE id = ?",
                                (run_id,)).fetchone()
        finished = dt.datetime.utcnow()
        duration = None
        if started_row:
            try:
                started = dt.datetime.fromisoformat(started_row["started_at"].rstrip("Z"))
                duration = (finished - started).total_seconds()
            except Exception:
                pass
        c.execute(
            "UPDATE scheduler_runs SET finished_at = ?, status = ?, duration_sec = ?, "
            "report_path = ?, error_text = ?, cost_usd = ?, input_tokens = ?, output_tokens = ? "
            "WHERE id = ?",
            (finished.isoformat(timespec="seconds") + "Z", status, duration,
             report_path, error_text, cost_usd, input_tokens, output_tokens, run_id),
        )


def last_run_for(schedule_id: int) -> Optional[dict]:
    init_db()
    with conn() as c:
        r = c.execute(
            "SELECT * FROM scheduler_runs WHERE schedule_id = ? "
            "ORDER BY started_at DESC LIMIT 1", (schedule_id,)
        ).fetchone()
    return dict(r) if r else None


def recent_scheduler_runs(limit: int = 50, project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            rows = c.execute(
                "SELECT * FROM scheduler_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM scheduler_runs WHERE project_id = ? ORDER BY started_at DESC LIMIT ?",
                (pid, limit),
            ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------- cost_log
# Anthropic pricing per million tokens (claude-sonnet-4-5 default).
ANTHROPIC_PRICING = {
    "claude-sonnet-4-5":      {"in": 3.00, "out": 15.00},
    "claude-sonnet-4-6":      {"in": 3.00, "out": 15.00},
    "claude-opus-4-6":        {"in": 15.00, "out": 75.00},
    "claude-haiku-4-5":       {"in": 0.80, "out": 4.00},
    "claude-haiku-4-5-20251001": {"in": 0.80, "out": 4.00},
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = ANTHROPIC_PRICING.get(model)
    if not rates:
        # default to sonnet pricing if unknown
        rates = ANTHROPIC_PRICING["claude-sonnet-4-5"]
    return round(
        (input_tokens / 1_000_000) * rates["in"] +
        (output_tokens / 1_000_000) * rates["out"],
        6,
    )


def log_cost(agent: str, model: str, input_tokens: int, output_tokens: int,
             run_id: str = "", prompt_label: str = "", project_id: Optional[int] = None) -> float:
    init_db()
    pid = _pid(project_id)
    cost = estimate_cost_usd(model, input_tokens, output_tokens)
    with conn() as c:
        c.execute(
            "INSERT INTO cost_log (ts, agent, run_id, model, input_tokens, output_tokens, "
            "cost_usd, prompt_label, project_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
             agent, run_id, model, input_tokens, output_tokens, cost, prompt_label, pid),
        )

    # Mirror to Postgres so the Next.js admin's right-rail Today's-Bill is
    # real (and so cost history survives Streamlit Cloud container restarts).
    # Best-effort — never fails the SQLite write.
    try:
        slug = None
        if pid is not None:
            proj = get_project(pid)
            if proj:
                slug = proj.get("slug")
        save_cost_to_pg(
            project_slug=slug,
            agent=agent, model=model,
            input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost,
            run_id=run_id, prompt_label=prompt_label,
        )
    except Exception as _pg_err:
        # Already swallowed inside save_cost_to_pg, but belt-and-suspenders.
        pass

    return cost


def cost_totals(days: int = 30, project_id: Optional[int] = None) -> dict:
    init_db()
    pid = _pid(project_id)
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat(timespec="seconds") + "Z"
    today_start = dt.datetime.utcnow().replace(hour=0, minute=0, second=0,
                                                microsecond=0).isoformat() + "Z"
    base_where = "ts >= ?" + (" AND project_id = ?" if pid is not None else "")
    base_params = [cutoff] + ([pid] if pid is not None else [])
    today_where = "ts >= ?" + (" AND project_id = ?" if pid is not None else "")
    today_params = [today_start] + ([pid] if pid is not None else [])
    with conn() as c:
        total = c.execute(
            "SELECT COALESCE(SUM(cost_usd),0) AS s, COALESCE(SUM(input_tokens),0) AS i, "
            "COALESCE(SUM(output_tokens),0) AS o, COUNT(*) AS n "
            f"FROM cost_log WHERE {base_where}", base_params
        ).fetchone()
        today = c.execute(
            f"SELECT COALESCE(SUM(cost_usd),0) AS s FROM cost_log WHERE {today_where}",
            today_params,
        ).fetchone()
        by_agent = c.execute(
            "SELECT agent, COALESCE(SUM(cost_usd),0) AS s, COUNT(*) AS n "
            f"FROM cost_log WHERE {base_where} GROUP BY agent", base_params
        ).fetchall()
    return {
        "window_days": days,
        "total_usd": round(total["s"], 4),
        "today_usd": round(today["s"], 4),
        "input_tokens": total["i"],
        "output_tokens": total["o"],
        "call_count": total["n"],
        "by_agent": [dict(r) for r in by_agent],
    }


def cost_daily_series(days: int = 30, project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat(timespec="seconds") + "Z"
    where = "ts >= ?" + (" AND project_id = ?" if pid is not None else "")
    params = [cutoff] + ([pid] if pid is not None else [])
    with conn() as c:
        rows = c.execute(
            f"SELECT substr(ts,1,10) AS day, SUM(cost_usd) AS s "
            f"FROM cost_log WHERE {where} GROUP BY day ORDER BY day", params,
        ).fetchall()
    return [dict(r) for r in rows]


def cost_daily_series_by_agent(days: int = 30, project_id: Optional[int] = None) -> List[dict]:
    """Daily spend broken out by agent — for stacked-area visualisations."""
    init_db()
    pid = _pid(project_id)
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat(timespec="seconds") + "Z"
    where = "ts >= ?" + (" AND project_id = ?" if pid is not None else "")
    params = [cutoff] + ([pid] if pid is not None else [])
    with conn() as c:
        rows = c.execute(
            f"SELECT substr(ts,1,10) AS day, COALESCE(NULLIF(agent,''),'unknown') AS agent, "
            f"SUM(cost_usd) AS s "
            f"FROM cost_log WHERE {where} "
            f"GROUP BY day, agent ORDER BY day", params,
        ).fetchall()
    return [dict(r) for r in rows]


# -------------------------------------------------------------------- decisions
def add_decision(title: str, detail: str = "", source_report: str = "",
                 target_url: str = "", target_keyword: str = "",
                 effort: str = "", impact: str = "", project_id: Optional[int] = None) -> int:
    init_db()
    pid = _pid(project_id)
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        cur = c.execute(
            "INSERT INTO decisions (created_at, updated_at, title, detail, source_report, "
            "target_url, target_keyword, effort, impact, status, project_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
            (now, now, title, detail, source_report, target_url, target_keyword, effort, impact, pid),
        )
        return cur.lastrowid


def list_decisions(status: str = "", project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    where_parts = []
    params: list = []
    if status:
        where_parts.append("status = ?")
        params.append(status)
    if pid is not None:
        where_parts.append("project_id = ?")
        params.append(pid)
    where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    with conn() as c:
        rows = c.execute(
            f"SELECT * FROM decisions{where} ORDER BY created_at DESC", params,
        ).fetchall()
    return [dict(r) for r in rows]


def update_decision_status(decision_id: int, status: str, note: str = "") -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        if status == "done":
            c.execute(
                "UPDATE decisions SET status = ?, status_note = ?, updated_at = ?, "
                "shipped_at = ? WHERE id = ?",
                (status, note, now, now, decision_id),
            )
        else:
            c.execute(
                "UPDATE decisions SET status = ?, status_note = ?, updated_at = ? WHERE id = ?",
                (status, note, now, decision_id),
            )


def open_decisions_summary(max_items: int = 20) -> str:
    """Compact text block to inject into agent prompts so they don't re-flag known issues."""
    open_items = list_decisions(status="open")
    in_prog = list_decisions(status="in_progress")
    wontfix = list_decisions(status="wontfix")
    if not (open_items or in_prog or wontfix):
        return ""
    lines = ["## Known decisions (from past runs — do not re-flag)"]
    for d in (open_items + in_prog)[:max_items]:
        tag = f"[{d['status'].upper()}]"
        scope = d.get("target_url") or d.get("target_keyword") or ""
        lines.append(f"- {tag} {d['title']} {('· ' + scope) if scope else ''}")
    if wontfix:
        lines.append("\n### Won't fix (do not re-recommend)")
        for d in wontfix[:10]:
            lines.append(f"- {d['title']} — reason: {d.get('status_note') or 'not stated'}")
    return "\n".join(lines)


# --------------------------------------------------------------------- outreach
def add_outreach(prospect_url: str, prospect_name: str = "", region: str = "",
                 angle: str = "", pitch_template: str = "", contact_email: str = "",
                 source_report: str = "", project_id: Optional[int] = None) -> int:
    init_db()
    pid = _pid(project_id)
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        cur = c.execute(
            "INSERT INTO outreach (created_at, updated_at, prospect_url, prospect_name, "
            "region, angle, pitch_template, contact_email, status, source_report, project_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)",
            (now, now, prospect_url, prospect_name, region, angle, pitch_template,
             contact_email, source_report, pid),
        )
        return cur.lastrowid


def list_outreach(status: str = "", project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    where_parts = []
    params: list = []
    if status:
        where_parts.append("status = ?")
        params.append(status)
    if pid is not None:
        where_parts.append("project_id = ?")
        params.append(pid)
    where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    with conn() as c:
        rows = c.execute(
            f"SELECT * FROM outreach{where} ORDER BY created_at DESC", params,
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------- content_calendar
def add_content_item(
    title: str, target_keyword: str = "", intent: str = "informational",
    content_type: str = "blog", owner: str = "", due_date: str = "",
    target_url: str = "", word_count: int = 0, outline: str = "",
    source_report: str = "", status: str = "idea", project_id: Optional[int] = None,
) -> int:
    init_db()
    pid = _pid(project_id)
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        cur = c.execute(
            "INSERT INTO content_calendar (created_at, updated_at, title, target_keyword, "
            "intent, content_type, owner, due_date, target_url, word_count, outline, "
            "status, source_report, project_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now, now, title, target_keyword, intent, content_type, owner, due_date,
             target_url, word_count, outline, status, source_report, pid),
        )
        return cur.lastrowid


def list_content(status: str = "", project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    where_parts = []
    params: list = []
    if status:
        where_parts.append("status = ?")
        params.append(status)
    if pid is not None:
        where_parts.append("project_id = ?")
        params.append(pid)
    where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    with conn() as c:
        rows = c.execute(
            f"SELECT * FROM content_calendar{where} "
            "ORDER BY COALESCE(due_date, '9999') ASC, created_at DESC", params,
        ).fetchall()
    return [dict(r) for r in rows]


def update_content_status(content_id: int, status: str, note: str = "",
                          publish_date: str = "") -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        if publish_date:
            c.execute(
                "UPDATE content_calendar SET status = ?, status_note = ?, "
                "publish_date = ?, updated_at = ? WHERE id = ?",
                (status, note, publish_date, now, content_id),
            )
        else:
            c.execute(
                "UPDATE content_calendar SET status = ?, status_note = ?, "
                "updated_at = ? WHERE id = ?",
                (status, note, now, content_id),
            )


def delete_content_item(content_id: int) -> None:
    with conn() as c:
        c.execute("DELETE FROM content_calendar WHERE id = ?", (content_id,))


# ------------------------------------------------------------- aeo_citations
def log_aeo_citation(query: str, engine: str, cited: bool,
                     citation_count: int = 0, response_text: str = "",
                     citations: Optional[List[str]] = None,
                     project_id: Optional[int] = None) -> None:
    init_db()
    pid = _pid(project_id)
    import json as _json
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        c.execute(
            "INSERT INTO aeo_citations (ts, query, engine, cited, citation_count, "
            "response_text, citations_json, project_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (now, query, engine, 1 if cited else 0, citation_count,
             (response_text or "")[:4000], _json.dumps(citations or []), pid),
        )


def aeo_citation_history(days: int = 30, project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat(timespec="seconds") + "Z"
    where = "ts >= ?" + (" AND project_id = ?" if pid is not None else "")
    params = [cutoff] + ([pid] if pid is not None else [])
    with conn() as c:
        rows = c.execute(
            f"SELECT ts, query, engine, cited, citation_count "
            f"FROM aeo_citations WHERE {where} ORDER BY ts DESC", params,
        ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------ report_favorites
def toggle_favorite(report_name: str, project_id: Optional[int] = None) -> bool:
    """Toggle a report's favorite status (scoped per project). Returns the new state."""
    init_db()
    pid = _pid(project_id)
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        if pid is None:
            existing = c.execute(
                "SELECT 1 FROM report_favorites WHERE report_name = ? AND project_id IS NULL",
                (report_name,),
            ).fetchone()
        else:
            existing = c.execute(
                "SELECT 1 FROM report_favorites WHERE report_name = ? AND project_id = ?",
                (report_name, pid),
            ).fetchone()
        if existing:
            if pid is None:
                c.execute(
                    "DELETE FROM report_favorites WHERE report_name = ? AND project_id IS NULL",
                    (report_name,),
                )
            else:
                c.execute(
                    "DELETE FROM report_favorites WHERE report_name = ? AND project_id = ?",
                    (report_name, pid),
                )
            return False
        c.execute(
            "INSERT INTO report_favorites (report_name, favorited_at, project_id) VALUES (?, ?, ?)",
            (report_name, now, pid),
        )
        return True


def is_favorite(report_name: str, project_id: Optional[int] = None) -> bool:
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            r = c.execute(
                "SELECT 1 FROM report_favorites WHERE report_name = ? AND project_id IS NULL",
                (report_name,),
            ).fetchone()
        else:
            r = c.execute(
                "SELECT 1 FROM report_favorites WHERE report_name = ? AND project_id = ?",
                (report_name, pid),
            ).fetchone()
    return bool(r)


def update_outreach_status(outreach_id: int, status: str, note: str = "",
                           placed_url: str = "") -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        sets = ["status = ?", "status_note = ?", "updated_at = ?"]
        vals: list = [status, note, now]
        if status == "contacted":
            sets.append("contacted_at = ?")
            vals.append(now)
        if status == "replied":
            sets.append("replied_at = ?")
            vals.append(now)
        if status == "placed":
            sets.append("placed_at = ?")
            sets.append("placed_url = ?")
            vals.extend([now, placed_url])
        vals.append(outreach_id)
        c.execute(f"UPDATE outreach SET {', '.join(sets)} WHERE id = ?", vals)


# =============================================================================
# Sprint 6 — Smarter-over-time helpers
# =============================================================================

def get_agent_notes(agent_key: str, project_id: Optional[int] = None) -> str:
    """Return the free-form learnings notebook for an agent (Markdown)."""
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            row = c.execute(
                "SELECT notes_md FROM agent_notes WHERE agent_key = ? AND project_id IS NULL",
                (agent_key,),
            ).fetchone()
        else:
            row = c.execute(
                "SELECT notes_md FROM agent_notes WHERE agent_key = ? AND project_id = ?",
                (agent_key, pid),
            ).fetchone()
    return row["notes_md"] if row else ""


def set_agent_notes(agent_key: str, notes_md: str,
                    project_id: Optional[int] = None) -> None:
    init_db()
    pid = _pid(project_id)
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        # Try update first; if no row, insert.
        if pid is None:
            res = c.execute(
                "UPDATE agent_notes SET notes_md = ?, updated_at = ? "
                "WHERE agent_key = ? AND project_id IS NULL",
                (notes_md, now, agent_key),
            )
        else:
            res = c.execute(
                "UPDATE agent_notes SET notes_md = ?, updated_at = ? "
                "WHERE agent_key = ? AND project_id = ?",
                (notes_md, now, agent_key, pid),
            )
        if res.rowcount == 0:
            c.execute(
                "INSERT INTO agent_notes (project_id, agent_key, notes_md, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (pid, agent_key, notes_md, now),
            )


def add_agent_rejection(agent_key: str, reason: str,
                        report_name: str = "",
                        project_id: Optional[int] = None) -> int:
    init_db()
    pid = _pid(project_id)
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with conn() as c:
        cur = c.execute(
            "INSERT INTO agent_rejections (project_id, agent_key, report_name, "
            "reason, rejected_at) VALUES (?, ?, ?, ?, ?)",
            (pid, agent_key, report_name, reason, now),
        )
        return cur.lastrowid


def recent_rejections(agent_key: Optional[str] = None, limit: int = 10,
                      project_id: Optional[int] = None) -> List[dict]:
    init_db()
    pid = _pid(project_id)
    parts = []
    params: list = []
    if agent_key:
        parts.append("agent_key = ?")
        params.append(agent_key)
    if pid is not None:
        parts.append("project_id = ?")
        params.append(pid)
    where = (" WHERE " + " AND ".join(parts)) if parts else ""
    params.append(limit)
    with conn() as c:
        rows = c.execute(
            f"SELECT * FROM agent_rejections{where} ORDER BY rejected_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def list_favorites_with_notes(project_id: Optional[int] = None) -> List[dict]:
    """Starred reports + their why-it-was-great note. Powers the few-shot vault."""
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            rows = c.execute(
                "SELECT report_name, COALESCE(note,'') AS note, favorited_at "
                "FROM report_favorites WHERE project_id IS NULL ORDER BY favorited_at DESC"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT report_name, COALESCE(note,'') AS note, favorited_at "
                "FROM report_favorites WHERE project_id = ? ORDER BY favorited_at DESC",
                (pid,),
            ).fetchall()
    return [dict(r) for r in rows]


def set_favorite_note(report_name: str, note: str,
                      project_id: Optional[int] = None) -> None:
    """Annotate a starred report (why it's a good reference)."""
    init_db()
    pid = _pid(project_id)
    with conn() as c:
        if pid is None:
            c.execute(
                "UPDATE report_favorites SET note = ? "
                "WHERE report_name = ? AND project_id IS NULL",
                (note, report_name),
            )
        else:
            c.execute(
                "UPDATE report_favorites SET note = ? "
                "WHERE report_name = ? AND project_id = ?",
                (note, report_name, pid),
            )


def seed_default_schedules() -> bool:
    """Seed Daily Health Check + Weekly Full Audit once. Returns True if seeded."""
    init_db()
    with conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT)")
        row = c.execute(
            "SELECT value FROM app_meta WHERE key = ?",
            ("default_schedules_seeded",),
        ).fetchone()
        if row:
            return False
    for s in SEED_SCHEDULES:
        add_schedule(s["name"], s["cron"], s["prompt"], s["skip_marketer"])
    with conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
            ("default_schedules_seeded", "1"),
        )
    return True
