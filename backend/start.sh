#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

exec uvicorn app.main:app --host "$HOST" --port "$PORT"
