# tests/test_report.py
from paf_index import report
from paf_index.derive import DeriveResult, Edge, NewNode
from paf_index.reconcile import ReconcileReport

def test_render_report_has_sections():
    dr = DeriveResult(
        edges=[Edge("OWNS", "a", "team-x", "owner field", "high", "2026-07-08", "2026-07-08")],
        new_nodes=[NewNode("kr-1-1", "key-result", "t", {})],
        unresolved_owners=[("b", "Кто-то Неизвестный")],
    )
    rr = ReconcileReport(isolated=["c"], workslop=[], dangling=[],
                         ownerless_kr=[], context_ripeness={"team": 0.42})
    out = report.render_report(dr, rr, n_nodes=187)
    assert "OWNS" in out
    assert "ContextRipeness" in out
    assert "team" in out
    assert "Кто-то Неизвестный" in out  # unresolved → queue visible

def test_render_report_episode_section():
    from paf_index.derive import DeriveResult, EpisodeDeriveResult, Edge, NewNode
    from paf_index.reconcile import ReconcileReport
    dr = DeriveResult()
    rr = ReconcileReport(isolated=[], workslop=[], dangling=[], ownerless_kr=[],
                         context_ripeness={"team": 0.9})
    edr = EpisodeDeriveResult(
        edges=[Edge("MENTIONS", "pulse-x", "system-a", "s", "high", "2026-07-09", "2026-07-09")],
        new_nodes=[NewNode("pulse-x", "episode", "pulse-x", {})],
        unresolved_participants=[("pulse-x", "Кто-то Неизвестный")],
        dangling_refs=[("pulse-x", "nonexistent-node")],
    )
    out = report.render_report(dr, rr, n_nodes=1, episode_result=edr)
    assert "Эпизоды" in out
    assert "MENTIONS" in out
    assert "Кто-то Неизвестный" in out
    assert "nonexistent-node" in out

def test_report_renders_gate_section():
    from paf_index import reconcile
    dr = DeriveResult()
    rr = ReconcileReport(context_ripeness={"a": 0.9})
    gr = reconcile.GateResult(passed=False, reasons=["3 KR без OWNS→person"], ripeness_min=0.9)
    inv = {"kr_without_owns": ["kr-1", "kr-2", "kr-3"], "spine_orphans": [],
           "ownership_contradictions": []}
    out = report.render_report(dr, rr, n_nodes=1, gate_result=gr, invariants=inv,
                               candidate_counts={"open": 5, "approved": 1})
    assert "## Скелет-гейт" in out
    assert "Готов: НЕТ" in out
    assert "3 KR без OWNS→person" in out
    assert "open=5" in out

def test_report_has_grounding_section():
    from paf_index.derive import EpisodeDeriveResult

    er = EpisodeDeriveResult(
        edges=[
            Edge("MENTIONS", "pulse-a", "system-x", "s", "high", "2026-07-09", "2026-07-09"),
            Edge("MENTIONS", "pulse-a", "task-PROJ-1", "s", "medium", "2026-07-09", "2026-07-09"),
        ],
        new_nodes=[NewNode("pulse-a", "episode", "pulse-a", {})],
        dangling_refs=[("pulse-a", "unknown-ref")],
    )
    class _DR:  edges=[]; new_nodes=[]; unresolved_owners=[]
    class _RR:  isolated=[]; workslop=[]; dangling=[]; context_ripeness={}
    out = report.render_report(_DR(), _RR(), n_nodes=1, episode_result=er)
    assert "## Заземление" in out
    assert "nexus/high: 1" in out
    assert "jira/medium: 1" in out
    assert "не заземлено: 1" in out
