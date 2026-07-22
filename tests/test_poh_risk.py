import pathlib as _pl
import pathlib
import networkx as nx
from falkordb import FalkorDB
import yaml as _yaml
import poh_memory.ingest as ing_mod
import poh_memory.risk as risk_mod
from poh_memory.ingest import ingest
from poh_memory.risk import severity, affected_krs, synthesize_risks, gate, _risk_id, write_queue, percentile_rank
from poh_memory.risk import materialize_risks, build_risk, blast_distribution
from poh_memory.query import _load_graph
from poh_memory.client import FALKOR_HOST, FALKOR_PORT


def test_percentile_rank_empty_dist_neutral():
    assert percentile_rank(5, []) == 0.5

def test_percentile_rank_all_equal_is_half():
    assert percentile_rank(3, [3, 3, 3, 3]) == 0.5

def test_percentile_rank_midrank_distribution():
    # value=3 in [1,2,3,3,5]: below=2, equal=2 -> (2 + 0.5*2)/5 = 0.6
    assert percentile_rank(3, [1, 2, 3, 3, 5]) == 0.6

def test_percentile_rank_min_and_max():
    # max value=5 in [1,2,3,3,5]: below=4, equal=1 -> (4+0.5)/5 = 0.9
    assert percentile_rank(5, [1, 2, 3, 3, 5]) == 0.9
    # below min: value=0 -> below=0, equal=0 -> 0.0
    assert percentile_rank(0, [1, 2, 3, 3, 5]) == 0.0

def test_percentile_rank_order_independent():
    assert percentile_rank(3, [5, 3, 1, 3, 2]) == percentile_rank(3, [1, 2, 3, 3, 5])


def test_severity_bounds_and_none():
    assert 0.0 <= severity(0, 0, None) <= 1.0
    assert severity(0, 0, None) == severity(0, 0, 0.5)   # None -> 0.5
    assert severity(100, 100, 0.0) == 1.0                 # clamped to 1.0


def test_severity_monotonic():
    base = severity(2, 1, 0.8)
    assert severity(5, 1, 0.8) >= base       # больше blast -> не меньше
    assert severity(2, 3, 0.8) >= base       # больше конфликтующих -> не меньше
    assert severity(2, 1, 0.2) >= base       # ниже уверенность заземления -> не меньше


def test_severity_legacy_path_unchanged():
    # blast_dist=None -> legacy blast/10: 0.5*min(5/10,1)+0.3*min(1/3,1)+0.2*(1-0.5)
    # = 0.5*0.5 + 0.3*0.3333 + 0.2*0.5 = 0.25 + 0.1 + 0.1 = 0.45
    assert severity(5, 1, 0.5) == 0.45


def test_severity_uses_percentile_when_dist_given():
    # blast=5, dist=[1,2,3,3,5] -> percentile 0.9; 0.5*0.9+0.3*0.3333+0.2*0.5
    # = 0.45 + 0.1 + 0.1 = 0.65
    assert severity(5, 1, 0.5, blast_dist=[1, 2, 3, 3, 5]) == 0.65


def test_severity_relative_same_blast_different_dist():
    # same blast=5, but in a graph where 5 is small vs large -> different severity
    high = severity(5, 1, 0.5, blast_dist=[1, 1, 2, 3, 5])   # 5 is top -> high blast_n
    low = severity(5, 1, 0.5, blast_dist=[5, 8, 9, 10, 12])  # 5 is bottom -> low blast_n
    assert high > low


def test_severity_bounds():
    s = severity(100, 9, 0.0, blast_dist=[1, 2, 3])
    assert 0.0 <= s <= 1.0


def test_affected_krs_path_and_guards():
    G = nx.Graph()
    G.add_edge("kr-1", "sys-a")
    G.add_edge("sys-a", "pulse-x")
    G.add_edge("kr-2", "sys-b")              # отдельный компонент
    assert affected_krs(G, "pulse-x") == ["kr-1"]     # kr-1 достигает, kr-2 нет
    assert affected_krs(G, "kr-1") == []              # сам узел исключён (kr!=node)
    assert affected_krs(G, "iso-x") == []             # узла нет в G -> [] (без NodeNotFound)


GRAPH = "poh_risk_test"


class _Note:
    def __init__(self, node_id, sources):
        self.node_id = node_id
        self.frontmatter = {"sources": sources}


def _claim(cid, subject, aspect, value, polarity, grounded, speaker=None,
           invalid_at=None, superseded_by=None, confidence=0.8):
    return {"id": cid, "subject": subject, "aspect": aspect, "value": value, "polarity": polarity,
            "grounded_node": grounded, "speaker": speaker, "confidence": confidence, "episode": "ep",
            "invalid_at": invalid_at, "expired_at": None, "superseded_by": superseded_by}


