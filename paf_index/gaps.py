from __future__ import annotations
from dataclasses import dataclass
from paf_index.frontmatter import Node
from paf_index.derive import Edge, NewNode

@dataclass
class Gap:
    src: str
    reason: str   # "isolated" | "no-serves"
    title: str

# Value-axis edge types (FNR-4). Distinct from spine/ownership (SERVES/DELIVERS/
# OWNS) and weak association (MENTIONS): these express the PAF value chain.
VALUE_AXIS_EDGES = {"REALIZES", "BASED_ON", "DEPENDS_ON",
                    "ADDRESSES", "SATISFIES", "HAS_NEED"}

# Nexuses that carry the PAF value chain. team (People Graph), okr (goal spine)
# and pulse (episodes) live on other planes and are NOT value-axis-eligible.
VALUE_AXIS_NEXUSES = {"product", "customer", "growth", "market", "system"}

def is_value_axis_eligible(n: Node) -> bool:
    """True for content nodes that SHOULD sit on the PAF value axis (I5 scope)."""
    return is_value_content(n) and n.nexus in VALUE_AXIS_NEXUSES

def _title(n: Node) -> str:
    return str(n.frontmatter.get("title") or n.node_id)

def value_axis_gaps(nodes: list[Node], edges: list[Edge],
                    content_filter=None) -> list[str]:
    """Content nodes with NO incident value-axis edge (oracle I5, FNR-4).

    A node may be reachable from the KR spine via OWNS/DELIVERS yet still not be
    wired into the PAF value chain (REALIZES/ADDRESSES/BASED_ON/...). This finds
    such nodes. `content_filter`, if given, restricts to value-axis content
    (framework scaffolding excluded). Returns sorted node_ids.
    """
    on_axis: set[str] = set()
    for e in edges:
        if e.type in VALUE_AXIS_EDGES:
            on_axis.add(e.src)
            on_axis.add(e.dst)
    content = (n for n in nodes if content_filter is None or content_filter(n))
    return sorted(n.node_id for n in content if n.node_id not in on_axis)

def find_gaps(nodes: list[Node], edges: list[Edge]) -> list[Gap]:
    incident: dict[str, int] = {}
    serves_src: set[str] = set()
    for e in edges:
        incident[e.src] = incident.get(e.src, 0) + 1
        incident[e.dst] = incident.get(e.dst, 0) + 1
        if e.type == "SERVES":
            serves_src.add(e.src)
    out: list[Gap] = []
    for n in nodes:
        isolated = incident.get(n.node_id, 0) == 0 and not n.manages and not n.reports_to
        if isolated:
            out.append(Gap(n.node_id, "isolated", _title(n)))
        elif n.nexus == "system" and n.node_id not in serves_src:
            out.append(Gap(n.node_id, "no-serves", _title(n)))
    return out

def is_value_content(n: Node) -> bool:
    """True for value-axis / spine content nodes; False for framework
    scaffolding (step-overview overviews, MOC `_index`/`_template`/`_registry`
    files) that must not count in value-axis reachability (FNR-4 oracle)."""
    if n.node_type == "step-overview":
        return False
    if n.path.stem.startswith("_"):
        return False
    return True

@dataclass
class ReachReport:
    reachable: set[str]
    unreachable: list[str]   # node_ids not reachable from KR spine (sorted)
    fraction: float          # reachable content nodes / total nodes

def reachability_from_kr(nodes: list[Node], edges: list[Edge],
                         edge_types: set[str] | None = None,
                         content_filter=None) -> ReachReport:
    """Measure connectivity of the graph to the KR spine (oracle I4/I6).

    BFS from every `key-result` node over edges treated as undirected. If
    `edge_types` is given, only those edge types are traversed (e.g. exclude
    MENTIONS to measure typed connectivity).

    `content_filter`, if given, is a predicate node -> bool selecting value-axis
    content nodes. The fraction and the `unreachable` list are then computed
    only over content nodes (framework scaffolding — step-overview / MOC index /
    templates — is excluded from the denominator but still traversed as a
    waypoint). Returns the full reachable set regardless of the filter.
    """
    node_ids = {n.node_id for n in nodes}
    adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for e in edges:
        if edge_types is not None and e.type not in edge_types:
            continue
        if e.src in adj and e.dst in adj:
            adj[e.src].add(e.dst)
            adj[e.dst].add(e.src)
    seeds = [n.node_id for n in nodes if n.node_type == "key-result"]
    reachable: set[str] = set()
    stack = list(seeds)
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        stack.extend(adj[cur] - reachable)
    if content_filter is None:
        counted = node_ids
    else:
        counted = {n.node_id for n in nodes if content_filter(n)}
    unreachable = sorted(counted - reachable)
    fraction = len(reachable & counted) / len(counted) if counted else 0.0
    return ReachReport(reachable=reachable, unreachable=unreachable, fraction=fraction)

def kr_choices(new_nodes: list[NewNode], nodes: list[Node]) -> list[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for nn in new_nodes:
        if nn.node_type == "key-result":
            out.add((nn.node_id, nn.title))
    for n in nodes:
        if n.node_type == "key-result":
            out.add((n.node_id, _title(n)))
    return sorted(out)
