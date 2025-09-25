# app/routers/search.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import os
import re

import psycopg
from psycopg.rows import dict_row

from app.embeddings import embed_one
from app.text_utils import normalize_text

router = APIRouter(prefix="/search", tags=["search"])

# -------------------------------
# DB connection
# -------------------------------
def _get_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # Inline ARRAY[...]::vector is used, so no pgvector adapter required.
    return psycopg.connect(url, row_factory=dict_row)

# -------------------------------
# Request model
# -------------------------------
class SearchIn(BaseModel):
    text: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    offset: int = Field(0, ge=0)                # <— pagination start
    document_id: Optional[int] = None
    product_id: Optional[int] = None  # reserved for later JOIN-based filtering
    clean_preview: bool = False
    highlight_terms: bool = True      # simple keyword emphasis
    min_content_chars: int = Field(0, ge=0)  # filter out tiny snippets
    exclude_sections: List[str] = Field(default_factory=list)

# -------------------------------
# MAIN: semantic search (inline vector + fallback)
# -------------------------------
@router.post("")
def semantic_search(payload: SearchIn) -> Dict[str, Any]:
    """
    Semantic search that:
      - embeds the query in Python,
      - inlines the vector as ARRAY[... ]::float8[]::vector in SQL,
      - runs a full query (with documents join & rich fields),
      - if 0 rows, falls back to a minimal ranking query.
    Always returns a 'debug' block to show executed SQL and param types.

    Note: using L2 distance (<->) for ranking.
    """
    # 1) Embed query and build inline vector literal
    q = list(map(float, embed_one(payload.text)))
    qarr_sql = "ARRAY[" + ",".join(f"{v}" for v in q) + "]::float8[]::vector"

    # 2) Optional WHERE
    where_clauses: List[str] = []
    params: List[Any] = []

    if payload.document_id is not None:
        where_clauses.append("c.document_id = %s")
        params.append(payload.document_id)

    if payload.exclude_sections:
        where_clauses.append("NOT (COALESCE(c.section_path, '') = ANY(%s))")
        params.append(payload.exclude_sections)

    if payload.min_content_chars and payload.min_content_chars > 0:
        where_clauses.append("char_length(c.content) >= %s")
        params.append(int(payload.min_content_chars))

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Stable ORDER BY: distance, then chunk_id to break ties deterministically
    order_by = "dist ASC, c.id ASC"

    # 3) First attempt: rich fields + LEFT JOIN documents (L2 distance)
    sql_full = f"""
        SELECT
          c.id                  AS chunk_id,
          (ce.embedding <-> {qarr_sql}) AS dist,
          c.document_id         AS document_id,
          d.title               AS document_title,
          d.source_url          AS source_url,
          c.section_path        AS section_path,
          c.chunk_index         AS chunk_index,
          c.start_page          AS start_page,
          c.end_page            AS end_page,
          LEFT(c.content, 300)  AS preview
        FROM chunk_embeddings ce
        JOIN document_chunks c ON c.id = ce.chunk_id
        LEFT JOIN documents d  ON d.id = c.document_id
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s::int OFFSET %s::int;
    """.strip()

    # 4) Fallback: minimal ranking only (no extra join) (L2 distance)
    sql_min = f"""
        SELECT
          c.id AS chunk_id,
          (ce.embedding <-> {qarr_sql}) AS dist,
          c.document_id AS document_id,
          LEFT(c.content, 200) AS preview
        FROM chunk_embeddings ce
        JOIN document_chunks c ON c.id = ce.chunk_id
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s::int OFFSET %s::int;
    """.strip()

    debug: Dict[str, Any] = {
        "sql_first": sql_full.replace(qarr_sql, "<INLINE_VECTOR>"),
        "params_types_first": [type(p).__name__ for p in (params + [int(payload.top_k), int(payload.offset)])],
    }

    rows: List[Dict[str, Any]] = []
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            # Try the full query
            cur.execute(sql_full, tuple(params + [int(payload.top_k), int(payload.offset)]))
            rows = cur.fetchall()

            # If no rows, try the minimal query
            if not rows:
                debug["fell_back_to_minimal"] = True
                debug["sql_fallback"] = sql_min.replace(qarr_sql, "<INLINE_VECTOR>")
                debug["params_types_fallback"] = [type(p).__name__ for p in (params + [int(payload.top_k), int(payload.offset)])]
                cur.execute(sql_min, tuple(params + [int(payload.top_k), int(payload.offset)]))
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")

    # Optional cleanup & highlighting
    if payload.clean_preview or payload.highlight_terms:
        terms = [t for t in re.split(r"\W+", payload.text) if t]
        pattern = re.compile(r"(" + "|".join(map(re.escape, terms)) + r")", re.IGNORECASE) if terms else None

        for r in rows:
            raw = r.get("preview") or ""
            s = raw.replace("Â©", "©")
            s = normalize_text(s)
            s = "\n".join(ln for ln in s.splitlines() if not ln.strip().isdigit())
            s = re.sub(r"[ \t]+", " ", s).strip()
            if payload.clean_preview:
                r["preview_clean"] = s
            if payload.highlight_terms and pattern:
                r["preview_marked"] = pattern.sub(r"**\1**", s)

            # Also provide a simple normalized score from distance, if you like
            # This is optional and heuristic; here: score = 1 / (1 + dist)
            if "dist" in r and isinstance(r["dist"], (int, float)):
                r["score"] = 1.0 / (1.0 + float(r["dist"]))

    # Pagination bookkeeping
    next_offset = payload.offset + len(rows)

    return {
        "query": payload.text,
        "top_k": payload.top_k,
        "offset": payload.offset,
        "next_offset": next_offset,
        "document_filter": payload.document_id,
        "product_filter": payload.product_id,
        "results": rows,
        "debug": debug,
    }

