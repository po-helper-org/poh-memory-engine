"""KR->реплика запрос поверх FalkorDB: читаем граф в networkx, PPR (HippoRAG-логика)
seeded на KR, возвращаем достигнутые эпизоды + shortest-path цепочку.

FalkorDB: узлы label Entity со свойством `name`(=канонический node_id), тип ребра =
хребет OKR + ценностная ось PAF. Читаем a.name/type(r)/b.name + битемпоральные метки
ребра (valid_at/invalid_at/expired_at) и фильтруем предикатом active_at на момент as_of.
Retrieval-граф семантический: `_load_graph` фильтрует до `_SEM_REL` — хабы (OWNS) и
claim-слой (ASSERTS/ABOUT) вне PPR (правило 2).
"""
from __future__ import annotations
import networkx as nx
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT
from poh_memory.edges import SEM_FIELDS
from poh_memory.temporal import active_at

# Тот же вокабуляр, что у edges/ingest — один источник на все три фильтра. Правило 2
# держится само: claim-слой (ASSERTS/ABOUT/SUPERSEDED_BY) и хаб OWNS в SEM_FIELDS
# отсутствуют, поэтому в retrieval-граф не попадают.
_SEM_REL = frozenset(SEM_FIELDS.values())


def _load_graph(graph_name: str, host: str = FALKOR_HOST, port: int = FALKOR_PORT,
                as_of: str | None = None) -> nx.Graph:
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    rows = g.query(
        "MATCH (a)-[r]->(b) "
        "RETURN a.name, type(r), b.name, r.valid_at, r.invalid_at, r.expired_at"
    ).result_set
    G = nx.Graph()
    for src, etype, dst, valid_at, invalid_at, expired_at in rows:
        if not (src and dst):
            continue
        if etype not in _SEM_REL:          # claim-слой (ASSERTS/ABOUT) вне PPR — правило 2
            continue
        props = {"valid_at": valid_at, "invalid_at": invalid_at, "expired_at": expired_at}
        if not active_at(props, as_of):
            continue
        G.add_edge(src, dst, type=etype)
    return G


def _ppr_episodes(G: nx.Graph, personalization: dict, seeds: list[str], topn: int) -> list[dict]:
    ppr = nx.pagerank(G, personalization=personalization, alpha=0.85)
    eps = sorted(((ppr[n], n) for n in G if n.startswith("pulse-") and ppr.get(n, 0) > 0),
                 reverse=True)[:topn]
    out = []
    for score, ep in eps:
        path = []
        for seed in seeds:
            if seed in G:
                try:
                    path = nx.shortest_path(G, seed, ep)
                    break
                except nx.NetworkXNoPath:
                    continue
        out.append({"episode": ep, "score": round(score, 4), "chain": path})
    return out


def kr_to_replica(graph_name: str, kr_id: str, topn: int = 5,
                  as_of: str | None = None) -> list[dict]:
    """Seed на известном KR-узле (Stage 1/2)."""
    G = _load_graph(graph_name, as_of=as_of)
    if kr_id not in G:
        return []
    return _ppr_episodes(G, {kr_id: 1.0}, [kr_id], topn)


def text_to_replica(graph_name: str, query_text: str, topk_seed: int = 5,
                    topn: int = 5, as_of: str | None = None) -> list[dict]:
    """Заземление произвольного текста: bge-m3 -> top-k узлов -> PPR -> цепочка."""
    from poh_memory.vectors import seed_from_text
    G = _load_graph(graph_name, as_of=as_of)
    seeds = {nid: w for nid, w in seed_from_text(query_text, topk_seed).items() if nid in G}
    if not seeds:
        return []
    ranked = sorted(seeds, key=seeds.get, reverse=True)
    return _ppr_episodes(G, seeds, ranked, topn)
