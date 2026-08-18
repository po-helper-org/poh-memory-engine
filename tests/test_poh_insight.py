# tests/test_poh_insight.py
import pathlib
from falkordb import FalkorDB
import poh_memory.ingest as ing_mod
from poh_memory.ingest import ingest
from poh_memory.insight import analyze
from poh_memory.client import FALKOR_HOST, FALKOR_PORT

GRAPH = "poh_insight_test"


def _reset():
    FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH).query("MATCH (n) DETACH DELETE n")


def _claim(cid, ep, grounded=None):
    return {"id": cid, "subject": "s", "aspect": "a", "value": "v", "polarity": "neutral",
            "speaker": None, "grounded_node": grounded, "confidence": None, "episode": ep,
            "invalid_at": None, "expired_at": None, "superseded_by": None}


def test_analyze_integration(monkeypatch):
    _reset()
    # kr-a connected to sys-a via pulse-1; kr-b has no episode (empty goal)
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [
        ("kr-a", "sys-a", "SERVES"), ("pulse-1", "sys-a", "MENTIONS"), ("pulse-1", "kr-a", "MENTIONS")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [
        _claim("c1", "pulse-1", grounded="sys-a"), _claim("c2", "pulse-1", grounded=None)])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-12")
    monkeypatch.setattr("poh_memory.insight.episode_claims", lambda r: [
        _claim("c1", "pulse-1", grounded="sys-a"), _claim("c2", "pulse-1", grounded=None)])
    res = analyze(GRAPH, pathlib.Path("."))
    assert res["stats"]["entities"] >= 3
    assert "kr-a" in res["goal_coverage"]
    assert res["grounding"] == {"grounded": 1, "ungrounded": 1}
    assert res["communities"]["count"] >= 1
    assert "top_by_blast_radius" in res["communities"]
    assert res["isolated_nodes"] == []   # все 3 сущности имеют семантич. рёбра
    _reset()


def _vault_with_vocab(tmp_path, canonical: str) -> pathlib.Path:
    """Волт с словарём аспектов; возвращает NEXUS-корень (как его получает analyze)."""
    nexus = tmp_path / "GROUND" / "NEXUS"
    nexus.mkdir(parents=True)
    (tmp_path / "GROUND" / "_index").mkdir(parents=True)
    (tmp_path / "GROUND" / "_index" / "aspect-vocab.yaml").write_text(
        f"aspects:\n  - canonical: {canonical}\n    synonyms: []\n", encoding="utf-8")
    return nexus


def test_analyze_reports_off_vocab_aspects(monkeypatch, tmp_path):
    _reset()
    monkeypatch.setattr(ing_mod, "semantic_edges", lambda r: [("kr-a", "sys-a", "SERVES"),
                                                             ("pulse-1", "sys-a", "MENTIONS")])
    monkeypatch.setattr(ing_mod, "node_titles", lambda r: {})
    monkeypatch.setattr(ing_mod, "episode_claims", lambda r: [_claim("c1", "pulse-1", grounded="sys-a")])
    ingest(pathlib.Path("."), GRAPH, ingest_at="2026-07-13")
    # insight reads claims via its own episode_claims; return a claim with a canonical + an off-vocab aspect
    monkeypatch.setattr("poh_memory.insight.episode_claims", lambda r: [
        {**_claim("c1", "pulse-1", grounded="sys-a"), "aspect": "актуальность/жизненный цикл"},  # canonical
        {**_claim("c2", "pulse-1", grounded="sys-a"), "aspect": "free-text-not-in-vocab"},        # off-vocab
    ])
    # словарь живёт в волте, а не в cwd — analyze обязан найти его от nexus_root
    nexus = _vault_with_vocab(tmp_path, "актуальность/жизненный цикл")
    res = analyze(GRAPH, nexus)
    assert "free-text-not-in-vocab" in res["off_vocab_aspects"]
    assert "актуальность/жизненный цикл" not in res["off_vocab_aspects"]
    _reset()