# -------------------------------
# Quick sanity: self-distance should be 0.0 (L2)
# -------------------------------
@router.get("/_diag")
def semantic_search_diag() -> Dict[str, Any]:
    sql = """
    SELECT
      c.id                 AS chunk_id,
      c.document_id        AS document_id,
      LEFT(c.content, 160) AS preview,
      (ce.embedding <-> ce.embedding) AS self_distance
    FROM chunk_embeddings ce
    JOIN document_chunks c ON c.id = ce.chunk_id
    ORDER BY c.id ASC
    LIMIT 3;
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"diag failed: {e}")
    return {"ok": True, "rows": rows}

# -------------------------------
# Deep diagnostics: confirm DB, counts, and in-app ranking
# -------------------------------
@router.get("/_why")
def search_why() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    sql_counts = """
    SELECT
      (SELECT current_database()) AS current_database,
      (SELECT current_user)       AS current_user,
      (SELECT COUNT(*) FROM documents)        AS n_documents,
      (SELECT COUNT(*) FROM document_chunks)  AS n_chunks,
      (SELECT COUNT(*) FROM chunk_embeddings) AS n_embeddings
    """
    sql_self = """
    SELECT
      c.id AS chunk_id,
      (ce.embedding <-> ce.embedding) AS self_distance
    FROM chunk_embeddings ce
    JOIN document_chunks c ON c.id = ce.chunk_id
    ORDER BY c.id ASC
    LIMIT 3;
    """
    # Param-free ranking using an existing vector as the query (L2)
    sql_rank_sample = """
    WITH q AS (
      SELECT embedding AS v
      FROM chunk_embeddings
      ORDER BY chunk_id ASC
      LIMIT 1
    )
    SELECT
      c.id AS chunk_id,
      (ce.embedding <-> q.v) AS dist
    FROM chunk_embeddings ce
    JOIN document_chunks c ON c.id = ce.chunk_id
    CROSS JOIN q
    ORDER BY dist ASC, c.id ASC
    LIMIT 3;
    """
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql_counts);        out["counts"] = cur.fetchone()
            cur.execute(sql_self);          out["self_dist_sample"] = cur.fetchall()
            cur.execute(sql_rank_sample);   out["rank_sample"] = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"why failed: {e}")
    return out

# -------------------------------
# Echo DSN parts to ensure the server sees the right DATABASE_URL
# -------------------------------
@router.get("/_dsn")
def search_dsn() -> Dict[str, Any]:
    dsn = os.getenv("DATABASE_URL", "")
    # redaction: keep scheme/host/db visible but hide credentials roughly
    redacted = dsn
    if "://" in dsn and "@" in dsn:
        try:
            scheme, rest = dsn.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            user = creds.split(":")[0]
            redacted = f"{scheme}://{user}:***@{hostpart}"
        except Exception:
            redacted = "***"
    return {"DATABASE_URL": redacted}
