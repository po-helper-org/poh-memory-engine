"""Reflexion (#4) — верификация понимания. Детерминированный ярус (без LLM):
node_contexts собирает контекст+структурные флаги на каждый Entity-узел;
aggregate сводит вердикты агента в отчёт (структурные очереди — из детерм. флагов,
не из agent-issues). Спека: docs/superpowers/specs/2026-07-13-poh-reflexion-design.md"""
from __future__ import annotations
import pathlib
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT
from poh_memory.query import _load_graph
from poh_memory.claims import episode_claims
from poh_memory.contradictions import candidate_pairs
from paf_index.frontmatter import load_all_nexus_notes


def node_contexts(graph_name: str, nexus_root, host: str = FALKOR_HOST,
                  port: int = FALKOR_PORT) -> list[dict]:
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    rows = g.query("MATCH (n:Entity) RETURN n.name, n.summary").result_set   # имена + summary
    G = _load_graph(graph_name, host=host, port=port)                        # семантич. граф (без изолированных)
    notes = {n.node_id: n for n in load_all_nexus_notes(pathlib.Path(nexus_root))}  # ВСЕ нексус-ноты (rglob)
    contra = {c["grounded_node"]
              for a, b in candidate_pairs(episode_claims(pathlib.Path(nexus_root)))
              for c in (a, b)}
    out: list[dict] = []
    for name, summary in rows:
        if not name:
            continue
        neighbors = ([(G[name][nbr]["type"], nbr) for nbr in G.neighbors(name)]
                     if name in G else [])   # guard: изолированный узел не в G
        out.append({
            "node_id": name,
            "summary": summary,
            "neighbors": neighbors,
            "flags": {
                "isolated": name not in G,
                "workslop_no_sources": (name not in notes) or (not notes[name].frontmatter.get("sources")),
                "in_contradiction": name in contra,
            },
        })
    return out


def aggregate(contexts: list[dict], verdicts: list[dict]) -> dict:
    total = len(contexts)
    understood = sum(1 for v in verdicts if v.get("understood"))
    share = round(understood / total, 3) if total else 0.0
    flags = {c["node_id"]: c["flags"] for c in contexts}

    def _q(flag: str) -> list[str]:
        return sorted(nid for nid, f in flags.items() if f.get(flag))

    not_understood = sorted(v["node_id"] for v in verdicts if not v.get("understood"))
    return {
        "total": total,
        "understood": understood,
        "share": share,
        "queues": {
            "not_understood": not_understood,
            "isolated": _q("isolated"),
            "workslop": _q("workslop_no_sources"),
            "contradictory": _q("in_contradiction"),
        },
    }
