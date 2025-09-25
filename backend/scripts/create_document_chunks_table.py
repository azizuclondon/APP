# scripts/create_document_chunks_table.py
from sqlalchemy import text
from app.db import SessionLocal

SQL = """
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_path TEXT NOT NULL,
    level INTEGER NOT NULL,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_doc_chunks UNIQUE (document_id, section_path, chunk_index)
);
"""

def main():
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("SUCCESS: table 'document_chunks' ensured.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: failed to create table: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
