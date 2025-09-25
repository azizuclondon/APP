"""
app/embedder_openai.py
OpenAI embeddings provider (standalone, not yet wired into get_embedder()).

Safe to keep alongside the fake provider. Only used when we later import and
explicitly select it (we won't do that yet).
"""

from __future__ import annotations
from typing import List
import os
import json
import httpx

EMBED_DIM = 1536  # matches your pgvector schema

class OpenAIEmbedder:
    """
    Real embeddings via OpenAI REST API.

    Env vars (only needed when we actually enable it later):
        OPENAI_API_KEY           - required (not placeholder)
        EMBEDDING_MODEL          - default 'text-embedding-3-small' (1536 dims)
        OPENAI_BASE_URL (opt)    - override base URL if using Azure/proxy
        OPENAI_TIMEOUT_SECONDS   - default 40
        OPENAI_BATCH_SIZE        - default 64
    """
    name = "openai"
    dim = EMBED_DIM

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        # We intentionally do NOT raise here while setting up,
        # because we might import this class without using it yet.
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "40"))
        self.batch_size = int(os.getenv("OPENAI_BATCH_SIZE", "64"))
        if self.batch_size < 1:
            self.batch_size = 1

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if not self.api_key or self.api_key.strip() in {"", "<PUT_YOUR_KEY_HERE>"}:
            raise RuntimeError("OPENAI_API_KEY is not set (or placeholder).")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/embeddings"

        out: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            payload = {"model": self.model, "input": batch}

            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, data=json.dumps(payload))

            if resp.status_code != 200:
                raise RuntimeError(
                    f"OpenAI embeddings failed (HTTP {resp.status_code}): {resp.text[:500]}"
                )

            data = resp.json()
            vectors = [d["embedding"] for d in data.get("data", [])]

            # Validate shape to protect DB inserts later
            for v in vectors:
                if len(v) != self.dim:
                    raise RuntimeError(
                        f"Embedding dim mismatch: got {len(v)}, expected {self.dim}. "
                        "Use a 1536-dim model like 'text-embedding-3-small' "
                        "or change the DB schema."
                    )

            out.extend(vectors)

        return out
