from falkordb import FalkorDB
from poh_memory.client import FALKOR_HOST, FALKOR_PORT
from poh_memory.query import _load_graph

GRAPH = "poh_claim_isolation_test"


def _seed():
    g = FalkorDB(host=FALKOR_HOST, port=FALKOR_PORT).select_graph(GRAPH)
    g.query("MATCH (n) DETACH DELETE n")
    # семантич. ребро (должно попасть в граф)
    g.query("MERGE (a:Entity {name:'kr-x'}) MERGE (b:Entity {name:'system-y'}) "
            "MERGE (a)-[r:SERVES]->(b) SET r.valid_at=null, r.invalid_at=null, r.expired_at=null")
    # claim-слой (НЕ должен попасть)
    g.query("MERGE (e:Entity {name:'pulse-ep'}) MERGE (c:Claim {name:'claim-1'}) "
            "MERGE (e)-[r:ASSERTS]->(c) SET r.valid_at=null, r.invalid_at=null, r.expired_at=null")
    g.query("MERGE (c:Claim {name:'claim-1'}) MERGE (n:Entity {name:'system-y'}) "
            "MERGE (c)-[r:ABOUT]->(n) SET r.valid_at=null, r.invalid_at=null, r.expired_at=null")
    return g


def test_load_graph_excludes_claim_layer():
    _seed()
    G = _load_graph(GRAPH)
    assert G.has_edge("kr-x", "system-y")       # семантич. ребро есть
    assert "claim-1" not in G                    # Claim-узел исключён
    assert not G.has_edge("pulse-ep", "claim-1") # ASSERTS исключён
    # ABOUT (claim-1 -> system-y) исключён: claim-1 вообще не в графе
    assert G.number_of_edges() == 1
