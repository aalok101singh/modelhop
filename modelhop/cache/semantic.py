"""Local-embedding semantic cache (v1.1 W1).

Backed by fastembed/sentence-transformers when available ([cache] extra);
falls back to hashed token vectors so the default path stays zero-dependency.
Brute-force cosine search. Never stores raw text when policy forbids.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import List, Optional


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash_vector(text: str, dim: int = 128) -> List[float]:
    vec = [0.0] * dim
    for tok in _tokens(text):
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@dataclass
class SemanticEntry:
    vector: List[float]
    response: str
    model: str
    policy_version: str
    text_hash: str = ""


class SemanticCache:
    def __init__(self, threshold: float = 0.85, dim: int = 128, store_text: bool = True):
        self.threshold = threshold
        self.dim = dim
        self.store_text = store_text
        self.entries: List[SemanticEntry] = []
        self._embed = None
        self._try_load_embed()

    def _try_load_embed(self) -> None:
        try:
            from fastembed import TextEmbedding  # type: ignore

            self._embed = TextEmbedding()
            return
        except Exception:
            pass
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model = SentenceTransformer("all-MiniLM-L6-v2")
            self._embed = model
        except Exception:
            self._embed = None

    def _vector(self, text: str) -> List[float]:
        if self._embed is not None:
            try:
                # fastembed returns generator; sentence-transformers returns array.
                out = (
                    list(self._embed.embed([text]))
                    if hasattr(self._embed, "embed")
                    else self._embed.encode([text])
                )
                vec = list(out[0])
                norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                return [float(v) / norm for v in vec]
            except Exception:
                pass
        return _hash_vector(text, self.dim)

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (na * nb)

    def put(self, query: str, response: str, model: str, policy_version: str = "1") -> None:
        vec = self._vector(query)
        text_hash = hashlib.sha256(query.encode()).hexdigest()
        self.entries.append(
            SemanticEntry(
                vector=vec,
                response=response if self.store_text else "",
                model=model,
                policy_version=policy_version,
                text_hash=text_hash,
            )
        )

    def get(self, query: str, policy_version: Optional[str] = None) -> Optional[dict]:
        if not self.entries:
            return None
        vec = self._vector(query)
        best = None
        best_score = -1.0
        for entry in self.entries:
            if policy_version is not None and entry.policy_version != policy_version:
                continue
            score = self._cosine(vec, entry.vector)
            if score > best_score:
                best_score = score
                best = entry
        if best is not None and best_score >= self.threshold:
            return {"response": best.response, "model": best.model, "score": best_score}
        return None

    def invalidate(self) -> None:
        self.entries = []
