# scripts/add_local_path_column.py
from sqlalchemy import text
from app.db import SessionLocal

SQL_STEPS = [
    # Add a nullable local_path to store where we saved the downloaded file
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS local_path text"
]

def main():
    db = SessionLocal()
    try:
        for sql in SQL_STEPS:
            db.execute(text(sql))
        db.commit()
        print("SUCCESS: documents.local_path ensured (nullable).")
    except Exception as e:
        db.rollback()
        print(f"ERROR: failed to alter schema: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