def test_synthesize_risks_three_axes(monkeypatch):
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")
    # граф: kr-a -SERVES-> sys-a ; pulse-1 -MENTIONS-> sys-a
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES"),
                                                             ("pulse-1", "sys-a", "MENTIONS")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-13")
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query(
        "MERGE (n:Entity {name:'iso-x'}) SET n.summary='Isolated'")   # изолированный -> understanding_gap

    # reflexion читает notes/claims из своих импортов; risk читает episode_claims из своего
    conflict = [_claim("c1", "S", "a", "выводит", "positive", "sys-a", speaker="Иван"),
                _claim("c2", "S", "a", "не выводит", "negative", "sys-a", speaker="Пётр")]
    superseded = [_claim("c3", "Фонд", "срок релиза", "сдвинут на Q4", "neutral", "sys-a",
                         invalid_at="2026-07-01", superseded_by="c9"),
                  _claim("c4", "Фонд", "объём фонда", "сокращён вдвое", "neutral", "sys-a",
                         invalid_at="2026-07-02", superseded_by="c8")]   # вытеснен, без date-kw -> requirements_change
    import poh_memory.reflexion as refl_mod
    monkeypatch.setattr(refl_mod, "episode_claims", lambda r: conflict)  # для in_contradiction/понимания
    monkeypatch.setattr(refl_mod, "load_all_nexus_notes",
                        lambda r: [_Note("kr-a", ["okr"]), _Note("sys-a", ["src"]), _Note("pulse-1", ["src"])])
    monkeypatch.setattr(risk_mod, "episode_claims", lambda r: conflict + superseded)

    risks = synthesize_risks(GRAPH, pathlib.Path("."))
    axes = {r["axis"] for r in risks}
    assert "understanding_gap" in axes          # iso-x (изолирован)
    assert "expectation_divergence" in axes     # c1 vs c2 на sys-a
    assert "schedule_slip" in axes              # c3 вытеснен + «срок релиза»
    assert "requirements_change" in axes        # c4 вытеснен, без date-kw
    # single-axis XOR: c4 порождает РОВНО один риск, ось requirements_change (не schedule_slip)
    req = [r for r in risks if r["axis"] == "requirements_change" and any("объём" in e for e in r["evidence"])]
    assert len(req) == 1
    assert not any(r["axis"] == "schedule_slip" and any("объём" in e for e in r["evidence"]) for r in risks)
    for r in risks:
        assert isinstance(r["severity"], float) and 0.0 <= r["severity"] <= 1.0
        assert r["evidence"]                     # непустой evidence (§4.6.1.5)
    ed = next(r for r in risks if r["axis"] == "expectation_divergence")
    assert set(ed["participants"]) == {"Иван", "Пётр"}
    assert "kr-a" in ed["affected_kr"]           # kr-a достигает sys-a
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def _r(axis="understanding_gap", severity=0.4, evidence=("e0",), affected_kr=()):
    return {"axis": axis, "severity": severity, "evidence": list(evidence),
            "affected_kr": list(affected_kr), "participants": [], "valid_time": None, "confidence": None}


def test_gate_three_routes_and_boundary():
    risks = [
        _r(affected_kr=["kr-a"]),                 # verified
        _r(severity=0.6),                          # review (no kr, sev>=0.5)
        _r(severity=0.3),                          # unlinkable (no kr, sev<0.5)
        _r(severity=0.5),                          # boundary -> review (>=)
    ]
    g = gate(risks)
    assert len(g["verified"]) == 1 and g["verified"][0]["affected_kr"] == ["kr-a"]
    assert len(g["review"]) == 2                   # sev 0.6 and 0.5
    assert len(g["unlinkable"]) == 1
    # every risk routed exactly once
    assert len(g["verified"]) + len(g["review"]) + len(g["unlinkable"]) == 4


def test_gate_empty():
    assert gate([]) == {"verified": [], "review": [], "unlinkable": []}


def test_risk_id_deterministic_and_evidence_sensitive():
    a = _risk_id(_r(evidence=["x"], affected_kr=["kr-1"]))
    b = _risk_id(_r(evidence=["x"], affected_kr=["kr-1"]))
    c = _risk_id(_r(evidence=["y"], affected_kr=["kr-1"]))
    assert a == b and a != c
    assert a.startswith("risk-understanding_gap-")


def test_risk_id_empty_evidence_no_crash():
    rid = _risk_id(_r(evidence=[]))
    assert rid.startswith("risk-understanding_gap-")


def test_write_queue_roundtrip(tmp_path):
    gated = {"verified": [_r(affected_kr=["kr-a"])],
             "review": [_r(severity=0.6)], "unlinkable": [_r(severity=0.2)]}
    p = write_queue(gated, tmp_path / "risk-queue.yaml")
    data = _yaml.safe_load(p.read_text(encoding="utf-8"))
    assert set(data) == {"review", "unlinkable"}      # verified НЕ в очереди
    assert len(data["review"]) == 1 and len(data["unlinkable"]) == 1
    assert data["review"][0]["evidence"] == ["e0"]    # список сохранён


