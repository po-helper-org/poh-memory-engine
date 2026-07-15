from __future__ import annotations
from collections import defaultdict
import re as _re
from paf_index.frontmatter import Node

def normalize_name(name: str | None) -> tuple[str, str] | None:
    if not name:
        return None
    toks = [t for t in str(name).replace('"', "").split() if t]
    if len(toks) < 2:
        return None
    return (toks[0].lower(), toks[1].lower())

def _person_index(persons: list[Node]) -> dict[tuple[str, str], list[str]]:
    idx: dict[tuple[str, str], list[str]] = defaultdict(list)
    for p in persons:
        key = normalize_name(p.full_name) or normalize_name(p.node_id.replace("team-", "").replace("-", " "))
        if key:
            idx[key].append(p.node_id)
    return idx

def resolve_owner(owner: str, persons: list[Node]) -> str | None:
    key = normalize_name(owner)
    if key is None:
        return None
    matches = _person_index(persons).get(key, [])
    return matches[0] if len(matches) == 1 else None

def resolve_person(name: str, persons: list[Node]) -> str | None:
    if not name:
        return None
    stripped = _re.sub(r"\s*\([^)]*\)\s*$", "", str(name)).strip()
    toks = [t for t in stripped.replace('"', "").split() if t]
    if len(toks) < 2:
        return None
    idx = _person_index(persons)
    for key in ((toks[0].lower(), toks[1].lower()), (toks[1].lower(), toks[0].lower())):
        matches = idx.get(key, [])
        if len(matches) == 1:
            return matches[0]
    return None
