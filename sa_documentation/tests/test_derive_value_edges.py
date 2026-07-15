import datetime
import pathlib

from paf_index.frontmatter import Node
from paf_index.derive import derive_value_edges

TODAY = datetime.date(2026, 7, 14).isoformat()


def _node(node_id, node_type="initiative", **fm_over):
    fm = {"node_id": node_id, "node_type": node_type}
    fm.update(fm_over)
    return Node(
        node_id=node_id, node_type=node_type, nexus="product", owner=None,
        full_name=None, sources=[], manages=[], reports_to=None,
        collaborates_with=[], updated=None, ttl_days=None, confidence=None,
        ripeness=None, path=pathlib.Path(f"{node_id}.md"), frontmatter=fm,
    )


def test_based_on_emits_typed_edge():
    nodes = [
        _node("init-x", based_on=["svc-y"]),
        _node("svc-y", node_type="service"),
    ]
    r = derive_value_edges(nodes, TODAY)
    edge = next(e for e in r.edges if e.type == "BASED_ON")
    assert edge.src == "init-x"
    assert edge.dst == "svc-y"
    assert edge.source_anchor == "based_on frontmatter"
    assert r.dangling_refs == []


def test_unresolved_target_is_dangling_not_edge():
    nodes = [_node("init-x", based_on=["svc-missing"])]
    r = derive_value_edges(nodes, TODAY)
    assert r.edges == []
    assert ("init-x", "svc-missing") in r.dangling_refs


def test_all_six_predicates_mapped():
    nodes = [
        _node("a", realizes=["b"], based_on=["b"], depends_on=["b"],
              addresses=["b"], satisfies=["b"], has_need=["b"]),
        _node("b", node_type="need"),
    ]
    r = derive_value_edges(nodes, TODAY)
    types = {e.type for e in r.edges}
    assert types == {"REALIZES", "BASED_ON", "DEPENDS_ON",
                     "ADDRESSES", "SATISFIES", "HAS_NEED"}
