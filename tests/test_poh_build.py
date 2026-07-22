# tests/test_poh_build.py
import pathlib
from falkordb import FalkorDB
import poh_memory.build as build_mod
from poh_memory.build import build_graph
from poh_memory.client import FALKOR_HOST, FALKOR_PORT

GRAPH = "poh_build_test"
DUMMY = pathlib.Path(".")


def _patch(monkeypatch, edges):
    import poh_memory.ingest as ing_mod
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda root: list(edges))
    monkeypatch.setattr(ing_mod, "node_titles", lambda root: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda root: [])


def test_build_graph_success(monkeypatch):
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")
    _patch(monkeypatch, [("kr-a", "sys-a", "SERVES"), ("kr-b", "sys-b", "SERVES")])
    res = build_graph(DUMMY, "2026-07-12", graph_name=GRAPH)
    assert res["ok"] is True
    assert res["entities"] == 4
    assert res["communities"] >= 1
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def test_build_graph_connection_fail_returns_error(monkeypatch):
    _patch(monkeypatch, [])
    res = build_graph(DUMMY, "2026-07-12", graph_name=GRAPH, port=1)  # nothing on port 1
    assert res["ok"] is False
    assert "error" in res


def test_build_graph_clean_rebuild_no_stale_accumulation(monkeypatch):
    # первый build: 2 рёбра / 4 узла
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")
    _patch(monkeypatch, [("kr-a", "sys-a", "SERVES"), ("kr-b", "sys-b", "SERVES")])
    r1 = build_graph(DUMMY, "2026-07-12", graph_name=GRAPH)
    assert r1["entities"] == 4
    # второй build с ДРУГИМ (меньшим) контентом: 1 ребро / 2 узла.
    # без drop-first старые kr-b/sys-b осели бы -> 4; с drop-first -> ровно 2.
    _patch(monkeypatch, [("kr-a", "sys-a", "SERVES")])
    r2 = build_graph(DUMMY, "2026-07-13", graph_name=GRAPH)
    assert r2["entities"] == 2   # чистая пересборка отражает только текущий контент
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")
