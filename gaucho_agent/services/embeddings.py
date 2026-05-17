"""Text embeddings for the memory layer.

Primary path: sentence-transformers MiniLM (`all-MiniLM-L6-v2`, 384-d, CPU).
Fallback: a deterministic hashing embedder so the test suite and demos run
with no torch install and no network — matching the project's offline-first
testing philosophy. Both paths emit L2-normalized float32 vectors of
`EMBED_DIM` so cosine similarity is a plain dot product.

The active backend is fixed for the lifetime of a database; never mix
MiniLM and fallback vectors in the same store.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

EMBED_DIM = 384
_TOKEN_RE = re.compile(r"[a-z0-9]+")

_model = None          # lazily-loaded SentenceTransformer
_backend: str | None = None  # "minilm" | "hash"


def _load_minilm():
    """Try to load MiniLM once. Returns the model or None if unavailable."""
    global _model, _backend
    if _backend is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer

        from gaucho_agent.config import settings

        _model = SentenceTransformer(settings.embedding_model)
        _backend = "minilm"
    except Exception:
        _model = None
        _backend = "hash"
    return _model


def active_backend() -> str:
    """Return the embedding backend in use: 'minilm' or 'hash'."""
    _load_minilm()
    return _backend or "hash"


def _hash_embed(text: str) -> np.ndarray:
    """Deterministic bag-of-hashed-tokens embedding (offline fallback).

    Positive term counts hashed into two buckets per token, then
    L2-normalized. Two hashes lower the chance that a collision cancels a
    genuine shared token; positive-only weights guarantee that lexical
    overlap never *reduces* cosine similarity. Good enough for heuristic
    retrieval and fully reproducible for tests.
    """
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    for tok in _TOKEN_RE.findall(text.lower()):
        h = hashlib.md5(tok.encode()).digest()
        i1 = int.from_bytes(h[:4], "little") % EMBED_DIM
        i2 = int.from_bytes(h[4:8], "little") % EMBED_DIM
        vec[i1] += 1.0
        vec[i2] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def embed(text: str) -> np.ndarray:
    """Return an L2-normalized float32 embedding for `text`."""
    model = _load_minilm()
    if model is not None:
        v = model.encode(text or "", normalize_embeddings=True)
        return np.asarray(v, dtype=np.float32)
    return _hash_embed(text or "")


def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> np.ndarray:
    if not blob:
        return np.zeros(EMBED_DIM, dtype=np.float32)
    return np.frombuffer(blob, dtype=np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity. Inputs are already normalized, but guard anyway."""
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return 0.0
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
