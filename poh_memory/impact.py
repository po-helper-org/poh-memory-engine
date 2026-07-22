# poh_memory/impact.py
"""Impact-движок: снимок графа + чистый diff двух снимков (before/after).
Claims читаются из episode_claims(nexus_root) (граф не хранит grounded_node как
свойство). diff_snapshots — чистая функция, graph-name-agnostic.
Спека: docs/superpowers/specs/2026-07-12-poh-impact-insight-report-design.md"""
from __future__ import annotations
import pathlib
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT
from poh_memory.query import kr_to_replica
from poh_memory.claims import episode_claims
from poh_memory.contradictions import candidate_pairs

_SEM = ["SERVES", "DELIVERS", "MENTIONS"]


def graph_snapshot(graph_name: str, nexus_root, host: str = FALKOR_HOST,
                   port: int = FALKOR_PORT) -> dict:
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    nodes = {r[0] for r in g.query("MATCH (n:Entity) RETURN n.name").result_set if r[0]}
    edges = {(s, t, d) for s, t, d in g.query(
        "MATCH (a:Entity)-[r]->(b:Entity) WHERE type(r) IN ['SERVES','DELIVERS','MENTIONS'] "
        "RETURN a.name, type(r), b.name").result_set}
    communities = {r[0]: r[1] for r in g.query(
        "MATCH (n:Entity) WHERE n.community_id IS NOT NULL "
        "RETURN n.name, n.community_id").result_set}
    kr_episodes = {kr: [e["episode"] for e in kr_to_replica(graph_name, kr)]
                   for kr in nodes if kr.startswith("kr-")}
    claims = episode_claims(pathlib.Path(nexus_root))
    return {"nodes": nodes, "edges": edges, "communities": communities,
            "kr_episodes": kr_episodes, "claims": claims}


def _resolved(c: dict) -> bool:
    return bool(c.get("superseded_by") or c.get("invalid_at") or c.get("expired_at"))


def diff_snapshots(base: dict, cand: dict) -> dict:
    new_nodes = cand["nodes"] - base["nodes"]
    new_edges = cand["edges"] - base["edges"]
    connecting = {e for e in new_edges if (e[0] in base["nodes"]) ^ (e[2] in base["nodes"])}
    internal = {e for e in new_edges if e[0] in new_nodes and e[2] in new_nodes}
    base_ids = {c["id"] for c in base["claims"]}
    new_claims = [c for c in cand["claims"] if c["id"] not in base_ids]
    new_ids = {c["id"] for c in new_claims}
    new_contra = [(a, b) for a, b in candidate_pairs(cand["claims"])
                  if a["id"] in new_ids or b["id"] in new_ids]
    base_by_id = {c["id"]: c for c in base["claims"]}
    newly_superseded = [c for c in cand["claims"]
                        if _resolved(c) and not (c["id"] in base_by_id and _resolved(base_by_id[c["id"]]))]
    kr_delta = {}
    for kr, eps in cand["kr_episodes"].items():
        b, c = set(base["kr_episodes"].get(kr, [])), set(eps)
        gained, lost = sorted(c - b), sorted(b - c)
        if gained or lost:
            kr_delta[kr] = {"gained": gained, "lost": lost}
    touched_ids = new_nodes | {e[0] for e in connecting} | {e[2] for e in connecting}
    touched = sorted({cand["communities"][n] for n in touched_ids if n in cand["communities"]})
    return {"new_nodes": sorted(new_nodes), "connecting_edges": sorted(connecting),
            "internal_new_edges": sorted(internal), "new_claims": new_claims,
            "new_contradiction_pairs": new_contra, "newly_superseded": newly_superseded,
            "kr_coverage_delta": kr_delta, "touched_communities": touched}
