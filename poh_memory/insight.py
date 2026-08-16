# poh_memory/insight.py
"""Аналитика всей базы для снимка /poh-report: покрытие целей, изолированные
узлы (workslop), противоречия, вытесненное, заземление, сообщества. Чистая (без
LLM). Спека: docs/superpowers/specs/2026-07-12-poh-impact-insight-report-design.md"""
from __future__ import annotations
import pathlib
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT
from poh_memory.query import _load_graph, kr_to_replica
from poh_memory.claims import episode_claims
from poh_memory.contradictions import candidate_pairs
from poh_memory.vocab import load_aspect_vocab, canonical_aspects, vocab_path_for


def _resolved(c: dict) -> bool:
    return bool(c.get("superseded_by") or c.get("invalid_at") or c.get("expired_at"))


def analyze(graph_name: str, nexus_root, host: str = FALKOR_HOST,
            port: int = FALKOR_PORT) -> dict:
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    all_entities = {r[0] for r in g.query("MATCH (n:Entity) RETURN n.name").result_set if r[0]}
    n_claims = g.query("MATCH (c:Claim) RETURN count(c)").result_set[0][0]
    G = _load_graph(graph_name, host=host, port=port)  # семантич. граф (узлы с рёбрами)
    isolated = sorted(all_entities - set(G.nodes()))  # Entity без семантич. рёбер = workslop
    krs = [n for n in all_entities if n.startswith("kr-")]
    goal_coverage = {kr: len(kr_to_replica(graph_name, kr)) for kr in krs}  # instance-global config
    empty_krs = sorted([kr for kr, n in goal_coverage.items() if n == 0])
    claims = episode_claims(pathlib.Path(nexus_root))
    # словарь живёт в волте (не в cwd) — иначе при запуске извне он пуст и ВСЕ
    # аспекты молча уезжают в off_vocab
    canon = canonical_aspects(load_aspect_vocab(vocab_path_for(nexus_root)))
    off_vocab = sorted({c["aspect"] for c in claims if c["aspect"] not in canon})
    grounded = sum(1 for c in claims if c.get("grounded_node"))
    contradictions = candidate_pairs(claims)
    superseded = [c for c in claims if _resolved(c)]
    comm_rows = g.query("MATCH (n:Entity) WHERE n.community_id IS NOT NULL "
                        "RETURN n.community_id, count(n)").result_set
    sizes = {cid: cnt for cid, cnt in comm_rows}
    top = sorted(((cid, cnt - 1) for cid, cnt in sizes.items()), key=lambda x: (-x[1], x[0]))
    return {
        "stats": {"entities": len(all_entities), "claims": n_claims, "sem_edges": G.number_of_edges()},
        "goal_coverage": goal_coverage,
        "empty_krs": empty_krs,
        "isolated_nodes": isolated,
        "grounding": {"grounded": grounded, "ungrounded": len(claims) - grounded},
        "off_vocab_aspects": off_vocab,
        "contradictions": contradictions,
        "superseded_claims": superseded,
        "communities": {"count": len(sizes), "sizes": sizes, "top_by_blast_radius": top},
    }
