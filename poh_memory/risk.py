"""Риск-движок #5-A: детерминированный синтез рисков из готовых сигналов.
severity/affected_krs — чистые; synthesize_risks собирает reflexion-флаги,
противоречия и supersession в типизированные риск-узлы (модель §4.6.1).
Спека: docs/superpowers/specs/2026-07-13-poh-risk-engine-a-design.md"""
from __future__ import annotations
import hashlib
import pathlib
import yaml
import networkx as nx
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT
from poh_memory.reflexion import node_contexts
from poh_memory.claims import episode_claims
from poh_memory.contradictions import candidate_pairs
from poh_memory.communities import blast_radius
from poh_memory.query import _load_graph

_DATE_KW = ("срок", "дата", "дедлайн", "релиз")
_RISK_SOURCE = "signal-synthesis"
_CLASSIFY_SOURCE = "agent-classify"   # #5-B2 /risk-classify track — separate drop-first scope from synthesis
_AXES = {"schedule_slip", "expectation_divergence", "requirements_change", "understanding_gap"}


def _risk_id(r: dict) -> str:
    """Content-hash id. Hashes axis + evidence + affected_kr. Empty-evidence-safe."""
    ev = " ".join(r.get("evidence") or [])
    kr = ",".join(r.get("affected_kr") or [])
    h = hashlib.sha1(f"{r['axis']}|{ev}|{kr}".encode("utf-8")).hexdigest()[:8]
    return f"risk-{r['axis']}-{h}"


def gate(risks: list[dict], review_threshold: float = 0.5) -> dict:
    """Route risks into three buckets: verified (has affected_kr), review (severity >= threshold),
    unlinkable (severity < threshold). Every risk routed exactly once."""
    out: dict = {"verified": [], "review": [], "unlinkable": []}
    for r in risks:
        if r["affected_kr"]:
            out["verified"].append(r)
        elif r["severity"] >= review_threshold:
            out["review"].append(r)
        else:
            out["unlinkable"].append(r)
    return out


