# app/routers/chunks.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
import os
import time
import logging

import psycopg
from psycopg.rows import dict_row

from app.embeddings import embed_one, get_embedder
from app.timing import timed_block

router = APIRouter(prefix="/admin/chunks", tags=["chunks"])

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

log = logging.getLogger(__name__)

def _get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def _fetch_chunk_text(conn, chunk_id: int) -> str:
    """
    Tries to read the chunk text. Your table likely stores the text in 'content'.
    If your schema uses 'text' instead, the fallback query will be used.
    """
    with conn.cursor() as cur:
        # Primary: content
        cur.execute("SELECT content FROM document_chunks WHERE id = %s", (chunk_id,))
        row = cur.fetchone()
        if row and row.get("content"):
            return row["content"]
    # Fallback to 'text' column if present in your schema
    with conn.cursor() as cur:
        cur.execute("SELECT text FROM document_chunks WHERE id = %s", (chunk_id,))
        row = cur.fetchone()
        if row and row.get("text"):
            return row["text"]
    raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found or has no text/content.")

def _upsert_embedding(conn, chunk_id: int, vec, model_name: str) -> None:
    """
    Upsert into chunk_embeddings.
    We pass the vector as a Postgres array literal and cast to vector.
    """
    array_literal = "{" + ",".join(str(float(x)) for x in vec) + "}"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, embedding, model)
            VALUES (%s, %s::float8[]::vector, %s)
            ON CONFLICT (chunk_id)
            DO UPDATE SET
                embedding = EXCLUDED.embedding,
                model     = EXCLUDED.model,
                created_at= NOW();
            """,
            (chunk_id, array_literal, model_name),
        )

@router.post("/{chunk_id}/embed")
def embed_chunk(chunk_id: int) -> Dict[str, Any]:
    """
    Compute embedding for a single chunk and upsert into chunk_embeddings.
    Returns basic metadata for verification.
    """
    provider = get_embedder().name
    t0 = time.perf_counter()
    with timed_block("embed_chunk"), _get_conn() as conn:
        text = _fetch_chunk_text(conn, chunk_id)
        vec = embed_one(text)
        _upsert_embedding(conn, chunk_id, vec, provider)
        conn.commit()

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    log.info("embed_chunk id=%s provider=%s elapsed_ms=%s", chunk_id, provider, elapsed_ms)
    return {
        "chunk_id": chunk_id,
        "provider": provider,
        "dim": len(vec),
        "elapsed_ms": elapsed_ms,
        "saved": True,
    }
