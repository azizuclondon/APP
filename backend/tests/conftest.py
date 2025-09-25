from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load .env from backend root deterministically (…/backend/.env)
BACKEND_DIR = Path(__file__).resolve().parents[1]
DOTENV_PATH = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=DOTENV_PATH, override=False)

# IMPORTANT: ensure DATABASE_URL is present after loading .env
if not os.getenv("DATABASE_URL"):
    raise RuntimeError(f"DATABASE_URL not found. Expected it in {DOTENV_PATH}")

# Import FastAPI app after env is loaded, so startup sees correct settings
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Session-wide FastAPI test client."""
    return TestClient(app)
