# run_schema_fix.py
from sqlalchemy import text
from app.db import SessionLocal

SQL_STEPS = [
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS title text",
    "UPDATE documents SET title = 'Untitled' WHERE title IS NULL",
    "ALTER TABLE documents ALTER COLUMN title SET DEFAULT 'Untitled'",
    "ALTER TABLE documents ALTER COLUMN title SET NOT NULL",
]

def main():
    db = SessionLocal()
    try:
        for sql in SQL_STEPS:
            db.execute(text(sql))
        db.commit()
        print("SUCCESS: 'title' column ensured on 'documents' (NOT NULL with default).")
    except Exception as e:
        db.rollback()
        print(f"ERROR: failed to update schema: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
