from __future__ import annotations
from dataclasses import dataclass, field
from paf_index.frontmatter import Node, _as_list
from paf_index.okr import KrRow
from paf_index.resolve import resolve_owner, resolve_person
from paf_index.episode import Episode
from paf_index import ground as ground_mod

import os
# Client-agnostic defaults — the concrete vault overrides via env.
KR_SOURCE = os.environ.get("POH_KR_SOURCE", "okr:kr-epic-map")
DEFAULT_OWNER = os.environ.get("POH_DEFAULT_OWNER", "")

@dataclass
class Edge:
    type: str
    src: str
    dst: str
    source_anchor: str
    confidence: str
    valid_time: str
    ingest_time: str

# Value-axis predicate vocabulary (FNR-4): frontmatter field -> edge type.
# Deterministic tier — edges are authored in frontmatter, derived without LLM.
FIELD_PREDICATES = {
    "realizes": "REALIZES",
    "based_on": "BASED_ON",
    "depends_on": "DEPENDS_ON",
    "addresses": "ADDRESSES",
    "satisfies": "SATISFIES",
    "has_need": "HAS_NEED",
}

@dataclass
class ValueDeriveResult:
    edges: list["Edge"] = field(default_factory=list)
    dangling_refs: list[tuple[str, str]] = field(default_factory=list)

def derive_value_edges(nodes: list[Node], today: str) -> ValueDeriveResult:
    """Derive typed value-axis edges from authored frontmatter fields.

    For every node and every value-axis field present in its frontmatter,
    emit a typed Edge to each referenced node_id. References that do not
    resolve to an existing node are recorded as dangling (No Silent Drop),
    never emitted as edges.
    """
    r = ValueDeriveResult()
    existing = {n.node_id for n in nodes}
    for n in nodes:
        for fieldname, pred in FIELD_PREDICATES.items():
            for tgt in _as_list(n.frontmatter.get(fieldname)):
                if tgt in existing:
                    r.edges.append(Edge(pred, n.node_id, tgt,
                                        f"{fieldname} frontmatter", "high",
                                        today, today))
                else:
                    r.dangling_refs.append((n.node_id, tgt))
    return r

@dataclass
class NewNode:
    node_id: str
    node_type: str
    title: str
    frontmatter: dict

@dataclass
class DeriveResult:
    edges: list[Edge] = field(default_factory=list)
    new_nodes: list[NewNode] = field(default_factory=list)
    unresolved_owners: list[tuple[str, str]] = field(default_factory=list)

def kr_node_id(kr_id: str) -> str:
    return "kr-" + kr_id.replace(".", "-")

def obj_node_id(objective_id: str) -> str:
    return f"obj-{os.environ.get('POH_QUARTER', 'q')}-{objective_id}"

def _okr_frontmatter(node_id: str, node_type: str, title: str, today: str) -> dict:
    return {
        "nexus": "okr",
        "node_id": node_id,
        "node_type": node_type,
        "paf_step": None,
        "sprint_phase": None,
        "kind": "empirical",
        "owner": DEFAULT_OWNER,
        "confidence": 0.4,
        "sources": [KR_SOURCE],
        "updated": today,
        "ttl_days": 90,
        "ripeness": "fresh",
        "title": title,
    }

def derive(nodes: list[Node], kr_rows: list[KrRow], today: str) -> DeriveResult:
    r = DeriveResult()
    persons = [n for n in nodes if n.node_type == "person"]

    # OWNS edges
    for n in nodes:
        if not n.owner:
            continue
        pid = resolve_owner(n.owner, persons)
        if pid:
            r.edges.append(Edge("OWNS", n.node_id, pid, "owner field", "high", today, today))
        else:
            r.unresolved_owners.append((n.node_id, n.owner))

    # KR / OBJ nodes + SERVES + DELIVERS
    seen_kr: set[str] = set()
    seen_obj: set[str] = set()
    for row in kr_rows:
        kid = kr_node_id(row.kr_id)
        oid = obj_node_id(row.objective_id)
        if oid not in seen_obj:
            seen_obj.add(oid)
            r.new_nodes.append(NewNode(oid, "objective",
                f"Objective {row.objective_id}",
                _okr_frontmatter(oid, "objective", f"Objective {row.objective_id}", today)))
        if kid not in seen_kr:
            seen_kr.add(kid)
            r.new_nodes.append(NewNode(kid, "key-result", row.title,
                _okr_frontmatter(kid, "key-result", row.title, today)))
            r.edges.append(Edge("SERVES", kid, oid, KR_SOURCE, "high", today, today))
        if row.epic_key:
            r.edges.append(Edge("DELIVERS", row.epic_key, kid, KR_SOURCE, "high", today, today))

    # OWNS edges for the newly-created KR/OBJ spine nodes themselves, so
    # ownership is captured in the same pass instead of only appearing after
    # a second build once these notes exist on disk (single-pass idempotency).
    for nn in r.new_nodes:
        owner = nn.frontmatter.get("owner")
        if not owner:
            continue
        pid = resolve_owner(owner, persons)
        if pid:
            r.edges.append(Edge("OWNS", nn.node_id, pid, "owner field", "high", today, today))
        else:
            r.unresolved_owners.append((nn.node_id, owner))
    return r

