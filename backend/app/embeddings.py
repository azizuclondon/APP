"""
app/embeddings.py
Pluggable embedding interface.

- Start with a deterministic FAKE provider (no network, no API keys).
- Later we’ll add a real provider (e.g., OpenAI) behind the same interface.

Public API you can import elsewhere:
    get_embedder() -> Embedder
    embed_one(text: str) -> list[float]
    embed_texts(texts: list[str]) -> list[list[float]]

All vectors are length 1536 to match your pgvector schema.
"""

from __future__ import annotations
from typing import List, Protocol, Literal
import os
import math
import hashlib
import struct

EMBED_DIM = 1536
ProviderName = Literal["fake", "openai"]  # we’ll add "openai" later


class Embedder(Protocol):
    """Simple protocol for interchangeable embedders."""
    name: str
    dim: int

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        ...


# -----------------------------
# FAKE provider (deterministic)
# -----------------------------
class FakeEmbedder:
    """
    Deterministic, offline embeddings.
    - Uses SHA256(text|i) per dimension.
    - Normalized to unit length.
    - Stable across runs and machines.
    """
    name = "fake-1536"
    dim = EMBED_DIM

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> List[float]:
        vals: List[float] = []
        for i in range(self.dim):
            h = hashlib.sha256(f"{text}|{i}".encode("utf-8")).digest()
            # Use first 4 bytes as unsigned int -> map to [-1, 1)
            num = struct.unpack("I", h[:4])[0]
            x = (num / 2**32) * 2.0 - 1.0
            vals.append(x)
        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]


# -----------------------------------
# Provider selection & convenience API
# -----------------------------------
def get_embedder() -> Embedder:
    """
    Select provider by EMB_PROVIDER env var (defaults to 'fake').
    Future: add OpenAI when ready.
    """
    provider: ProviderName = (os.getenv("EMB_PROVIDER") or "fake").lower()  # type: ignore
    if provider == "fake":
        return FakeEmbedder()
    # Placeholder for future real provider:
    if provider == "openai":
        raise NotImplementedError(
            "OpenAI provider not wired yet. We'll add this in the next steps."
        )
    # Fallback
    return FakeEmbedder()


def embed_one(text: str) -> List[float]:
    return get_embedder().embed_texts([text])[0]


def embed_texts(texts: List[str]) -> List[List[float]]:
    return get_embedder().embed_texts(texts)
