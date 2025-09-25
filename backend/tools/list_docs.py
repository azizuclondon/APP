# tools/list_docs.py
from pathlib import Path
import os
from dotenv import load_dotenv
from psycopg.rows import dict_row
from app.routers.documents import get_conn

def main() -> int:
    # Load backend/.env explicitly (works no matter your current directory)
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)

    if not os.getenv("DATABASE_URL"):
        print(f"ERROR: DATABASE_URL is not set. Expected it in: {env_path}")
        return 1

    SQL = """
    SELECT id, title, local_path, uploaded_at
    FROM documents
    ORDER BY id ASC
    """

    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(SQL)
            rows = cur.fetchall()

    if not rows:
        print("No documents found.")
        return 0

    print("Documents:")
    for r in rows:
        print(f"- id={r['id']:>3}  title={r['title']!r}  local_path={r['local_path']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
