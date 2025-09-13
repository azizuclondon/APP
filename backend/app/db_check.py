# backend/app/db_check.py
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg2


# Load .env locally; in Render, DATABASE_URL comes from env
DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL not found. Expected it in {DOTENV_PATH} or environment")


def check_db():
    """
    Connects to Postgres and returns:
      - ok: True/False
      - version: full version string from server
      - pgvector: whether the 'vector' extension is installed
    """
    # psycopg2-binary uses the same DSN string format you have locally/staging
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]

            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
            (has_vector,) = cur.fetchone()

    return {"ok": True, "version": version, "pgvector": bool(has_vector)}
