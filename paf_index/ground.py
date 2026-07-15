from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class GroundedRef:
    ref: str
    target: str
    plane: str    # "nexus" | "jira"
    trust: str    # "high" | "medium"
    resolved: bool = True


@dataclass
class GroundingResult:
    grounded: list[GroundedRef] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


def ground_refs(episode, node_ids: set[str]) -> GroundingResult:
    res = GroundingResult()
    for ref in episode.nexus_refs:
        if ref in node_ids:
            res.grounded.append(GroundedRef(ref, ref, "nexus", "high"))
        else:
            res.unresolved.append(ref)
    for key in episode.jira_refs:
        if key in node_ids:
            # collision with a real vault node id — nexus plane wins
            res.grounded.append(GroundedRef(key, key, "nexus", "high"))
        else:
            res.grounded.append(GroundedRef(key, "task-" + key, "jira", "medium"))
    return res
