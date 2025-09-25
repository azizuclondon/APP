# scripts/patch_documents_columns.py
from sqlalchemy import text
from app.db import SessionLocal

SQL_STEPS = [
    # Ensure `type` column
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS type text",
    "UPDATE documents SET type = 'pdf' WHERE type IS NULL",
    "ALTER TABLE documents ALTER COLUMN type SET DEFAULT 'pdf'",
    "ALTER TABLE documents ALTER COLUMN type SET NOT NULL",

    # Ensure `uploaded_at` column (used by inserts)
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS uploaded_at timestamp with time zone",
    "UPDATE documents SET uploaded_at = NOW() WHERE uploaded_at IS NULL",
    "ALTER TABLE documents ALTER COLUMN uploaded_at SET DEFAULT NOW()",
    "ALTER TABLE documents ALTER COLUMN uploaded_at SET NOT NULL",
]

def main():
    db = SessionLocal()
    try:
        for sql in SQL_STEPS:
            db.execute(text(sql))
        db.commit()
        print("SUCCESS: documents.type + documents.uploaded_at ensured (NOT NULL with defaults).")
    except Exception as e:
        db.rollback()
        print(f"ERROR: failed to patch schema: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
