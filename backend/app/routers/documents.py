# app/routers/documents.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, AnyHttpUrl
from typing import Optional, List, Tuple, Dict, Any
import os
import json
import shutil
import urllib.request
import urllib.parse
from pathlib import Path
import time
import logging

from app.text_utils import normalize_text
from app.timing import timed_block
from app.embeddings import get_embedder, embed_texts  # <-- pluggable provider

import psycopg
from psycopg.rows import dict_row
from psycopg import errors as pg_errors
import fitz  # PyMuPDF  <-- used for TOC + page text extraction

# Router must be defined before any @router decorators
router = APIRouter(prefix="/admin/documents", tags=["documents"])
logger = logging.getLogger(__name__)

# --- DB connection helper ---
def get_conn():
    """
    Open a psycopg connection using the DATABASE_URL env var.
    Read the env each call so scripts that load .env later still work.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # default row_factory per-cursor; we set dict_row on cursor usages
    return psycopg.connect(url)

# --- Small util: make safe filenames for Windows ---
def _safe_filename(name: str) -> str:
    """
    Keep letters/digits, dash, underscore, dot; replace everything else with underscore.
    """
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)

def _split_by_paragraphs(text: str, max_chars: int) -> List[str]:
    """
    Split long text into chunks not exceeding max_chars, preferring paragraph
    boundaries (double newlines). No overlap by default.
    """
    if len(text) <= max_chars:
        return [text] if text else []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buf = ""
    for p in paras:
        if len(p) > max_chars:
            if buf:
                chunks.append(buf.strip())
                buf = ""
            for i in range(0, len(p), max_chars):
                chunks.append(p[i:i+max_chars].strip())
            continue
        if len(buf) + (2 if buf else 0) + len(p) <= max_chars:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            chunks.append(buf.strip())
            buf = p
    if buf:
        chunks.append(buf.strip())
    return chunks

# --- Pydantic input models ---
class DocumentIn(BaseModel):
    product_id: int
    source_url: AnyHttpUrl
    title: Optional[str] = None
    type: str = "pdf"  # keep simple for now

class LocalPathIn(BaseModel):
    local_path: str
    title: Optional[str] = None  # allow updating title if you want

# ---------------- Routes ----------------

@router.post("/url")
def register_document_url(payload: DocumentIn):
    """
    Register a document by URL.
    """
    title = payload.title or str(payload.source_url).rstrip("/").split("/")[-1] or "Untitled"
    sql = """
        INSERT INTO documents (product_id, title, source_url, type, uploaded_at)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING id, product_id, title, source_url, type, uploaded_at, local_path, full_text_path
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (payload.product_id, title, str(payload.source_url), payload.type))
                return cur.fetchone()
    except pg_errors.ForeignKeyViolation:
        raise HTTPException(status_code=400, detail="product_id does not exist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to insert document: {e}")