def _verified(rid_axis="requirements_change", kr="kr-a"):
    return {"axis": rid_axis, "severity": 0.7, "evidence": ["вытеснено: срок=Q4"],
            "affected_kr": [kr], "participants": ["Иван"], "valid_time": "2026-07-01", "confidence": 0.8}


def test_materialize_risks_creates_risk_and_affects(monkeypatch):
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    g.query("MATCH (n) DETACH DELETE n")
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-13")

    n = materialize_risks(GRAPH, [_verified()])
    assert n == 1
    rows = g.query("MATCH (r:Risk)-[:AFFECTS]->(k:Entity {name:'kr-a'}) "
                   "RETURN r.axis, r.severity, r.source, r.participants").result_set
    assert rows and rows[0][0] == "requirements_change" and rows[0][2] == "signal-synthesis"
    assert rows[0][3] == "Иван"                       # participants stringified

    # idempotent: rerun -> still exactly 1 Risk (drop-first + stable id)
    materialize_risks(GRAPH, [_verified()])
    cnt = g.query("MATCH (r:Risk) RETURN count(r)").result_set[0][0]
    assert cnt == 1

    # PPR isolation: :Risk not in _load_graph
    G = _load_graph(GRAPH)
    assert not any(str(node).startswith("risk-") for node in G.nodes())
    g.query("MATCH (n) DETACH DELETE n")


def test_materialize_empty_clears_prior(monkeypatch):
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    g.query("MATCH (n) DETACH DELETE n")
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-13")
    materialize_risks(GRAPH, [_verified()])
    assert materialize_risks(GRAPH, []) == 0          # empty verified
    assert g.query("MATCH (r:Risk {source:'signal-synthesis'}) RETURN count(r)").result_set[0][0] == 0
    g.query("MATCH (n) DETACH DELETE n")


def test_understanding_gap_evidence_names_node(monkeypatch):
    # synthesize_risks understanding_gap evidence must include the node id
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    g.query("MATCH (n) DETACH DELETE n")
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-13")
    g.query("MERGE (n:Entity {name:'iso-x'}) SET n.summary='Iso'")
    import poh_memory.reflexion as refl_mod
    monkeypatch.setattr(refl_mod, "episode_claims", lambda r: [])
    monkeypatch.setattr(refl_mod, "load_all_nexus_notes", lambda r: [])
    monkeypatch.setattr(risk_mod, "episode_claims", lambda r: [])
    from poh_memory.risk import synthesize_risks
    ug = [r for r in synthesize_risks(GRAPH, pathlib.Path("."))
          if r["axis"] == "understanding_gap" and any("iso-x" in e for e in r["evidence"])]
    assert ug                                          # evidence names iso-x
    g.query("MATCH (n) DETACH DELETE n")


import pytest as _pytest


def _seed_graph_kr_a():
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    g.query("MATCH (n) DETACH DELETE n")
    g.query("MERGE (a:Entity {name:'kr-a'}) MERGE (b:Entity {name:'sys-a'}) "
            "MERGE (a)-[r:SERVES]->(b) SET r.valid_at=null, r.invalid_at=null, r.expired_at=null")
    return g


def test_build_risk_grounded_shape_and_affected_kr():
    _seed_graph_kr_a()
    r = build_risk("requirements_change", "sys-a", ["предложение X", "почему requirements_change"],
                   ["Иван"], 0.8, GRAPH)
    assert set(r) == {"axis", "severity", "evidence", "affected_kr", "participants",
                      "valid_time", "confidence"}
    assert r["axis"] == "requirements_change"
    assert isinstance(r["severity"], float) and 0.0 <= r["severity"] <= 1.0
    assert "kr-a" in r["affected_kr"]                 # kr-a достигает sys-a
    assert r["participants"] == ["Иван"]
    assert gate([r])["verified"] == [r]               # проходит гейт как verified
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def test_build_risk_grounded_materializes_via_shared_path():
    _seed_graph_kr_a()
    r = build_risk("requirements_change", "sys-a", ["ev"], [], 0.7, GRAPH)
    n = materialize_risks(GRAPH, gate([r])["verified"])
    assert n == 1
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    assert g.query("MATCH (r:Risk)-[:AFFECTS]->(:Entity {name:'kr-a'}) RETURN count(r)").result_set[0][0] == 1
    g.query("MATCH (n) DETACH DELETE n")


