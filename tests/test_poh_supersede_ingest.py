# tests/test_poh_supersede_ingest.py
import pathlib
from falkordb import FalkorDB
import poh_memory.ingest as ing_mod
from poh_memory.ingest import ingest
from poh_memory.query import _load_graph
from poh_memory.client import FALKOR_HOST, FALKOR_PORT

GRAPH = "poh_supersede_ingest_test"
DUMMY = pathlib.Path(".")  # не читается: semantic_edges/node_titles замоканы


def _reset():
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def _invalid_at(src, etype, dst):
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    rows = g.query(
        f"MATCH (:Entity {{name:$s}})-[r:{etype}]->(:Entity {{name:$d}}) RETURN r.invalid_at",
        {"s": src, "d": dst},
    ).result_set
    return rows[0][0] if rows else "MISSING"


def _patch_edges(monkeypatch, edges):
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda root: list(edges))
    monkeypatch.setattr(ing_mod, "node_titles", lambda root: {})


def test_removed_edge_invalidated_at_build_time(monkeypatch):
    _reset()
    _patch_edges(monkeypatch, [("kr-x", "system-y", "SERVES")])   # (src, dst, etype) как отдаёт semantic_edges
    ingest(DUMMY, GRAPH, ingest_at="2026-01-01")                   # билд1: ребро есть
    assert _invalid_at("kr-x", "SERVES", "system-y") is None
    _patch_edges(monkeypatch, [])                                  # билд2: ребро исчезло
    ingest(DUMMY, GRAPH, ingest_at="2026-02-01")
    assert _invalid_at("kr-x", "SERVES", "system-y") == "2026-02-01"


def test_reactivation_clears_invalid_at(monkeypatch):
    _reset()
    _patch_edges(monkeypatch, [("kr-x", "system-y", "SERVES")])
    ingest(DUMMY, GRAPH, ingest_at="2026-01-01")
    _patch_edges(monkeypatch, [])
    ingest(DUMMY, GRAPH, ingest_at="2026-02-01")                   # инвалидировано
    assert _invalid_at("kr-x", "SERVES", "system-y") == "2026-02-01"
    _patch_edges(monkeypatch, [("kr-x", "system-y", "SERVES")])    # снова утверждено
    ingest(DUMMY, GRAPH, ingest_at="2026-03-01")
    assert _invalid_at("kr-x", "SERVES", "system-y") is None       # реактивировано


def test_ingest_at_none_skips_reconciliation(monkeypatch):
    _reset()
    _patch_edges(monkeypatch, [("kr-x", "system-y", "SERVES")])
    ingest(DUMMY, GRAPH, ingest_at="2026-01-01")
    _patch_edges(monkeypatch, [])
    ingest(DUMMY, GRAPH, ingest_at=None)                           # реконсиляция пропущена
    assert _invalid_at("kr-x", "SERVES", "system-y") is None       # НЕ инвалидировано


def test_asof_sees_removed_edge_before_build(monkeypatch):
    # сцепка с #1: as-of ДО билда2 видит ребро, current — нет
    _reset()
    _patch_edges(monkeypatch, [("kr-x", "system-y", "SERVES")])
    ingest(DUMMY, GRAPH, ingest_at="2026-01-01")
    _patch_edges(monkeypatch, [])
    ingest(DUMMY, GRAPH, ingest_at="2026-02-01")
    before = _load_graph(GRAPH, as_of="2026-01-15")                # до границы
    current = _load_graph(GRAPH)                                   # as_of=None -> текущее
    assert before.has_edge("kr-x", "system-y")
    assert not current.has_edge("kr-x", "system-y")
