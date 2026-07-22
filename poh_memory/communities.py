"""Communities (#3) — детект сообществ label-propagation + blast-radius.

detect_communities — чистая графовая математика (без FalkorDB, без LLM): над
networkx-графом (как из query._load_graph) считает разбиение на сообщества и
присваивает каждому узлу community_id = лексикографически минимальный node_id
его кластера (стабильный, человекочитаемый id, не зависит от внутренней
случайности алгоритма). blast_radius — тонкая читалка материализованной метки.
Спека: docs/superpowers/specs/2026-07-12-poh-communities-design.md
"""
from __future__ import annotations
import networkx as nx
from networkx.algorithms.community import asyn_lpa_communities
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT


def detect_communities(G: nx.Graph) -> dict[str, str]:
    """{node_id: community_id}. community_id = min node_id кластера. {} для пустого графа."""
    if G.number_of_nodes() == 0:
        return {}
    # детерминированный вход: отсортированный порядок узлов и рёбер
    H = nx.Graph()
    H.add_nodes_from(sorted(G.nodes()))
    H.add_edges_from(sorted((min(u, v), max(u, v)) for u, v in G.edges()))
    out: dict[str, str] = {}
    for comm in asyn_lpa_communities(H, seed=42):
        cid = min(comm)                       # стабильный id = наименьший член
        for n in comm:
            out[n] = cid
    return out


def blast_radius(graph_name: str, node_id: str,
                 host: str = FALKOR_HOST, port: int = FALKOR_PORT) -> list[str]:
    """Узлы того же сообщества, что node_id (без самого узла), отсортированно.
    [] если узла нет или у него нет community_id. Читает материализованную метку."""
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    rows = g.query("MATCH (n:Entity {name:$id}) RETURN n.community_id",
                   {"id": node_id}).result_set
    if not rows or rows[0][0] is None:
        return []
    cid = rows[0][0]
    rows = g.query(
        "MATCH (m:Entity) WHERE m.community_id=$cid AND m.name<>$id RETURN m.name",
        {"cid": cid, "id": node_id},
    ).result_set
    return sorted(r[0] for r in rows)
