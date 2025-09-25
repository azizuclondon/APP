# scripts/create_document_pages_table.py
from sqlalchemy import text
from app.db import SessionLocal

SQL = """
CREATE TABLE IF NOT EXISTS document_pages (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_document_pages UNIQUE (document_id, page_number)
);
"""

def main():
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("SUCCESS: table 'document_pages' ensured.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: failed to create table: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
