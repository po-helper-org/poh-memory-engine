import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "sa_documentation"))
import validate_ground as vg

def test_new_node_types_present():
    for t in ("key-result", "objective", "epic", "task", "episode", "risk", "decision", "component-ref"):
        assert t in vg.NODE_TYPES

def test_new_edge_fields_present():
    assert "owns_node" in vg.EDGE_FIELDS_SINGLE
    assert "serves" in vg.EDGE_FIELDS_SINGLE
    assert "delivered_by" in vg.EDGE_FIELDS_LIST

def test_episode_edge_fields_present():
    assert "mentions" in vg.EDGE_FIELDS_LIST
    assert "involves" in vg.EDGE_FIELDS_LIST
