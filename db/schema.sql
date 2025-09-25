BEGIN;

-- Make sure pgvector is available (safe to run multiple times)
CREATE EXTENSION IF NOT EXISTS vector;

-- 1) Products
CREATE TABLE IF NOT EXISTS products (
  id           BIGSERIAL PRIMARY KEY,
  brand        TEXT        NOT NULL,
  model        TEXT        NOT NULL,
  description  TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (brand, model)
);

-- 2) Documents (per product)
CREATE TABLE IF NOT EXISTS documents (
  id           BIGSERIAL PRIMARY KEY,
  product_id   BIGINT      NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  source_url   TEXT,
  filename     TEXT,
  doc_type     TEXT,       -- e.g., "manual", "quickstart"
  version      TEXT,
  language     TEXT,
  page_count   INT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (product_id, source_url)
);
CREATE INDEX IF NOT EXISTS idx_documents_product_id ON documents(product_id);

-- 3) Chunks (text + embedding)
-- NOTE: 1536 dims fits common embedding models; adjust later if needed.
CREATE TABLE IF NOT EXISTS chunks (
  id           BIGSERIAL PRIMARY KEY,
  document_id  BIGINT      NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index  INT         NOT NULL,               -- 0,1,2... order in doc
  content      TEXT        NOT NULL,
  embedding    vector(1536),
  page_number  INT,
  section      TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
-- ANN index for fast similarity search (L2 distance)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
  ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- 4) Feedback (keep even if product/doc deleted)
CREATE TABLE IF NOT EXISTS feedback (
  id             BIGSERIAL PRIMARY KEY,
  product_id     BIGINT REFERENCES products(id)  ON DELETE SET NULL,
  document_id    BIGINT REFERENCES documents(id) ON DELETE SET NULL,
  user_email     TEXT,
  question       TEXT        NOT NULL,
  answer_summary TEXT,
  rating         INT CHECK (rating BETWEEN 1 AND 5),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5) Requests for unsupported products
CREATE TABLE IF NOT EXISTS requests (
  id          BIGSERIAL PRIMARY KEY,
  brand       TEXT        NOT NULL,
  model       TEXT        NOT NULL,
  user_email  TEXT,
  notes       TEXT,
  status      TEXT        NOT NULL DEFAULT 'new',  -- new|in_progress|done|cannot_find
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);

COMMIT;