def test_build_risk_none_grounded_routes_to_queue(tmp_path):
    r = build_risk("understanding_gap", None, ["не заземлилось"], [], 0.6, GRAPH)
    assert r["affected_kr"] == [] and r["severity"] >= 0.0
    g = gate([r])
    assert r in g["review"]                            # нет KR + sev 0.6 -> review
    p = write_queue(g, tmp_path / "q.yaml")
    assert p.exists()


def test_build_risk_invalid_axis():
    with _pytest.raises(ValueError):
        build_risk("bogus-axis", "sys-a", ["e"], [], 0.5, GRAPH)


def test_build_risk_empty_evidence():
    with _pytest.raises(ValueError):
        build_risk("schedule_slip", "sys-a", [], [], 0.5, GRAPH)


def test_materialize_sources_isolated():
    """#5-B2: signal-synthesis and agent-classify sources do not clobber each other."""
    g = _seed_graph_kr_a()

    # step 1: materialize a synthesized risk (default args -> source="signal-synthesis", drop_first=True)
    synth = {"axis": "requirements_change", "severity": 0.7, "evidence": ["synth-ev"],
             "affected_kr": ["kr-a"], "participants": [], "valid_time": None, "confidence": 0.8}
    materialize_risks(GRAPH, [synth])
    rows = g.query("MATCH (r:Risk {source:'signal-synthesis'}) RETURN r.name").result_set
    assert rows, "synthesized Risk node must exist"
    synth_name = rows[0][0]

    # step 2: materialize a DIFFERENT classify risk (source="agent-classify", drop_first=False)
    classify1 = {"axis": "understanding_gap", "severity": 0.5, "evidence": ["classify-ev-1"],
                 "affected_kr": [], "participants": [], "valid_time": None, "confidence": 0.6}
    materialize_risks(GRAPH, [classify1], source="agent-classify", drop_first=False)
    # classify node exists
    c_rows = g.query("MATCH (r:Risk {source:'agent-classify'}) RETURN r.name").result_set
    assert c_rows, "classify Risk node must exist"
    # synthesized node was NOT dropped
    s_rows = g.query("MATCH (r:Risk {source:'signal-synthesis'}) RETURN r.name").result_set
    assert s_rows, "synthesized Risk node must still exist after agent-classify run"

    # step 3: materialize a SECOND distinct classify risk (accumulate — drop_first=False)
    classify2 = {"axis": "schedule_slip", "severity": 0.6, "evidence": ["classify-ev-2"],
                 "affected_kr": [], "participants": [], "valid_time": None, "confidence": 0.7}
    materialize_risks(GRAPH, [classify2], source="agent-classify", drop_first=False)
    all_rows = g.query("MATCH (r:Risk) RETURN r.name, r.source").result_set
    classify_names = {row[0] for row in all_rows if row[1] == "agent-classify"}
    synth_names = {row[0] for row in all_rows if row[1] == "signal-synthesis"}
    assert len(classify_names) == 2, f"both classify nodes must exist; got {classify_names}"
    assert len(synth_names) == 1, f"synthesized node must still exist; got {synth_names}"

    g.query("MATCH (n) DETACH DELETE n")


def test_build_risk_grounded_uses_distribution():
    _seed_graph_kr_a()
    r = build_risk("schedule_slip", "sys-a", ["предложение", "почему schedule_slip"],
                   [], 0.7, GRAPH)
    assert 0.0 <= r["severity"] <= 1.0
    assert r["axis"] == "schedule_slip"
    assert "kr-a" in r["affected_kr"]
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")

def test_build_risk_ungrounded_still_confidence():
    _seed_graph_kr_a()
    r = build_risk("schedule_slip", None, ["предложение", "почему"], [], 0.7, GRAPH)
    assert r["severity"] == 0.7          # confidence, unchanged (blast_distribution NOT called)
    assert r["affected_kr"] == []
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def test_blast_distribution_excludes_risk_and_sorted():
    _seed_graph_kr_a()                        # 2 :Entity nodes: kr-a, sys-a
    dist = blast_distribution(GRAPH)
    assert isinstance(dist, list) and all(isinstance(x, int) for x in dist)
    assert dist == sorted(dist)               # ascending
    assert len(dist) == 2                     # one entry per :Entity node (kr-a, sys-a)

    # seed a :Claim node; confirm it does NOT enter the distribution
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    g.query("MERGE (c:Claim {name:'claim-x'})")
    assert len(blast_distribution(GRAPH)) == 2   # :Claim excluded — only kr-a, sys-a (Entity) count

    # materialize a :Risk node; confirm it does NOT enter the distribution
    risk = {"axis": "schedule_slip", "severity": 0.9, "evidence": ["e"],
            "affected_kr": ["kr-a"], "participants": [], "valid_time": None, "confidence": 0.9}
    materialize_risks(GRAPH, [risk])
    assert len(blast_distribution(GRAPH)) == 2   # :Risk excluded — count unchanged
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")
