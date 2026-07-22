from falkordb import FalkorDB
from poh_memory.client import FALKOR_HOST, FALKOR_PORT
from poh_memory.supersede import reconcile_edges

GRAPH = "poh_supersede_test"


def _graph():
    return FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)


def _seed(edges):
    """edges: list of (src, etype, dst, invalid_at)."""
    g = _graph()
    g.query("MATCH (n) DETACH DELETE n")
    for src, etype, dst, inv in edges:
        g.query(
            f"MERGE (x:Entity {{name:$s}}) MERGE (y:Entity {{name:$d}}) "
            f"MERGE (x)-[r:{etype}]->(y) SET r.invalid_at=$iv",
            {"s": src, "d": dst, "iv": inv},
        )
    return g


def _invalid_at(g, src, etype, dst):
    rows = g.query(
        f"MATCH (:Entity {{name:$s}})-[r:{etype}]->(:Entity {{name:$d}}) "
        f"RETURN r.invalid_at",
        {"s": src, "d": dst},
    ).result_set
    return rows[0][0] if rows else "MISSING"


def test_absent_edge_gets_invalidated():
    g = _seed([("a", "SERVES", "b", None), ("c", "MENTIONS", "d", None)])
    n = reconcile_edges(g, {("a", "SERVES", "b")}, "2026-03-01")
    assert n == 1                                         # только c-MENTIONS-d
    assert _invalid_at(g, "a", "SERVES", "b") is None     # asserted -> не тронут
    assert _invalid_at(g, "c", "MENTIONS", "d") == "2026-03-01"


def test_already_invalidated_not_overwritten():
    g = _seed([("c", "MENTIONS", "d", "2020-01-01")])
    n = reconcile_edges(g, set(), "2026-03-01")           # не в asserted, но уже invalid
    assert n == 0
    assert _invalid_at(g, "c", "MENTIONS", "d") == "2020-01-01"


def test_all_asserted_no_invalidation():
    g = _seed([("a", "SERVES", "b", None)])
    n = reconcile_edges(g, {("a", "SERVES", "b")}, "2026-03-01")
    assert n == 0
    assert _invalid_at(g, "a", "SERVES", "b") is None
