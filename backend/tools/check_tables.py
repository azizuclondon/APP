# tools/check_tables.py
from app.routers.documents import get_conn

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema='public';
        """)
        rows = cur.fetchall()

print("Tables in DB:")
for row in rows:
    print("-", row[0])
