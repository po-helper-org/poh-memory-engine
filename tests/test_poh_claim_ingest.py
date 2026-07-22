# tests/test_poh_claim_ingest.py
import logging
import pathlib
from falkordb import FalkorDB
import poh_memory.ingest as ing_mod
from poh_memory.ingest import ingest
from poh_memory.query import _load_graph
from poh_memory.supersede import reconcile_edges
from poh_memory.client import FALKOR_HOST, FALKOR_PORT

GRAPH = "poh_claim_ingest_test"
DUMMY = pathlib.Path(".")


def _reset():
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def _g():
    return FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)


def _patch(monkeypatch, edges, claims):
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda root: list(edges))
    monkeypatch.setattr(ing_mod, "node_titles", lambda root: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda root: list(claims))


def _claim(cid, episode, subject="s", aspect="a", value="v", grounded=None,
           invalid_at=None, expired_at=None, superseded_by=None):
    return {"id": cid, "subject": subject, "aspect": aspect, "value": value,
            "polarity": "neutral", "speaker": None, "grounded_node": grounded,
            "confidence": None, "episode": episode,
            "invalid_at": invalid_at, "expired_at": expired_at, "superseded_by": superseded_by}


def test_claim_node_and_asserts_created(monkeypatch):
    _reset()
    _patch(monkeypatch, [], [_claim("claim-1", "pulse-2026-07-06-x")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-06")
    rows = _g().query(
        "MATCH (e:Entity {name:'pulse-2026-07-06-x'})-[:ASSERTS]->(c:Claim {name:'claim-1'}) "
        "RETURN c.subject, c.valid_at, c.invalid_at"
    ).result_set
    assert rows == [["s", "2026-07-06", None]]   # valid_at=дата эпизода, invalid_at=null


def test_grounded_claim_has_about_edge(monkeypatch):
    _reset()
    # спайн-узел system-y существует (семантич. ребро его создаёт)
    _patch(monkeypatch, [("kr-x", "system-y", "SERVES")],
           [_claim("claim-1", "pulse-ep", grounded="system-y")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-06")
    rows = _g().query(
        "MATCH (c:Claim {name:'claim-1'})-[:ABOUT]->(n:Entity {name:'system-y'}) RETURN n.name"
    ).result_set
    assert rows == [["system-y"]]


def test_ungrounded_claim_no_about(monkeypatch):
    _reset()
    _patch(monkeypatch, [], [_claim("claim-1", "pulse-ep", grounded="does-not-exist")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-06")
    rows = _g().query("MATCH (c:Claim {name:'claim-1'})-[:ABOUT]->() RETURN count(*)").result_set
    assert rows[0][0] == 0                        # узла нет -> ABOUT не создан


def test_claim_layer_excluded_from_ppr(monkeypatch):
    _reset()
    _patch(monkeypatch, [("kr-x", "system-y", "SERVES")],
           [_claim("claim-1", "pulse-ep", grounded="system-y")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-06")
    G = _load_graph(GRAPH)
    assert G.has_edge("kr-x", "system-y")
    assert "claim-1" not in G                      # изоляция end-to-end


def test_reconcile_does_not_touch_claim_edges(monkeypatch):
    _reset()
    _patch(monkeypatch, [("kr-x", "system-y", "SERVES")],
           [_claim("claim-1", "pulse-ep", grounded="system-y")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-06")
    # реконсиляция с asserted, НЕ содержащим claim-рёбер: не должна их инвалидировать
    reconcile_edges(_g(), {("kr-x", "SERVES", "system-y")}, "2026-08-01")
    rows = _g().query(
        "MATCH (:Entity {name:'pulse-ep'})-[r:ASSERTS]->(:Claim) RETURN r.invalid_at"
    ).result_set
    assert rows[0][0] is None                      # ASSERTS не инвалидировано (guard по _REL)


def test_claim_invalid_at_materialized(monkeypatch):
    _reset()
    _patch(monkeypatch, [], [_claim("claim-old", "pulse-ep",
                                    invalid_at="2026-07-09", superseded_by="claim-new")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-11")
    rows = _g().query(
        "MATCH (c:Claim {name:'claim-old'}) RETURN c.invalid_at, c.expired_at, c.superseded_by"
    ).result_set
    assert rows == [["2026-07-09", None, "claim-new"]]


def test_claim_expired_at_materialized(monkeypatch):
    _reset()
    _patch(monkeypatch, [], [_claim("claim-old", "pulse-ep",
                                    expired_at="2026-07-11", superseded_by="claim-new")])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-11")
    rows = _g().query(
        "MATCH (c:Claim {name:'claim-old'}) RETURN c.invalid_at, c.expired_at"
    ).result_set
    assert rows == [[None, "2026-07-11"]]


def test_superseded_by_edge_created_when_target_exists(monkeypatch):
    _reset()
    _patch(monkeypatch, [], [
        _claim("claim-new", "pulse-new"),
        _claim("claim-old", "pulse-old", invalid_at="2026-07-09", superseded_by="claim-new"),
    ])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-11")
    rows = _g().query(
        "MATCH (:Claim {name:'claim-old'})-[:SUPERSEDED_BY]->(:Claim {name:'claim-new'}) RETURN count(*)"
    ).result_set
    assert rows[0][0] == 1


def test_superseded_by_edge_skipped_and_no_phantom_when_target_absent(monkeypatch, caplog):
    _reset()
    _patch(monkeypatch, [], [_claim("claim-old", "pulse-old",
                                    invalid_at="2026-07-09", superseded_by="claim-ghost")])
    with caplog.at_level(logging.INFO, logger="poh_memory.ingest"):
        ingest(DUMMY, GRAPH, ingest_at="2026-07-11")
    # ребро не создано
    edge = _g().query("MATCH (:Claim {name:'claim-old'})-[:SUPERSEDED_BY]->() RETURN count(*)").result_set
    assert edge[0][0] == 0
    # фантомный узел claim-ghost НЕ наминчен (MATCH, не MERGE)
    ghost = _g().query("MATCH (c:Claim {name:'claim-ghost'}) RETURN count(c)").result_set
    assert ghost[0][0] == 0
    # skip log was emitted
    assert any("SUPERSEDED_BY edges skipped" in r.message for r in caplog.records)


def test_superseded_by_edge_excluded_from_ppr(monkeypatch):
    _reset()
    _patch(monkeypatch, [("kr-x", "system-y", "SERVES")], [
        _claim("claim-new", "pulse-new", grounded="system-y"),
        _claim("claim-old", "pulse-old", grounded="system-y",
               invalid_at="2026-07-09", superseded_by="claim-new"),
    ])
    ingest(DUMMY, GRAPH, ingest_at="2026-07-11")
    G = _load_graph(GRAPH)
    assert G.has_edge("kr-x", "system-y")
    assert "claim-new" not in G and "claim-old" not in G     # claim-слой и SUPERSEDED_BY вне PPR
