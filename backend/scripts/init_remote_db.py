# backend/scripts/init_remote_db.py
import os
import sys
from pathlib import Path

# Ensure "backend/" is on sys.path so "import app" works
ROOT = Path(__file__).resolve().parents[1]  # points to .../backend
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from app.models import Base  # uses your existing ORM models

# Load local .env if present (not required when DATABASE_URL is set in env)
dotenv_path = ROOT / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL env var is required. Set it to your managed Postgres URL.")

engine = create_engine(DATABASE_URL, future=True)

# Create tables if they don't exist; does not drop or alter existing ones
Base.metadata.create_all(engine)
print("✅ Created/verified tables on remote DB.")
