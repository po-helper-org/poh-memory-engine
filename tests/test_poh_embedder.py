import asyncio
from poh_memory.embedder import BgeM3Embedder, DIM


def test_embed_dim_and_determinism():
    emb = BgeM3Embedder()
    v1 = asyncio.run(emb.create("каталог кино на витрине"))
    v2 = asyncio.run(emb.create("каталог кино на витрине"))
    assert len(v1) == DIM
    assert v1 == v2  # детерминизм


def test_create_batch():
    emb = BgeM3Embedder()
    vs = asyncio.run(emb.create_batch(["B2B дистрибуция", "рекомендации фильмов"]))
    assert len(vs) == 2 and all(len(v) == DIM for v in vs)
