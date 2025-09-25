CREATE TABLE IF NOT EXISTS document_toc (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    level INT NOT NULL,
    title TEXT NOT NULL,
    page_from INT NOT NULL,
    page_to INT,
    order_index INT NOT NULL,
    raw_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_toc_doc
    ON document_toc(document_id);
