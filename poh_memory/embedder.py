"""Локальный bge-m3 эмбеддер как graphiti EmbedderClient (RU-first, zero-key).

EmbedderClient требует реализовать create() и create_batch() (подтверждено интроспекцией).
bge-m3: dim 1024, топ ruMTEB retrieval, Apache-2, CPU. Первый вызов качает ~2.2GB.
"""
from __future__ import annotations
from functools import lru_cache
from graphiti_core.embedder import EmbedderClient

MODEL_NAME = "BAAI/bge-m3"
DIM = 1024


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def _encode(texts: list[str]) -> list[list[float]]:
    vecs = _model().encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


class BgeM3Embedder(EmbedderClient):
    """Pluggable локальный эмбеддер. Свап на другой = замена этого класса."""

    async def create(self, input_data):
        # Graphiti-контракт: create() -> ОДИН вектор (даже если input обёрнут в список).
        # Множественные эмбеддинги — через create_batch.
        texts = input_data if isinstance(input_data, list) else [input_data]
        return _encode([str(t) for t in texts])[0]

    async def create_batch(self, input_data_list):
        return _encode([str(t) for t in input_data_list])
