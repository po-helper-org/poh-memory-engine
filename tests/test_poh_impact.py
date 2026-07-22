# tests/test_poh_impact.py
from poh_memory.impact import diff_snapshots


def _claim(cid, subject="s", aspect="a", value="v", polarity="neutral", grounded="node-x", **extra):
    d = {"id": cid, "subject": subject, "aspect": aspect, "value": value, "polarity": polarity,
         "grounded_node": grounded, "invalid_at": None, "expired_at": None, "superseded_by": None,
         "episode": "pulse-ep"}
    d.update(extra)
    return d


def _snap(nodes=(), edges=(), communities=None, kr_episodes=None, claims=()):
    return {"nodes": set(nodes), "edges": set(edges), "communities": dict(communities or {}),
            "kr_episodes": dict(kr_episodes or {}), "claims": list(claims)}


def test_new_node_and_connecting_edge():
    base = _snap(nodes=["kr-a", "sys-a"], edges=[("kr-a", "SERVES", "sys-a")])
    cand = _snap(nodes=["kr-a", "sys-a", "pulse-1"],
                 edges=[("kr-a", "SERVES", "sys-a"), ("pulse-1", "MENTIONS", "sys-a")])
    d = diff_snapshots(base, cand)
    assert d["new_nodes"] == ["pulse-1"]
    # edge touches pre-existing sys-a and new pulse-1 -> connecting
    assert ("pulse-1", "MENTIONS", "sys-a") in d["connecting_edges"]
    assert d["internal_new_edges"] == []


def test_internal_new_edge_between_two_new_nodes():
    base = _snap(nodes=["kr-a"])
    cand = _snap(nodes=["kr-a", "x", "y"], edges=[("x", "MENTIONS", "y")])
    d = diff_snapshots(base, cand)
    assert ("x", "MENTIONS", "y") in d["internal_new_edges"]
    assert d["connecting_edges"] == []


def test_new_claim_and_contradiction():
    base = _snap(claims=[_claim("c1", polarity="positive")])
    cand = _snap(claims=[_claim("c1", polarity="positive"), _claim("c2", polarity="negative")])
    d = diff_snapshots(base, cand)
    assert [c["id"] for c in d["new_claims"]] == ["c2"]
    # c1(pos) vs c2(neg) same node-x/aspect-a -> contradiction pair involving new c2
    assert len(d["new_contradiction_pairs"]) == 1


def test_newly_superseded():
    base = _snap(claims=[_claim("c1")])
    cand = _snap(claims=[_claim("c1", invalid_at="2026-07-09", superseded_by="c2")])
    d = diff_snapshots(base, cand)
    assert [c["id"] for c in d["newly_superseded"]] == ["c1"]


def test_kr_coverage_delta():
    base = _snap(kr_episodes={"kr-a": ["ep1"]})
    cand = _snap(kr_episodes={"kr-a": ["ep1", "ep2"]})
    d = diff_snapshots(base, cand)
    assert d["kr_coverage_delta"] == {"kr-a": {"gained": ["ep2"], "lost": []}}


def test_empty_diff_when_identical():
    s = _snap(nodes=["a"], edges=[("a", "SERVES", "a")], claims=[_claim("c1")])
    d = diff_snapshots(s, s)
    assert d["new_nodes"] == [] and d["new_claims"] == [] and d["kr_coverage_delta"] == {}


import pathlib as _pl
from falkordb import FalkorDB
import poh_memory.ingest as _ing
from poh_memory.ingest import ingest
from poh_memory.impact import graph_snapshot
from poh_memory.client import FALKOR_HOST, FALKOR_PORT

_GRAPH = "poh_impact_snapshot_test"


def test_graph_snapshot_integration(monkeypatch):
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(_GRAPH).query("MATCH (n) DETACH DELETE n")
    monkeypatch.setattr(_ing, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES"),
                                                           ("pulse-1", "sys-a", "MENTIONS")])
    monkeypatch.setattr(_ing, "node_titles", lambda r: {})
    monkeypatch.setattr(_ing, "episode_claims", lambda r: [])
    ingest(_pl.Path("."), _GRAPH, ingest_at="2026-07-12")
    snap = graph_snapshot(_GRAPH, _pl.Path("."))
    assert "kr-a" in snap["nodes"] and "sys-a" in snap["nodes"]
    assert ("kr-a", "SERVES", "sys-a") in snap["edges"]
    assert "kr-a" in snap["kr_episodes"]           # KR node present -> PPR ran
    assert all(v for v in snap["communities"].values())
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(_GRAPH).query("MATCH (n) DETACH DELETE n")
