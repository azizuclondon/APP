# scripts/add_title_column.py
import os
import sys
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL env var is not set.")
    sys.exit(1)

SQL_STEPS = [
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS title text;",
    "UPDATE documents SET title = 'Untitled' WHERE title IS NULL;",
    "ALTER TABLE documents ALTER COLUMN title SET DEFAULT 'Untitled';",
    "ALTER TABLE documents ALTER COLUMN title SET NOT NULL;",
]

try:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for sql in SQL_STEPS:
                cur.execute(sql)
        conn.commit()
        print("SUCCESS: 'title' column ensured on 'documents' (NOT NULL with default).")
except Exception as e:
    print(f"ERROR: failed to update schema: {e}")
    sys.exit(1)
