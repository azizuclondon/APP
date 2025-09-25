# scripts/add_full_text_path_column.py
from sqlalchemy import text
from app.db import SessionLocal

SQL = """
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS full_text_path TEXT;
"""

def main():
    db = SessionLocal()
    try:
        db.execute(text(SQL))
        db.commit()
        print("SUCCESS: documents.full_text_path column ensured.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: failed to alter schema: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
