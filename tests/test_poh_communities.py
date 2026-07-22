import networkx as nx
from poh_memory.communities import detect_communities


def _two_disconnected_triangles():
    G = nx.Graph()
    G.add_edges_from([("a", "b"), ("b", "c"), ("a", "c")])   # cluster 1
    G.add_edges_from([("x", "y"), ("y", "z"), ("x", "z")])   # cluster 2 (disconnected)
    return G


def test_two_components_two_communities():
    cid = detect_communities(_two_disconnected_triangles())
    # each triangle shares one community_id; the two differ
    assert cid["a"] == cid["b"] == cid["c"]
    assert cid["x"] == cid["y"] == cid["z"]
    assert cid["a"] != cid["x"]


def test_community_id_is_min_member():
    cid = detect_communities(_two_disconnected_triangles())
    assert cid["a"] == "a"   # min of {a,b,c}
    assert cid["x"] == "x"   # min of {x,y,z}


def test_isolated_node_is_own_community():
    G = nx.Graph()
    G.add_edge("a", "b")
    G.add_node("solo")
    cid = detect_communities(G)
    assert cid["solo"] == "solo"
    assert cid["a"] == cid["b"] == "a"


def test_empty_graph_returns_empty():
    assert detect_communities(nx.Graph()) == {}


def test_deterministic_across_calls_and_insertion_order():
    G1 = _two_disconnected_triangles()
    G2 = nx.Graph()
    # reversed insertion order — result must be identical
    G2.add_edges_from([("z", "x"), ("z", "y"), ("y", "x")])
    G2.add_edges_from([("c", "a"), ("c", "b"), ("b", "a")])
    assert detect_communities(G1) == detect_communities(G1)      # stable across calls
    assert detect_communities(G1) == detect_communities(G2)      # independent of order
