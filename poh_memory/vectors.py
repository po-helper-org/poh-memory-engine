"""Вектор-seed: bge-m3 эмбеддинги узлов в LanceDB (embedded, локально).

Текст-запрос -> bge-m3 -> top-k узлов (семантический seed) -> отдаётся в PPR.
Индекс производный/пересбираемый (истина в спайне/FalkorDB). LanceDB локально.
"""
from __future__ import annotations
import pathlib
import lancedb
from poh_memory.embedder import _model
from poh_memory.edges import node_titles

INDEX_DIR = pathlib.Path("GROUND/_index/poh-lancedb")
TABLE = "poh_nodes"


def _embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _model().encode(texts, normalize_embeddings=True)]


def build_index(nexus_root: pathlib.Path, index_dir: pathlib.Path = INDEX_DIR):
    titles = node_titles(nexus_root)
    ids = list(titles)
    vecs = _embed([titles[i] for i in ids])
    db = lancedb.connect(str(index_dir))
    rows = [{"id": ids[i], "vector": vecs[i]} for i in range(len(ids))]
    db.create_table(TABLE, data=rows, mode="overwrite")
    return len(rows)


def seed_from_text(query_text: str, topk: int = 5,
                   index_dir: pathlib.Path = INDEX_DIR) -> dict[str, float]:
    """Текст -> {node_id: similarity} по top-k (для personalization PPR)."""
    qv = _embed([query_text])[0]
    tbl = lancedb.connect(str(index_dir)).open_table(TABLE)
    res = tbl.search(qv).limit(topk).to_list()
    # L2 на нормированных ~ 2-2cos -> similarity = 1 - d/2
    return {r["id"]: max(0.0, 1 - r["_distance"] / 2) for r in res}
