"""Embeddings for analog search (TZ 9.1). multilingual-e5-small on CPU; hash fallback offline.

The fallback is NOT a language model: a deterministic char-n-gram hashing vectorizer, used only
when sentence-transformers / the model weights are unavailable (see docs/KNOWN_ISSUES.md)."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Protocol

from app.config import get_settings

log = logging.getLogger("embeddings")


class Embedder(Protocol):
    name: str

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _l2(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class HashEmbedder:
    name = "hash-ngram-384"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        t = re.sub(r"\s+", " ", text.lower())
        toks = re.findall(r"[a-zа-я0-9.+]+", t)
        grams = list(toks)
        for tok in toks:
            grams += [tok[i : i + 3] for i in range(max(1, len(tok) - 2))]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
            v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
        return _l2(v)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class E5Embedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy, lazy

        self.name = model_name
        self._m = SentenceTransformer(model_name, device="cpu")

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        out = self._m.encode([f"passage: {t}" for t in texts], normalize_embeddings=True)
        return [list(map(float, r)) for r in out]

    def embed_query(self, text: str) -> list[float]:
        return list(map(float, self._m.encode(f"query: {text}", normalize_embeddings=True)))


_embedder: Embedder | None = None


def set_embedder(e: Embedder | None) -> None:
    global _embedder
    _embedder = e


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        try:
            _embedder = E5Embedder(get_settings().embedding_model)
        except Exception as exc:
            log.warning("e5 model unavailable (%s); using hash fallback", type(exc).__name__)
            _embedder = HashEmbedder(get_settings().embedding_dim)
    return _embedder


def cosine(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))