@router.get("/{doc_id}")
def get_document(doc_id: int):
    """
    Fetch a single document by id.
    """
    sql = """
        SELECT id, product_id, title, source_url, type, uploaded_at, local_path, full_text_path
        FROM documents
        WHERE id = %s
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (doc_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="document not found")
                return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch document: {e}")

@router.post("/{doc_id}/download")
def download_document(doc_id: int):
    """
    Download the document from source_url, save to storage/docs, and update local_path.
    """
    sql_get = """
        SELECT id, product_id, title, source_url, type
        FROM documents
        WHERE id = %s
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_get, (doc_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="document not found")

                source_url = row["source_url"]
                title = row["title"] or f"doc_{doc_id}"
                doc_type = (row["type"] or "pdf").lower()

                base_dir = Path(os.getenv("DOCS_DIR", "storage/docs")).resolve()
                base_dir.mkdir(parents=True, exist_ok=True)

                url_path = urllib.parse.urlparse(source_url).path
                url_suffix = Path(url_path).suffix
                if doc_type == "pdf":
                    ext = ".pdf"
                else:
                    ext = url_suffix if url_suffix else ".bin"

                fname = _safe_filename(title)
                if not fname.lower().endswith(ext.lower()):
                    fname = f"{fname}{ext}"

                dest_path = base_dir / fname

                try:
                    req = urllib.request.Request(
                        source_url,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:
                        out.write(resp.read())
                except Exception as dl_err:
                    raise HTTPException(status_code=502, detail=f"download failed: {dl_err}")

                sql_upd = """
                    UPDATE documents
                    SET local_path = %s
                    WHERE id = %s
                    RETURNING id, product_id, title, source_url, type, uploaded_at, local_path, full_text_path
                """
                with conn.cursor(row_factory=dict_row) as cur2:
                    cur2.execute(sql_upd, (str(dest_path), doc_id))
                    updated = cur2.fetchone()
                return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download/update document: {e}")

@router.post("/upload")
async def upload_document(
    product_id: int = Form(...),
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
):
    """
    Upload a local file (PDF) and create a document row with local_path.
    """
    original_name = file.filename or "uploaded"
    stem = Path(original_name).stem
    ext = (Path(original_name).suffix or "").lower()
    inferred_type = "pdf" if ext == ".pdf" else (ext.lstrip(".") if ext else "bin")

    final_title = title or (stem + (ext if ext else ""))
    safe_stem = _safe_filename(stem)
    base_dir = Path(os.getenv("DOCS_DIR", "storage/docs")).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    final_ext = ".pdf" if inferred_type == "pdf" else (ext if ext else ".bin")
    dest_name = safe_stem + final_ext
    dest_path = base_dir / dest_name

    try:
        with open(dest_path, "wb") as out:
            shutil.copyfileobj(file.file, out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed to save uploaded file: {e}")

    sql = """
        INSERT INTO documents (product_id, title, source_url, type, uploaded_at, local_path)
        VALUES (%s, %s, %s, %s, NOW(), %s)
        RETURNING id, product_id, title, source_url, type, uploaded_at, local_path, full_text_path
    """
    synthetic_source = f"uploaded://{dest_name}"

    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    sql,
                    (product_id, final_title, synthetic_source, inferred_type, str(dest_path)),
                )
                return cur.fetchone()
    except pg_errors.ForeignKeyViolation:
        raise HTTPException(status_code=400, detail="product_id does not exist")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to insert uploaded document: {e}")

@router.post("/{doc_id}/set-local-path")
def set_local_path(doc_id: int, payload: LocalPathIn):
    """
    Admin helper: set documents.local_path (and optionally title).
    """
    lp = payload.local_path
    if not Path(lp).exists():
        raise HTTPException(status_code=400, detail=f"local_path does not exist on disk: {lp}")

    if payload.title:
        sql = """
            UPDATE documents
            SET local_path = %s, title = %s
            WHERE id = %s
            RETURNING id, product_id, title, source_url, type, uploaded_at, local_path, full_text_path
        """
        params = (lp, payload.title, doc_id)
    else:
        sql = """
            UPDATE documents
            SET local_path = %s
            WHERE id = %s
            RETURNING id, product_id, title, source_url, type, uploaded_at, local_path, full_text_path
        """
        params = (lp, doc_id)

    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="document not found")
                return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set local_path: {e}")

# --------- TOC (on-the-fly from PDF) ----------
@router.get("/{doc_id}/toc")
def get_document_toc(doc_id: int):
    """
    Read the PDF at documents.local_path and return the TOC.
    """
    sql = "SELECT id, title, local_path FROM documents WHERE id = %s"
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (doc_id,))
                doc_row = cur.fetchone()
                if not doc_row:
                    raise HTTPException(status_code=404, detail="document not found")
                local_path = doc_row["local_path"]
                if not local_path:
                    raise HTTPException(status_code=400, detail="local_path is empty; set it first")
                if not Path(local_path).exists():
                    raise HTTPException(status_code=400, detail=f"local_path not found on disk: {local_path}")

        try:
            pdf = fitz.open(local_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"failed to open PDF: {e}")

        toc = pdf.get_toc(simple=False)  # list of [level, title, page]
        pdf.close()

        if not toc:
            return {"document_id": doc_id, "title": doc_row["title"], "toc": []}

        items = []
        for entry in toc:
            level = int(entry[0]) if len(entry) > 0 else 1
            title = str(entry[1]).strip() if len(entry) > 1 else ""
            page = int(entry[2]) if len(entry) > 2 else 1
            items.append({"level": level, "title": title, "page_number": page})

        return {"document_id": doc_id, "title": doc_row["title"], "toc": items}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read TOC: {e}")

