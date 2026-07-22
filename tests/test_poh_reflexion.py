from poh_memory.reflexion import aggregate
import pathlib
from falkordb import FalkorDB
import poh_memory.ingest as ing_mod
import poh_memory.reflexion as refl_mod
from poh_memory.ingest import ingest
from poh_memory.reflexion import node_contexts
from poh_memory.client import FALKOR_HOST, FALKOR_PORT

GRAPH = "poh_reflexion_test"


class _Note:
    def __init__(self, node_id, sources):
        self.node_id = node_id
        self.frontmatter = {"sources": sources}


def test_node_contexts_integration(monkeypatch):
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")
    # граф: kr-a -SERVES-> sys-a (связаны); iso-x без рёбер (добавим отдельным MERGE)
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {"kr-a": "KR A", "sys-a": "System A"})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-13")
    # изолированный Entity без рёбер
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query(
        "MERGE (n:Entity {name:'iso-x'}) SET n.summary='Isolated X'")
    # reflexion читает claims/notes из своих импортов -> monkeypatch их
    monkeypatch.setattr(refl_mod, "episode_claims", lambda r: [])   # нет claim'ов -> нет contradiction
    monkeypatch.setattr(refl_mod, "load_all_nexus_notes",
                        lambda r: [_Note("kr-a", ["okr"]), _Note("sys-a", [])])  # sys-a без sources

    ctxs = {c["node_id"]: c for c in node_contexts(GRAPH, pathlib.Path("."))}
    assert set(ctxs) == {"kr-a", "sys-a", "iso-x"}
    assert ctxs["kr-a"]["flags"]["isolated"] is False
    assert ("SERVES", "sys-a") in ctxs["kr-a"]["neighbors"]      # тип ребра из G[nid][nbr]["type"]
    assert ctxs["kr-a"]["summary"] == "KR A"                     # summary из FalkorDB
    assert ctxs["iso-x"]["flags"]["isolated"] is True
    assert ctxs["iso-x"]["neighbors"] == []                      # guard: нет NetworkXError
    assert ctxs["kr-a"]["flags"]["workslop_no_sources"] is False  # есть sources
    assert ctxs["sys-a"]["flags"]["workslop_no_sources"] is True  # пустой sources
    assert ctxs["iso-x"]["flags"]["workslop_no_sources"] is True  # нет ноты вовсе
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def test_node_contexts_flags_contradiction(monkeypatch):
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-13")
    # два claim'а на sys-a, один subject+aspect, разный polarity -> candidate pair -> in_contradiction
    def _cl(cid, pol):
        return {"id": cid, "subject": "S", "aspect": "a", "value": f"v{pol}", "polarity": pol,
                "grounded_node": "sys-a", "episode": "ep",
                "invalid_at": None, "expired_at": None, "superseded_by": None}
    monkeypatch.setattr(refl_mod, "episode_claims", lambda r: [_cl("c1", "positive"), _cl("c2", "negative")])
    monkeypatch.setattr(refl_mod, "load_all_nexus_notes", lambda r: [])
    ctxs = {c["node_id"]: c for c in node_contexts(GRAPH, pathlib.Path("."))}
    assert ctxs["sys-a"]["flags"]["in_contradiction"] is True
    assert ctxs["kr-a"]["flags"]["in_contradiction"] is False
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def _ctx(nid, isolated=False, workslop=False, contra=False):
    return {"node_id": nid, "summary": nid, "neighbors": [],
            "flags": {"isolated": isolated, "workslop_no_sources": workslop, "in_contradiction": contra}}


def _v(nid, understood, issues=()):
    return {"node_id": nid, "understood": understood, "issues": list(issues), "confidence": 0.8, "rationale": "r"}


def test_aggregate_share_and_queues():
    contexts = [_ctx("a"), _ctx("b", isolated=True), _ctx("c", workslop=True)]
    verdicts = [_v("a", True), _v("b", False, ["isolated"]), _v("c", False, ["workslop"])]
    r = aggregate(contexts, verdicts)
    assert r["total"] == 3
    assert r["understood"] == 1
    assert r["share"] == round(1 / 3, 3)
    assert r["queues"]["not_understood"] == ["b", "c"]
    assert r["queues"]["isolated"] == ["b"]        # из contexts-flags, детерминированно
    assert r["queues"]["workslop"] == ["c"]
    assert r["queues"]["contradictory"] == []


def test_aggregate_structural_queue_from_flags_not_agent_issues():
    # агент НЕ пометил issue, но флаг стоит -> узел всё равно в структурной очереди
    contexts = [_ctx("x", contra=True)]
    verdicts = [_v("x", True, issues=[])]          # понят, issue не указан
    r = aggregate(contexts, verdicts)
    assert r["queues"]["contradictory"] == ["x"]   # из флага, не из issues


def test_aggregate_empty_no_zero_division():
    r = aggregate([], [])
    assert r["total"] == 0
    assert r["share"] == 0.0
    assert r["queues"]["not_understood"] == []