@dataclass
class EpisodeDeriveResult:
    edges: list[Edge] = field(default_factory=list)
    new_nodes: list[NewNode] = field(default_factory=list)
    unresolved_participants: list[tuple[str, str]] = field(default_factory=list)
    dangling_refs: list[tuple[str, str]] = field(default_factory=list)

def _episode_frontmatter(ep: Episode, today: str) -> dict:
    src = f"транскрибация {ep.transcript}" if ep.transcript else ep.source_note
    return {
        "nexus": "pulse",
        "node_id": ep.episode_id,
        "node_type": "episode",
        "paf_step": None,
        "sprint_phase": None,
        "kind": "empirical",
        "owner": DEFAULT_OWNER,
        "confidence": 0.5,
        "sources": [src],
        "updated": ep.date,
        "ttl_days": 90,
        "ripeness": "fresh",
        "title": ep.episode_id,
        "source_note": ep.source_note,
    }

def _task_ref_frontmatter(key: str, today: str) -> dict:
    return {
        "nexus": "jira",
        "node_id": "task-" + key,
        "node_type": "task",
        "paf_step": None,
        "sprint_phase": None,
        "kind": "empirical",
        "owner": DEFAULT_OWNER,
        "confidence": 0.5,
        "sources": [f"JIRA:{key}"],
        "updated": today,
        "ttl_days": 90,
        "ripeness": "fresh",
        "title": key,
        "jira_key": key,
    }

def derive_episode_edges(episodes: list[Episode], nodes: list[Node], today: str) -> EpisodeDeriveResult:
    r = EpisodeDeriveResult()
    persons = [n for n in nodes if n.node_type == "person"]
    existing = {n.node_id for n in nodes}
    ep_by_stem = {ep.episode_id[len("pulse-"):]: ep.episode_id for ep in episodes}

    for ep in episodes:
        r.new_nodes.append(NewNode(ep.episode_id, "episode", ep.episode_id,
                                   _episode_frontmatter(ep, today)))

    seen_tasks: set[str] = set()
    for ep in episodes:
        anchor = ep.source_note
        gr = ground_mod.ground_refs(ep, existing)
        for g in gr.grounded:
            if g.plane == "jira":
                if g.target not in seen_tasks:
                    seen_tasks.add(g.target)
                    r.new_nodes.append(NewNode(g.target, "task", g.ref,
                                               _task_ref_frontmatter(g.ref, today)))
                r.edges.append(Edge("MENTIONS", ep.episode_id, g.target, anchor, "medium", ep.date, today))
            else:
                r.edges.append(Edge("MENTIONS", ep.episode_id, g.target, anchor, "high", ep.date, today))
        for ref in gr.unresolved:
            if ref in ep_by_stem:
                r.edges.append(Edge("MENTIONS", ep.episode_id, ep_by_stem[ref], anchor, "high", ep.date, today))
            else:
                r.dangling_refs.append((ep.episode_id, ref))
        for raw in ep.participants:
            pid = resolve_person(raw, persons)
            if pid:
                r.edges.append(Edge("involves", ep.episode_id, pid, anchor, "high", ep.date, today))
            else:
                r.unresolved_participants.append((ep.episode_id, raw))

    # OWNS edges for episodes, so ownership is captured in the same pass instead
    # of only appearing after a second build once these notes exist on disk
    # (single-pass idempotency).
    owner_pid = resolve_owner(DEFAULT_OWNER, persons)
    if owner_pid:
        for ep in episodes:
            r.edges.append(Edge("OWNS", ep.episode_id, owner_pid, "owner field", "high", ep.date, today))
    else:
        for ep in episodes:
            r.unresolved_participants.append((ep.episode_id, DEFAULT_OWNER))
    return r
