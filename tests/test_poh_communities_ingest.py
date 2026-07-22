# tests/test_poh_communities_ingest.py
import pathlib
from falkordb import FalkorDB
import poh_memory.ingest as ing_mod
from poh_memory.ingest import ingest
from poh_memory.client import FALKOR_HOST, FALKOR_PORT

GRAPH = "poh_communities_ingest_test"
DUMMY = pathlib.Path(".")


def _reset():
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def _g():
    return FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)


def _patch(monkeypatch, edges, claims):
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda root: list(edges))
    monkeypatch.setattr(ing_mod, "node_titles", lambda root: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda root: list(claims))


def _claim(cid, episode, grounded=None):
    return {"id": cid, "subject": "s", "aspect": "a", "value": "v", "polarity": "neutral",
            "speaker": None, "grounded_node": grounded, "confidence": None, "episode": episode,
            "invalid_at": None, "expired_at": None, "superseded_by": None}


def test_nodes_get_community_id_two_clusters(monkeypatch):
    _reset()
    # two disconnected KR->system pairs -> two communities
    _patch(monkeypatch, [("kr-a", "sys-a", "SERVES"), ("kr-b", "sys-b", "SERVES")], [])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-12")
    rows = _g().query(
        "MATCH (n:Entity) RETURN n.name, n.community_id ORDER BY n.name"
    ).result_set
    cid = {name: c for name, c in rows}
    assert cid["kr-a"] == cid["sys-a"]          # same cluster
    assert cid["kr-b"] == cid["sys-b"]
    assert cid["kr-a"] != cid["kr-b"]           # different clusters
    assert cid["kr-a"] == "kr-a"                # min-member id (kr-a < sys-a)


def test_claim_nodes_have_no_community_id(monkeypatch):
    _reset()
    _patch(monkeypatch, [("kr-a", "sys-a", "SERVES")],
           [_claim("claim-1", "pulse-ep", grounded="sys-a")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-12")
    rows = _g().query("MATCH (c:Claim {name:'claim-1'}) RETURN c.community_id").result_set
    assert rows[0][0] is None                   # claim-слой вне _load_graph -> метки нет


def test_reingest_stable_community_id(monkeypatch):
    _reset()
    _patch(monkeypatch, [("kr-a", "sys-a", "SERVES"), ("kr-b", "sys-b", "SERVES")], [])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-12")
    first = {n: c for n, c in _g().query("MATCH (n:Entity) RETURN n.name, n.community_id").result_set}
    ingest(DUMMY, GRAPH, ingest_at="2026-07-13")   # re-ingest
    second = {n: c for n, c in _g().query("MATCH (n:Entity) RETURN n.name, n.community_id").result_set}
    assert first == second                      # идемпотентно


from poh_memory.communities import blast_radius


def _seed_communities():
    g = _g()
    g.query("MATCH (n) DETACH DELETE n")
    # cluster "c1": a,b,c ; cluster "c2": x,y
    for n, cid in [("a", "c1"), ("b", "c1"), ("c", "c1"), ("x", "c2"), ("y", "c2")]:
        g.query("MERGE (n:Entity {name:$n}) SET n.community_id=$cid", {"n": n, "cid": cid})
    g.query("MERGE (n:Entity {name:'lonely'})")   # no community_id
    return g


def test_blast_radius_returns_co_community_sorted_without_self():
    _seed_communities()
    assert blast_radius(GRAPH, "a", host=FALKOR_HOST, port=FALKOR_PORT) == ["b", "c"]
    assert blast_radius(GRAPH, "x", host=FALKOR_HOST, port=FALKOR_PORT) == ["y"]


def test_blast_radius_missing_node_returns_empty():
    _seed_communities()
    assert blast_radius(GRAPH, "does-not-exist", host=FALKOR_HOST, port=FALKOR_PORT) == []


def test_blast_radius_node_without_community_returns_empty():
    _seed_communities()
    assert blast_radius(GRAPH, "lonely", host=FALKOR_HOST, port=FALKOR_PORT) == []


from poh_memory.query import _load_graph


def test_community_pass_does_not_change_ppr_graph(monkeypatch):
    _reset()
    _patch(monkeypatch, [("kr-a", "sys-a", "SERVES"), ("kr-b", "sys-b", "DELIVERS")], [])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-12")
    G = _load_graph(GRAPH)
    # community_id is a node property, not an edge -> PPR graph is exactly the 2 semantic edges
    assert G.number_of_edges() == 2
    assert G.has_edge("kr-a", "sys-a")
    assert G.has_edge("kr-b", "sys-b")
    # no SUPERSEDED_BY / community edges leaked in
    assert G.number_of_nodes() == 4
