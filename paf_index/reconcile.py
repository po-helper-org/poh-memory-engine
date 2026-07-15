from __future__ import annotations
import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from paf_index.frontmatter import Node
from paf_index.derive import Edge, NewNode

REQUIRED = ["nexus", "node_id", "node_type", "kind", "owner",
            "confidence", "sources", "updated", "ttl_days", "ripeness"]

@dataclass
class ReconcileReport:
    isolated: list[str] = field(default_factory=list)
    workslop: list[str] = field(default_factory=list)
    dangling: list[tuple[str, str, str]] = field(default_factory=list)
    ownerless_kr: list[str] = field(default_factory=list)
    context_ripeness: dict[str, float] = field(default_factory=dict)

def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))

def _age_days(updated: str | None, today: str) -> int | None:
    if not updated:
        return None
    try:
        u = datetime.date.fromisoformat(updated[:10])
        t = datetime.date.fromisoformat(today)
        return (t - u).days
    except ValueError:
        return None

def context_ripeness(nodes: list[Node], today: str) -> dict[str, float]:
    by_nexus: dict[str, list[Node]] = defaultdict(list)
    for n in nodes:
        by_nexus[n.nexus or "?"].append(n)
    out: dict[str, float] = {}
    for nx, ns in by_nexus.items():
        complete = sum(1 for n in ns if all(n.frontmatter.get(k) not in (None, "", []) for k in REQUIRED))
        completeness = complete / len(ns) if ns else 0.0
        num = den = 0.0
        for n in ns:
            age = _age_days(n.updated, today)
            ttl = n.ttl_days or 0
            if age is None or not ttl:
                continue
            # Nodes missing an explicit confidence value default to a neutral 0.5 weight
            w = float(n.confidence) if n.confidence is not None else 0.5
            num += _clamp(1 - age / ttl) * w
            den += w
        freshness = (num / den) if den else 0.0
        out[nx] = round(completeness * freshness, 3)
    return out

def reconcile(nodes: list[Node], new_nodes: list[NewNode], edges: list[Edge], today: str) -> ReconcileReport:
    rep = ReconcileReport()
    all_ids = {n.node_id for n in nodes} | {nn.node_id for nn in new_nodes}
    incident: dict[str, int] = defaultdict(int)
    for e in edges:
        incident[e.src] += 1
        incident[e.dst] += 1
        # dangling: dst must be a node; DELIVERS src is a JIRA epic key (allowed non-node)
        if e.dst not in all_ids:
            rep.dangling.append((e.src, e.type, e.dst))
        if e.type != "DELIVERS" and e.src not in all_ids:
            rep.dangling.append((e.src, e.type, e.dst))
    for n in nodes:
        if not n.sources:
            rep.workslop.append(n.node_id)
        if incident[n.node_id] == 0 and not n.manages and not n.reports_to:
            rep.isolated.append(n.node_id)
    for nn in new_nodes:
        if nn.node_type == "key-result" and incident[nn.node_id] == 0:
            rep.ownerless_kr.append(nn.node_id)
    rep.context_ripeness = context_ripeness(nodes, today)
    return rep

@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    ripeness_min: float = 0.0

def check_invariants(nodes: list[Node], new_nodes: list[NewNode], edges: list[Edge]) -> dict:
    kr_ids = {nn.node_id for nn in new_nodes if nn.node_type == "key-result"} | \
             {n.node_id for n in nodes if n.node_type == "key-result"}
    obj_ids = {nn.node_id for nn in new_nodes if nn.node_type == "objective"} | \
              {n.node_id for n in nodes if n.node_type == "objective"}
    # OWNS edge convention: Edge("OWNS", owned_node, owner_person).
    # Index by the owned node (src) so ownership can be looked up per KR.
    owners_of: dict[str, set] = defaultdict(set)    # owned_node -> {owner person}
    serves_up: dict[str, set] = defaultdict(set)    # kr -> {obj}
    serves_into: dict[str, set] = defaultdict(set)  # obj -> {kr}
    for e in edges:
        if e.type == "OWNS":
            owners_of[e.src].add(e.dst)
        elif e.type == "SERVES":
            serves_up[e.src].add(e.dst)
            serves_into[e.dst].add(e.src)
    kr_without_owns = sorted(k for k in kr_ids if not owners_of.get(k))
    spine_orphans = sorted(
        [k for k in kr_ids if not serves_up.get(k)] +
        [o for o in obj_ids if not serves_into.get(o)]
    )
    ownership_contradictions = [
        (k, "multiple-owns", ",".join(sorted(owners_of[k])))
        for k in sorted(kr_ids) if len(owners_of.get(k, set())) > 1
    ]
    return {"kr_without_owns": kr_without_owns,
            "spine_orphans": spine_orphans,
            "ownership_contradictions": ownership_contradictions}

def gate(report: ReconcileReport, invariants: dict, threshold: float = 0.6) -> GateResult:
    reasons: list[str] = []
    rip = report.context_ripeness or {}
    ripeness_min = min(rip.values()) if rip else 0.0
    if ripeness_min < threshold:
        reasons.append(f"ContextRipeness мин {round(ripeness_min, 3)} < {threshold}")
    if report.dangling:
        reasons.append(f"{len(report.dangling)} dangling рёбер")
    if invariants["kr_without_owns"]:
        reasons.append(f"{len(invariants['kr_without_owns'])} KR без OWNS→person")
    if invariants["spine_orphans"]:
        reasons.append(f"{len(invariants['spine_orphans'])} сирот спайна")
    if invariants["ownership_contradictions"]:
        reasons.append(f"{len(invariants['ownership_contradictions'])} противоречий владения")
    return GateResult(passed=not reasons, reasons=reasons, ripeness_min=round(ripeness_min, 3))

def status_dict(gr: GateResult, today: str) -> dict:
    return {"ready": gr.passed, "ripeness_min": gr.ripeness_min,
            "reasons": gr.reasons, "checked": today}
