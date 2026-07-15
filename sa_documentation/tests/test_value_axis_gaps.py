import pathlib

from paf_index.frontmatter import Node
from paf_index.derive import Edge
from paf_index.gaps import value_axis_gaps, is_value_content

TODAY = "2026-07-14"


def _node(node_id, node_type="initiative"):
    return Node(
        node_id=node_id, node_type=node_type, nexus="product", owner=None,
        full_name=None, sources=[], manages=[], reports_to=None,
        collaborates_with=[], updated=None, ttl_days=None, confidence=None,
        ripeness=None, path=pathlib.Path(f"{node_id}.md"), frontmatter={},
    )


def _edge(t, src, dst):
    return Edge(t, src, dst, "x", "high", TODAY, TODAY)


def test_node_with_value_edge_not_a_gap():
    nodes = [_node("init-a"), _node("svc-y", "service")]
    edges = [_edge("BASED_ON", "init-a", "svc-y")]
    assert value_axis_gaps(nodes, edges) == []


def test_node_with_only_owns_and_mentions_is_gap():
    nodes = [_node("init-a"), _node("p-1", "person")]
    edges = [_edge("OWNS", "init-a", "p-1"), _edge("MENTIONS", "init-a", "p-1")]
    gaps = value_axis_gaps(nodes, edges)
    assert "init-a" in gaps


def test_scaffolding_excluded():
    nodes = [_node("ov-x", "step-overview")]
    gaps = value_axis_gaps(nodes, [], content_filter=is_value_content)
    assert gaps == []


def test_value_axis_eligible_excludes_people_and_spine():
    from paf_index.gaps import is_value_axis_eligible
    person = _node("p-1", "person"); person.nexus = "team"
    kr = _node("kr-1", "key-result"); kr.nexus = "okr"
    ep = _node("ep-1", "episode"); ep.nexus = "pulse"
    init = _node("init-a"); init.nexus = "product"
    svc = _node("svc-y", "service"); svc.nexus = "system"
    assert not is_value_axis_eligible(person)
    assert not is_value_axis_eligible(kr)
    assert not is_value_axis_eligible(ep)
    assert is_value_axis_eligible(init)
    assert is_value_axis_eligible(svc)
