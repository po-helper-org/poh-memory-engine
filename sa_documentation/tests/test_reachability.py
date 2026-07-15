import pathlib

from paf_index.frontmatter import Node
from paf_index.derive import Edge
from paf_index.gaps import reachability_from_kr

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


def test_delivers_makes_node_reachable_from_kr():
    nodes = [_node("kr-1", "key-result"), _node("init-a")]
    edges = [_edge("DELIVERS", "init-a", "kr-1")]
    r = reachability_from_kr(nodes, edges)
    assert "init-a" in r.reachable
    assert r.unreachable == []
    assert r.fraction == 1.0


def test_isolated_node_is_unreachable():
    nodes = [_node("kr-1", "key-result"), _node("init-a"), _node("init-b")]
    edges = [_edge("DELIVERS", "init-a", "kr-1")]
    r = reachability_from_kr(nodes, edges)
    assert r.unreachable == ["init-b"]
    assert r.fraction == 2 / 3


def test_mentions_excluded_when_filtered():
    nodes = [_node("kr-1", "key-result"), _node("init-c")]
    edges = [_edge("MENTIONS", "kr-1", "init-c")]
    typed = {"DELIVERS", "SERVES", "OWNS", "BASED_ON"}
    r = reachability_from_kr(nodes, edges, edge_types=typed)
    assert "init-c" in r.unreachable


def test_no_kr_seeds_all_unreachable():
    nodes = [_node("init-a"), _node("init-b")]
    r = reachability_from_kr(nodes, [])
    assert r.fraction == 0.0
    assert set(r.unreachable) == {"init-a", "init-b"}


def test_scaffolding_excluded_from_denominator():
    # step-overview scaffolding must not count as a value-axis orphan.
    nodes = [_node("kr-1", "key-result"), _node("init-a"),
             _node("ov-x", "step-overview")]
    edges = [_edge("DELIVERS", "init-a", "kr-1")]
    is_content = lambda n: n.node_type != "step-overview"
    r = reachability_from_kr(nodes, edges, content_filter=is_content)
    assert "ov-x" not in r.unreachable
    assert r.unreachable == []
    assert r.fraction == 1.0
