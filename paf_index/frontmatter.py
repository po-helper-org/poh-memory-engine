from __future__ import annotations
import re, pathlib
from dataclasses import dataclass, field
import yaml

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)

@dataclass
class Node:
    node_id: str
    node_type: str | None
    nexus: str | None
    owner: str | None
    full_name: str | None
    sources: list[str]
    manages: list[str]
    reports_to: str | None
    collaborates_with: list[str]
    updated: str | None
    ttl_days: int | None
    confidence: float | None
    ripeness: str | None
    path: pathlib.Path
    frontmatter: dict = field(default_factory=dict)

def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(data, dict):
        return {}, text
    return data, m.group(2)

def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]

def load_note(path: pathlib.Path) -> Node | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fmd, _ = parse_frontmatter(text)
    nid = fmd.get("node_id")
    if not nid:
        return None
    return Node(
        node_id=str(nid),
        node_type=fmd.get("node_type"),
        nexus=fmd.get("nexus"),
        owner=fmd.get("owner"),
        full_name=fmd.get("full_name"),
        sources=_as_list(fmd.get("sources")),
        manages=_as_list(fmd.get("manages")),
        reports_to=fmd.get("reports_to"),
        collaborates_with=_as_list(fmd.get("collaborates_with")),
        updated=str(fmd["updated"]) if fmd.get("updated") is not None else None,
        ttl_days=fmd.get("ttl_days"),
        confidence=fmd.get("confidence"),
        ripeness=fmd.get("ripeness"),
        path=path,
        frontmatter=fmd,
    )

def load_all_nexus_notes(nexus_root: pathlib.Path) -> list[Node]:
    nodes = []
    for p in sorted(nexus_root.rglob("*.md")):
        n = load_note(p)
        if n is not None:
            nodes.append(n)
    return nodes