# --------- Store TOC to DB ----------
@router.post("/{doc_id}/store-toc")
def store_document_toc(doc_id: int):
    """
    Read the PDF's TOC and persist it into document_toc.
    """
    sql_doc = "SELECT id, title, local_path FROM documents WHERE id = %s"
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_doc, (doc_id,))
                doc = cur.fetchone()
                if not doc:
                    raise HTTPException(status_code=404, detail="document not found")

        lp = doc["local_path"]
        if not lp or not Path(lp).exists():
            raise HTTPException(status_code=400, detail="valid local_path required")

        try:
            pdf = fitz.open(lp)
            toc = pdf.get_toc(simple=False) or []
            pdf.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"failed to open/read PDF: {e}")

        if not toc:
            return {"document_id": doc_id, "stored": 0, "note": "No TOC found in PDF."}

        rows = []
        for i, entry in enumerate(toc, start=1):
            level = int(entry[0]) if len(entry) > 0 else 1
            title = str(entry[1]).strip() if len(entry) > 1 else ""
            page_from = int(entry[2]) if len(entry) > 2 else 1
            rows.append((doc_id, level, title, page_from, None, i, None))

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_toc WHERE document_id = %s", (doc_id,))
                cur.executemany("""
                    INSERT INTO document_toc
                      (document_id, level, title, page_from, page_to, order_index, raw_path)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, rows)
            conn.commit()

        return {"document_id": doc_id, "stored": len(rows)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store TOC: {e}")

# --------- Read stored TOC ----------
@router.get("/{doc_id}/toc-db")
def get_stored_toc(doc_id: int, limit: int = 2000):
    """
    List the TOC previously stored in document_toc for this document.
    """
    sql = """
        SELECT level, title, page_from, page_to, order_index, created_at
        FROM document_toc
        WHERE document_id = %s
        ORDER BY order_index ASC
        LIMIT %s
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (doc_id, limit))
                rows = cur.fetchall()
        return {"document_id": doc_id, "count": len(rows), "toc": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read stored TOC: {e}")

# --------- Parse pages (with normalization) ----------
@router.post("/{doc_id}/parse-pages")
def parse_pages(doc_id: int):
    """
    Extract plain text page-by-page from the PDF and upsert into document_pages.
    Uses normalize_text() to clean mojibake/whitespace.
    Returns stats + small previews.
    """
    # 1) Find the PDF path
    sql_get = "SELECT id, title, local_path FROM documents WHERE id = %s"
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_get, (doc_id,))
                doc_row = cur.fetchone()
                if not doc_row:
                    raise HTTPException(status_code=404, detail="document not found")

        local_path = doc_row["local_path"]
        if not local_path:
            raise HTTPException(status_code=400, detail="local_path is empty; set it first")
        if not Path(local_path).exists():
            raise HTTPException(status_code=400, detail=f"local_path not found: {local_path}")

        # 2) Open PDF and extract text per page
        try:
            pdf = fitz.open(local_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"failed to open PDF: {e}")

        with timed_block("parse-pages"):
            records = []
            empty_pages = 0
            for i, page in enumerate(pdf, start=1):
                text = page.get_text("text") or ""
                text = text.replace("\x00", "")
                text = normalize_text(text)
                if not text.strip():
                    empty_pages += 1
                records.append((doc_id, i, text))
            pdf.close()

        # 3) Upsert into document_pages
        upsert_sql = """
            INSERT INTO document_pages (document_id, page_number, content)
            VALUES (%s, %s, %s)
            ON CONFLICT (document_id, page_number)
            DO UPDATE SET content = EXCLUDED.content
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(upsert_sql, records)
                conn.commit()

        # 4) Small previews
        previews = []
        for (_, p, txt) in records[:3]:
            previews.append({"page_number": p, "preview": (txt[:300] + ("…" if len(txt) > 300 else ""))})

        return {
            "document_id": doc_id,
            "title": doc_row["title"],
            "pages_total": len(records),
            "pages_empty": empty_pages,
            "previews": previews,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse pages: {e}")

# --------- Chunk by stored TOC ----------
@router.post("/{doc_id}/chunk-toc")
def chunk_by_toc(doc_id: int, max_chars: int = 2000):
    """
    Build section chunks using the STORED TOC (document_toc) + cleaned page text (document_pages).
    - For each TOC entry, compute its page range (until the next entry of same-or-higher level).
    - Concatenate the text of those pages from document_pages.
    - If the section text exceeds max_chars, split it into multiple chunks on paragraph boundaries.
    - Upsert into document_chunks (document_id, section_path, chunk_index) as unique key.
    """
    try:
        # 1) Get document + PDF page_count (to bound ranges)
        sql_get_doc = "SELECT id, title, local_path FROM documents WHERE id = %s"
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_get_doc, (doc_id,))
                doc_row = cur.fetchone()
                if not doc_row:
                    raise HTTPException(status_code=404, detail="document not found")
                local_path = doc_row["local_path"]
                if not local_path or not Path(local_path).exists():
                    raise HTTPException(status_code=400, detail="valid local_path required")

        try:
            pdf = fitz.open(local_path)
            page_count = pdf.page_count
            pdf.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"failed to open PDF: {e}")

        # 2) Read STORED TOC (ordered)
        sql_toc = """
            SELECT level, title, page_from, order_index
            FROM document_toc
            WHERE document_id = %s
            ORDER BY order_index ASC
        """
        entries: List[Tuple[int, str, int, int]] = []
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_toc, (doc_id,))
                for r in cur.fetchall():
                    entries.append((int(r["level"]), (r["title"] or "").strip(), int(r["page_from"]), int(r["order_index"])))

        if not entries:
            return {"document_id": doc_id, "title": doc_row["title"], "chunks_created": 0, "note": "No stored TOC found. Run /store-toc first."}

        # 3) Compute page ranges by "next same-or-higher"
        ranges: List[Tuple[int, str, int, int, int]] = []
        for idx, (lvl, title, start, oi) in enumerate(entries):
            end = page_count
            for j in range(idx + 1, len(entries)):
                nlvl, _, nstart, _ = entries[j]
                if nlvl <= lvl:
                    end = max(nstart - 1, start)
                    break
            ranges.append((lvl, title, start, end, oi))

        # 4) Build hierarchical section paths
        paths: List[str] = []
        stack: List[str] = []
        for lvl, title, _, _, _ in ranges:
            if len(stack) < lvl:
                stack += [""] * (lvl - len(stack))
            stack = stack[:lvl]
            stack[lvl - 1] = title
            paths.append(" > ".join(s for s in stack if s))

        # 5) Page text map
        sql_pages = "SELECT page_number, content FROM document_pages WHERE document_id = %s"
        page_map = {}
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql_pages, (doc_id,))
                for row in cur.fetchall():
                    page_map[int(row["page_number"])] = row["content"] or ""

        # 6) Build chunks + upsert (timed)
        with timed_block("chunk-toc"):
            chunks_rows = []
            total_sections = 0
            total_chunks = 0
            for (lvl, title, start, end, oi), section_path in zip(ranges, paths):
                total_sections += 1
                pages_text = [page_map[p] for p in range(start, end + 1) if p in page_map]
                full_text = "\n\n".join(pages_text).strip()
                if not full_text:
                    continue

                pieces = _split_by_paragraphs(full_text, max_chars=max_chars)
                for ci, piece in enumerate(pieces):
                    chunks_rows.append((doc_id, section_path, lvl, start, end, ci, piece))
                    total_chunks += 1

            if not chunks_rows:
                return {"document_id": doc_id, "title": doc_row["title"], "chunks_created": 0, "note": "No text found for TOC ranges. Ensure /parse-pages ran."}

            # Upsert into document_chunks
            upsert = """
                INSERT INTO document_chunks
                    (document_id, section_path, level, start_page, end_page, chunk_index, content)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, section_path, chunk_index)
                DO UPDATE SET
                    level = EXCLUDED.level,
                    start_page = EXCLUDED.start_page,
                    end_page = EXCLUDED.end_page,
                    content = EXCLUDED.content
            """
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.executemany(upsert, chunks_rows)
                    conn.commit()

        # 7) Sample preview
        sample = []
        for row in chunks_rows[:3]:
            _, section_path, lvl, start, end, ci, content = row
            sample.append({
                "section_path": section_path,
                "level": lvl,
                "range": f"{start}-{end}",
                "chunk_index": ci,
                "preview": content[:300] + ("…" if len(content) > 300 else "")
            })

        return {
            "document_id": doc_id,
            "title": doc_row["title"],
            "sections_seen": total_sections,
            "chunks_created": total_chunks,
            "sample": sample
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to chunk by TOC: {e}")

# --------- Export chunks to files ----------
@router.post("/{doc_id}/export-chunks")
def export_chunks_to_files(doc_id: int):
    """
    Export all chunks for a document to the filesystem:
      - storage/chunks/doc_<id>/<NNNN>__<safe_section>__ci_<k>.txt  (one file per chunk)
      - storage/chunks/doc_<id>/chunks.json                         (summary index)
    """
    sql = """
        SELECT id, document_id, section_path, level, start_page, end_page, chunk_index, content, created_at
        FROM document_chunks
        WHERE document_id = %s
        ORDER BY section_path ASC, chunk_index ASC
    """
    try:
        with get_conn() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, (doc_id,))
                rows = cur.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No chunks found for this document. Run /chunk-toc first.")

        base_dir = Path("storage/chunks").resolve()
        out_dir = base_dir / f"doc_{doc_id}"
        out_dir.mkdir(parents=True, exist_ok=True)

        def _safe(name: str) -> str:
            return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)

        with timed_block("export-chunks"):
            index = []
            for i, r in enumerate(rows, start=1):
                sid = int(r["id"])
                sec = r["section_path"] or "section"
                lvl = int(r["level"])
                sp, ep = int(r["start_page"]), int(r["end_page"])
                ci = int(r["chunk_index"])
                txt = r["content"] or ""

                safe = _safe(sec)[:80] or "section"
                fname = f"{i:04d}__{safe}__ci_{ci}.txt"
                fpath = out_dir / fname

                header = (
                    f"--- chunk_id: {sid}\n"
                    f"--- section_path: {sec}\n"
                    f"--- level: {lvl}\n"
                    f"--- pages: {sp}-{ep}\n"
                    f"--- chunk_index: {ci}\n"
                    f"---\n\n"
                )
                fpath.write_text(header + txt, encoding="utf-8")

                index.append({
                    "file": str(fpath),
                    "chunk_id": sid,
                    "section_path": sec,
                    "level": lvl,
                    "start_page": sp,
                    "end_page": ep,
                    "chunk_index": ci,
                    "chars": len(txt)
                })

            (out_dir / "chunks.json").write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

        return {
            "document_id": doc_id,
            "dir": str(out_dir),
            "files_written": len(index),
            "index_json": str(out_dir / "chunks.json")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export chunks: {e}")

# --------- NEW: Embed all chunks for one document ----------
def _upsert_embedding(conn, chunk_id: int, vec: List[float], model_name: str) -> None:
    """
    Upsert helper for chunk_embeddings table.
    """
    # --- SAFETY CHECK: prevent wrong-dimension vectors from being saved ---
    if len(vec) != 1536:
        raise RuntimeError(
            f"Refusing to save embedding of length {len(vec)} (expected 1536). "
            "Check EMBEDDING_MODEL."
        )

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

@router.post("/{document_id}/embed")
def embed_document(document_id: int, batch_size: int = 32) -> Dict[str, Any]:
    """
    Embed all chunks for a document in batches and upsert into chunk_embeddings.

    Returns a summary {total_chunks, embedded, skipped, provider, dim, elapsed_ms}.
    """
    provider_name = get_embedder().name
    t0 = time.perf_counter()
    embedded = 0
    skipped = 0
    total = 0

    with timed_block("embed_document"), get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Fetch chunk ids + text for this document
            cur.execute(
                """
                SELECT id, content
                FROM document_chunks
                WHERE document_id = %s
                ORDER BY id ASC
                """,
                (document_id,),
            )
            rows: List[Dict[str, Any]] = cur.fetchall()
            total = len(rows)

        if total == 0:
            raise HTTPException(status_code=404, detail=f"No chunks found for document {document_id}")

        # Prepare batches
        def batched(seq: List[Dict[str, Any]], n: int):
            for i in range(0, len(seq), n):
                yield seq[i : i + n]

        for batch in batched(rows, batch_size):
            # Filter out empty text
            batch_pairs: List[Tuple[int, str]] = [
                (int(r["id"]), (r.get("content") or ""))
                for r in batch
            ]
            ids = [cid for cid, txt in batch_pairs if txt.strip()]
            texts = [txt for cid, txt in batch_pairs if txt.strip()]
            empty_count = len(batch_pairs) - len(ids)
            skipped += empty_count

            if ids:
                vecs = embed_texts(texts)  # one call for the whole batch
                for cid, vec in zip(ids, vecs):
                    _upsert_embedding(conn, cid, vec, provider_name)
                embedded += len(ids)
                conn.commit()  # commit per batch to avoid long transactions
                logger.info("embed_document doc=%s batch_done embedded=%s skipped_in_batch=%s", document_id, len(ids), empty_count)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "document_id": document_id,
        "provider": provider_name,
        "dim": 1536,
        "total_chunks": total,
        "embedded": embedded,
        "skipped": skipped,
        "elapsed_ms": elapsed_ms,
        "saved": True,
    }
