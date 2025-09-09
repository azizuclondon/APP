import psycopg
from psycopg.rows import dict_row

# Simple DB check: connect, read version, confirm pgvector exists
def check_db():
    try:
        conn = psycopg.connect(
            "postgresql://pmapp:pmapp@127.0.0.1:5432/pmapp",
            connect_timeout=2
        )
        with conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("select version() as version")
                version = cur.fetchone()["version"]
                cur.execute("select extname from pg_extension where extname = 'vector'")
                has_vector = cur.fetchone() is not None
        return {"ok": True, "version": version, "pgvector": has_vector}
    except Exception as e:
        return {"ok": False, "error": str(e)}
