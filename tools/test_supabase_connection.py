"""Quick connection test for Supabase Postgres.

Run from the project root after adding SUPABASE_DATABASE_URL to .env:

    python -m tools.test_supabase_connection

Prints clearly whether the connection works + a count of tables on the
remote DB (should be empty pre-migration).
"""
from __future__ import annotations

import os
import sys

try:
    import psycopg2
except ImportError:
    print("psycopg2 not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "psycopg2-binary"])
    import psycopg2

from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_DATABASE_URL", "")

if not URL:
    print("❌ SUPABASE_DATABASE_URL is not set in .env")
    sys.exit(1)

print(f"Connecting to: {URL.split('@')[1].split('/')[0]} ...")
try:
    conn = psycopg2.connect(URL, connect_timeout=15, sslmode="require")
    cur = conn.cursor()
    cur.execute("SELECT version(), current_database(), current_user;")
    v, db, u = cur.fetchone()
    print("✅ CONNECTION SUCCESS")
    print(f"   Postgres: {v.split(',')[0]}")
    print(f"   Database: {db}")
    print(f"   User:     {u}")

    cur.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'public';"
    )
    n = cur.fetchone()[0]
    print(f"   Tables in public schema: {n} "
          f"({'empty — ready for migration' if n == 0 else 'will need to handle existing tables'})")

    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ CONNECTION FAILED: {type(e).__name__}: {e}")
    print()
    print("Common fixes:")
    print("  • Password may be wrong — try resetting at")
    print("    https://supabase.com/dashboard/project/pgacujsitjnbhxkpvsvf/settings/database")
    print("  • Special chars in password need URL-encoding (* → %2A, @ → %40, etc.)")
    print("  • Network: check you can reach aws-1-ap-southeast-1.pooler.supabase.com")
    sys.exit(1)
