# tools/run_sql.py
from pathlib import Path
from app.routers.documents import get_conn

# Path to your migration file
sql_path = Path("db/002_add_document_toc.sql")

# Read the SQL text
sql_text = sql_path.read_text()

# Run SQL against your DB
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(sql_text)
    conn.commit()

print("✅ Migration applied successfully: document_toc table created.")
