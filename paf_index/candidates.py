from __future__ import annotations
from dataclasses import dataclass, asdict
import pathlib
import yaml
from paf_index.gaps import Gap
from paf_index.derive import Edge

@dataclass
class Candidate:
    src: str
    reason: str
    title: str
    dst: str | None = None
    confidence: float | None = None
    rationale: str = ""
    status: str = "open"

def load_candidates(path: pathlib.Path) -> list[Candidate]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    out: list[Candidate] = []
    for d in data:
        out.append(Candidate(
            src=str(d["src"]),
            reason=str(d.get("reason", "")),
            title=str(d.get("title", "")),
            dst=(str(d["dst"]) if d.get("dst") else None),
            confidence=(float(d["confidence"]) if d.get("confidence") is not None else None),
            rationale=str(d.get("rationale", "")),
            status=str(d.get("status", "open")),
        ))
    return out

def save_candidates(path: pathlib.Path, items: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(c) for c in sorted(items, key=lambda c: c.src)]
    path.write_text(yaml.safe_dump(rows, allow_unicode=True, sort_keys=False), encoding="utf-8")

def seed_gaps(path: pathlib.Path, gaps: list[Gap]) -> int:
    gap_by_src = {g.src: g for g in gaps}
    existing = {c.src: c for c in load_candidates(path)}
    added = 0
    for src, g in gap_by_src.items():
        if src not in existing:
            existing[src] = Candidate(src=src, reason=g.reason, title=g.title, status="open")
            added += 1
    for src, c in existing.items():
        if c.status == "open" and src not in gap_by_src:
            c.status = "resolved"
    save_candidates(path, list(existing.values()))
    return added

def promote(path: pathlib.Path, nodes_by_id: dict, today: str, run_gate_fn=None):
    from paf_index import write
    items = load_candidates(path)
    kr_ids = {nid for nid, n in nodes_by_id.items()
              if getattr(n, "node_type", None) == "key-result"}
    edges: list[Edge] = []
    to_mark: list[Candidate] = []
    skipped: list[str] = []
    for c in items:
        if c.status != "approved":
            continue
        if not c.dst or c.src not in nodes_by_id or c.dst not in kr_ids:
            skipped.append(c.src)
            continue
        conf = str(c.confidence) if c.confidence is not None else "0.5"
        edges.append(Edge("SERVES", c.src, c.dst, "semantic:agent", conf, today, today))
        to_mark.append(c)
    changed = write.apply_edges(edges, nodes_by_id) if edges else 0
    issues = run_gate_fn() if run_gate_fn is not None else []
    if not issues:
        for c in to_mark:
            c.status = "promoted"
        save_candidates(path, items)
    return changed, issues, skipped