def write_queue(gated: dict, path) -> pathlib.Path:
    """Write {review, unlinkable} to yaml. Creates parent dirs. Keeps evidence/participants as lists.
    verified risks are NOT written to queue."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump({"review": gated["review"], "unlinkable": gated["unlinkable"]},
                       allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return p


def severity(blast: int, n_conflicting: int, grounding_confidence: float | None,
             blast_dist: list[int] | None = None) -> float:
    """0..1. blast_dist given -> graph-relative percentile of blast (calibrated, #5-B3);
    None -> legacy absolute blast/10 (uncalibrated; for graph-less callers/tests only,
    NOT a runtime fallback). Weights 0.5/0.3/0.2 and n_conflicting/3 are policy (unchanged)."""
    if blast_dist is not None:
        blast_n = percentile_rank(blast, blast_dist)
    else:
        blast_n = min(blast / 10, 1.0)
    conf_n = min(n_conflicting / 3, 1.0)
    gc = grounding_confidence if grounding_confidence is not None else 0.5
    raw = 0.5 * blast_n + 0.3 * conf_n + 0.2 * (1.0 - gc)
    return round(min(1.0, raw), 3)


def blast_distribution(graph_name: str, host: str = FALKOR_HOST,
                       port: int = FALKOR_PORT) -> list[int]:
    """Ascending-sorted blast-radius sizes of every :Entity graph node.
    Population for graph-relative severity percentile (#5-B3). Reads only; mints nothing.
    Population = :Entity nodes (the grounding-eligible universe blast_radius operates on).
    :Claim/:Risk are excluded by construction (not :Entity). Isolated :Entity without
    community_id count as legitimate zero-blast members (blast_radius returns [] -> len 0)."""
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    res = g.query("MATCH (n:Entity) RETURN n.name")
    names = [row[0] for row in res.result_set if row[0] is not None]
    return sorted(len(blast_radius(graph_name, name, host=host, port=port)) for name in names)


def percentile_rank(value: int, dist: list[int]) -> float:
    """Mid-rank (Hazen) percentile of value within dist. Range 0..1.
    (count(x<value) + 0.5*count(x==value)) / len(dist). Empty dist -> 0.5.
    All-equal dist -> 0.5 for every value (neutral, not 1.0). Order-independent."""
    n = len(dist)
    if n == 0:
        return 0.5
    below = sum(1 for x in dist if x < value)
    equal = sum(1 for x in dist if x == value)
    return (below + 0.5 * equal) / n


def affected_krs(G, node) -> list[str]:
    """KR-узлы (префикс 'kr-') со связностью до node в undirected графе.
    [] если node вне графа (изолированный) — иначе nx.has_path бросил бы NodeNotFound."""
    if node not in G:
        return []
    return sorted(kr for kr in G
                  if kr.startswith("kr-") and kr != node and nx.has_path(G, kr, node))


def _grounding(claim_list) -> float | None:
    """Среднее confidence по списку; None если список пуст или все confidence=None."""
    vals = [c["confidence"] for c in claim_list if c.get("confidence") is not None]
    return sum(vals) / len(vals) if vals else None


def synthesize_risks(graph_name: str, nexus_root, host: str = FALKOR_HOST,
                     port: int = FALKOR_PORT) -> list[dict]:
    """Детерминированный синтез рисков из 4 осей: understanding_gap, expectation_divergence,
    requirements_change, schedule_slip. Без LLM. Read-only."""
    contexts = node_contexts(graph_name, nexus_root, host=host, port=port)
    claims = episode_claims(pathlib.Path(nexus_root))
    pairs = candidate_pairs(claims)
    G = _load_graph(graph_name, host=host, port=port)
    dist = blast_distribution(graph_name, host=host, port=port)

    def _blast(node) -> int:
        return len(blast_radius(graph_name, node, host=host, port=port)) if node else 0

    risks: list[dict] = []

    # understanding_gap: изолированные / workslop-узлы
    for c in contexts:
        f = c["flags"]
        if f["isolated"] or f["workslop_no_sources"]:
            node = c["node_id"]
            risks.append({
                "axis": "understanding_gap",
                "severity": severity(_blast(node), 1, None, blast_dist=dist),
                "evidence": [f"{node}: isolated={f['isolated']}, workslop_no_sources={f['workslop_no_sources']}"],
                "affected_kr": affected_krs(G, node),
                "participants": [], "valid_time": None, "confidence": None,
            })

    # expectation_divergence: противоречащие пары
    for a, b in pairs:
        node = a["grounded_node"]
        gc = _grounding([a, b])
        risks.append({
            "axis": "expectation_divergence",
            "severity": severity(_blast(node), 2, gc, blast_dist=dist),
            "evidence": [f"{a['polarity']}: {a['value'][:60]}", f"{b['polarity']}: {b['value'][:60]}"],
            "affected_kr": affected_krs(G, node),
            "participants": sorted({s for s in (a.get("speaker"), b.get("speaker")) if s}),
            "valid_time": None, "confidence": gc,
        })

    # requirements_change (+ schedule_slip): вытесненные claim'ы (напрямую из episode_claims)
    for c in claims:
        if not (c.get("superseded_by") or c.get("invalid_at") or c.get("expired_at")):
            continue
        node = c.get("grounded_node")
        hay = f"{c.get('aspect', '')} {c.get('value', '')}".lower()
        axis = "schedule_slip" if any(k in hay for k in _DATE_KW) else "requirements_change"
        risks.append({
            "axis": axis,
            "severity": severity(_blast(node), 1, c.get("confidence"), blast_dist=dist),
            "evidence": [f"вытеснено: {c.get('aspect')}={str(c.get('value'))[:60]}"],
            "affected_kr": affected_krs(G, node) if node else [],
            "participants": [s for s in [c.get("speaker")] if s],
            "valid_time": c.get("invalid_at") or c.get("expired_at"),
            "confidence": c.get("confidence"),
        })

    return risks


def build_risk(axis: str, grounded_node, evidence, participants, confidence,
               graph_name: str, host: str = FALKOR_HOST, port: int = FALKOR_PORT) -> dict:
    """Собрать риск-объект #5-A-формы из агент-классификации (детерм.).
    axis ∈ _AXES; evidence непуст. grounded_node пуст -> affected_kr=[]/blast=0
    (blast_radius/affected_krs НЕ вызываются на None)."""
    if axis not in _AXES:
        raise ValueError(f"unknown axis: {axis!r}; must be one of {sorted(_AXES)}")
    if not evidence:
        raise ValueError("evidence required (§4.6.1.5): риск без evidence не создаётся")
    if grounded_node:
        G = _load_graph(graph_name, host=host, port=port)
        affected_kr = affected_krs(G, grounded_node)
        blast = len(blast_radius(graph_name, grounded_node, host=host, port=port))
        dist = blast_distribution(graph_name, host=host, port=port)
        sev = severity(blast, 1, confidence, blast_dist=dist)
    else:
        affected_kr = []
        # No graph grounding: agent confidence is the direct severity proxy (no blast available).
        sev = float(confidence) if confidence is not None else 0.0
    return {
        "axis": axis,
        "severity": round(min(1.0, sev), 3),
        "evidence": list(evidence),
        "affected_kr": affected_kr,
        "participants": list(participants or []),
        "valid_time": None,
        "confidence": confidence,
    }


def materialize_risks(graph_name: str, verified_risks: list[dict],
                      host: str = FALKOR_HOST, port: int = FALKOR_PORT,
                      source: str = _RISK_SOURCE, drop_first: bool = True) -> int:
    """Write verified risks as :Risk graph nodes + AFFECTS->KR edges (gate §4.7 verified route).
    source-scoped drop-first drops prior Risk{source:<source>} only when drop_first=True;
    drop_first=False accumulates (MERGE by stable id, no delete) — used by the one-at-a-time
    classify track (source='agent-classify'). Returns count of risks written.
    :Risk nodes are isolated from PPR (_load_graph excludes them)."""
    g = FalkorDB(host=host, port=port).select_graph(graph_name)
    if drop_first:
        g.query("MATCH (r:Risk {source:$s}) DETACH DELETE r", {"s": source})   # source-scoped drop-first
    n = 0
    for r in verified_risks:
        rid = _risk_id(r)
        g.query(
            "MERGE (r:Risk {name:$id}) SET r.source=$s, r.axis=$axis, r.severity=$sev, "
            "r.evidence=$ev, r.valid_time=$vt, r.confidence=$conf, r.participants=$parts",
            {"id": rid, "s": source, "axis": r["axis"], "sev": r["severity"],
             "ev": " | ".join(r.get("evidence") or []), "vt": r.get("valid_time"),
             "conf": r.get("confidence"), "parts": " | ".join(r.get("participants") or [])},
        )
        for kr in r.get("affected_kr") or []:
            g.query("MATCH (r:Risk {name:$id}) MATCH (k:Entity {name:$kr}) "
                    "MERGE (r)-[:AFFECTS]->(k)", {"id": rid, "kr": kr})
        n += 1
    return n
