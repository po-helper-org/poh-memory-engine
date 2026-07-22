from dataclasses import dataclass
from paf_index import ground

@dataclass
class _Ep:
    nexus_refs: list
    jira_refs: list

def test_nexus_ref_high_trust():
    ep = _Ep(["system-extapi-go"], [])
    res = ground.ground_refs(ep, {"system-extapi-go"})
    g = res.grounded[0]
    assert (g.plane, g.trust, g.target, g.resolved) == ("nexus", "high", "system-extapi-go", True)
    assert res.unresolved == []

def test_jira_ref_medium_trust_task_target():
    ep = _Ep([], ["PROJ-17704"])
    res = ground.ground_refs(ep, set())
    g = res.grounded[0]
    assert (g.plane, g.trust, g.target) == ("jira", "medium", "task-PROJ-17704")

def test_unknown_nexus_ref_goes_unresolved():
    ep = _Ep(["no-such-node"], [])
    res = ground.ground_refs(ep, {"system-extapi-go"})
    assert res.grounded == []
    assert res.unresolved == ["no-such-node"]

def test_jira_key_colliding_with_node_id_prefers_nexus():
    ep = _Ep([], ["PROJ-17704"])
    res = ground.ground_refs(ep, {"PROJ-17704"})
    g = res.grounded[0]
    assert (g.plane, g.trust, g.target) == ("nexus", "high", "PROJ-17704")
