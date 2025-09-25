# app/routers/search.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Tuple
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

    # Filters
    document_id: Optional[int] = None
    product_id: Optional[int] = None  # reserved for later JOIN-based filtering
    exclude_section_exact: List[str] = Field(
        default_factory=lambda: ["Dummy PDF file"]
    )
    min_chars: int = 60

    # Pagination
    offset: int = Field(0, ge=0)

    # Output options
    clean_preview: bool = False
    highlight_terms: bool = True

# Utility: light markdown highlighter for matched words (client-side polish)
def _mk_highlighter(q: str):
    # very light tokenizer: split on non-letters/digits, keep 3+ length tokens
    terms = [t for t in re.split(r"[^A-Za-z0-9]+", q.lower()) if len(t) >= 3]
    if not terms:
        return None

    rx = re.compile(r"(" + "|".join(re.escape(t) for t in terms) + r")", re.IGNORECASE)

    def hi(s: str) -> str:
        return rx.sub(lambda m: f"**{m.group(1)}**", s)

    return hi

# -------------------------------
# MAIN: semantic search with:
#  • L2 distance
#  • diversity (best per section_path)
#  • lexical boost (simple LIKE)
#  • pagination (LIMIT/OFFSET + next_offset)
#  • optional cleaning + term highlighting
#  • page_url (source_url#page=N)
# -------------------------------
@router.post("")
def semantic_search(payload: SearchIn) -> Dict[str, Any]:
    """
    One-shot enhanced semantic search:
      - embeds the query and inlines ARRAY[... ]::float8[]::vector
      - computes L2 distance (<->),
      - adds a simple lexical boost when content contains the query text,
      - enforces diversity: pick the top chunk per (document_id, section_path),
      - supports pagination via LIMIT/OFFSET and returns next_offset,
      - returns page_url built from source_url + '#page=start_page',
      - optionally cleans + highlights previews.
    """
    # 1) Embed query and build inline vector literal
    q_vec = list(map(float, embed_one(payload.text)))
    qarr_sql = "ARRAY[" + ",".join(f"{v}" for v in q_vec) + "]::float8[]::vector"

    # 2) Optional WHERE fragments
    where_clauses: List[str] = []
    params: List[Any] = []

    if payload.document_id is not None:
        where_clauses.append("c.document_id = %s")
        params.append(payload.document_id)

    # Basic content quality guard
    if payload.min_chars > 0:
        where_clauses.append("char_length(c.content) >= %s")
        params.append(int(payload.min_chars))

    # Exclude exact section matches (e.g., front matter)
    if payload.exclude_section_exact:
        where_clauses.append("NOT (COALESCE(c.section_path, '') = ANY(%s))")
        params.append(payload.exclude_section_exact)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # 3) Lexical boost (very simple)
    like_term = f"%{payload.text.lower()}%"
    boost_coef = 0.05  # small, conservative boost
    params_for_like = [like_term]

    # 4) SQL with diversity (best per section_path) and STABLE global sort
    sql_full = f"""
    WITH rank_by AS (
      SELECT
        c.id                          AS chunk_id,
        c.document_id                 AS document_id,
        d.title                       AS document_title,
        d.source_url                  AS source_url,
        c.section_path                AS section_path,
        c.chunk_index                 AS chunk_index,
        c.start_page                  AS start_page,
        c.end_page                    AS end_page,
        LEFT(c.content, 300)          AS preview,
        (ce.embedding <-> {qarr_sql}) AS dist,
        CASE
          WHEN LOWER(c.content) LIKE %s THEN 1
          ELSE 0
        END                           AS lexical_hit
      FROM chunk_embeddings ce
      JOIN document_chunks c ON c.id = ce.chunk_id
      LEFT JOIN documents d  ON d.id = c.document_id
      WHERE {where_sql}
    ),
    scored AS (
      SELECT
        *,
        (dist - {boost_coef} * lexical_hit) AS combined
      FROM rank_by
    ),
    best_per_section AS (
      SELECT *, ROW_NUMBER() OVER (
        PARTITION BY document_id, COALESCE(section_path, '')
        ORDER BY combined ASC, dist ASC, chunk_id ASC
      ) AS rn
      FROM scored
    ),
    final AS (
      SELECT
        chunk_id, dist, document_id, document_title, source_url, section_path,
        chunk_index, start_page, end_page, preview, lexical_hit, combined
      FROM best_per_section
      WHERE rn = 1
      ORDER BY
        combined ASC,
        dist ASC,
        lexical_hit DESC,
        chunk_id ASC
      LIMIT %s::int OFFSET %s::int
    )
    SELECT * FROM final;
    """.strip()

    # For debug visibility
    debug: Dict[str, Any] = {
        "sql_first": re.sub(r"\s+", " ", sql_full.strip()),
        "params_types_first": [type(p).__name__ for p in (params_for_like + params + [int(payload.top_k), int(payload.offset)])],
    }

    rows: List[Dict[str, Any]] = []
    try:
        with _get_conn() as conn, conn.cursor() as cur:
            full_params: Tuple[Any, ...] = tuple(
                params_for_like + params + [int(payload.top_k), int(payload.offset)]
            )
            cur.execute(sql_full, full_params)
            rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")

    # 5) Post-process results
    hi_fn = _mk_highlighter(payload.text) if payload.highlight_terms else None

    out_rows: List[Dict[str, Any]] = []
    for r in rows:
        start_page = r.get("start_page")
        src = r.get("source_url") or ""
        page_url = None
        if src and isinstance(start_page, int) and start_page > 0:
            page_url = f"{src}#page={start_page}"

        dist = float(r.get("dist") or 0.0)
        score = 1.0 / (1.0 + dist)

        preview_raw = r.get("preview") or ""
        preview_clean = normalize_text(preview_raw).replace("Â©", "©")
        preview_clean = "\n".join(
            ln for ln in preview_clean.splitlines() if not ln.strip().isdigit()
        )
        preview_clean = re.sub(r"[ \t]+", " ", preview_clean).strip()

        preview_marked = preview_clean
        if hi_fn:
            preview_marked = hi_fn(preview_marked)

        out_rows.append(
            {
                "chunk_id": r.get("chunk_id"),
                "dist": dist,
                "score": score,
                "document_id": r.get("document_id"),
                "document_title": r.get("document_title"),
                "source_url": src,
                "page_url": page_url,
                "section_path": r.get("section_path"),
                "chunk_index": r.get("chunk_index"),
                "start_page": start_page,
                "end_page": r.get("end_page"),
                "preview": preview_raw,
                "preview_clean": preview_clean if payload.clean_preview else None,
                "preview_marked": preview_marked if payload.highlight_terms else None,
            }
        )

    # 6) Pagination helper
    next_offset = payload.offset + len(out_rows) if len(out_rows) == payload.top_k else None

    return {
        "query": payload.text,
        "top_k": payload.top_k,
        "offset": payload.offset,
        "next_offset": next_offset,
        "document_filter": payload.document_id,
        "product_filter": payload.product_id,
        "results": out_rows,
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
    ORDER BY dist ASC
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
