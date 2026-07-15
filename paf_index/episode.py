from __future__ import annotations
import re, pathlib
from dataclasses import dataclass
from paf_index.frontmatter import parse_frontmatter

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
_TRANSCRIPT_RE = re.compile(r"(transcript-[\w-]+|\d{6,})")
_JIRA_RE = re.compile(r"[A-Z]{2,}-\d+")

@dataclass
class Episode:
    episode_id: str
    source_note: str
    date: str
    transcript: str | None
    participants: list[str]
    nexus_refs: list[str]
    jira_refs: list[str]
    path: pathlib.Path

def _dedup(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def parse_summary(path: pathlib.Path) -> Episode | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fmd, body = parse_frontmatter(text)
    if not fmd or fmd.get("дата") is None:
        return None

    date = str(fmd["дата"])[:10]

    src = fmd.get("источник")
    transcript = None
    if src:
        m = _TRANSCRIPT_RE.search(str(src))
        transcript = m.group(1) if m else None

    parts_raw = fmd.get("участники")
    if isinstance(parts_raw, list):
        participants = [str(p).strip() for p in parts_raw if str(p).strip()]
    elif parts_raw:
        participants = [p.strip() for p in str(parts_raw).split(",") if p.strip()]
    else:
        participants = []

    refs = []
    nl = fmd.get("nexus_links")
    if isinstance(nl, list):
        refs.extend(str(x).strip() for x in nl)
    refs.extend(m.strip() for m in _WIKILINK_RE.findall(body))
    nexus_refs = _dedup([r for r in refs if r])

    fm_text = " ".join(str(v) for v in fmd.values())
    jira_refs = _dedup(_JIRA_RE.findall(fm_text) + _JIRA_RE.findall(body))

    return Episode(
        episode_id="pulse-" + path.stem,
        source_note=path.relative_to(path.parents[3]).as_posix()
            if len(path.parents) >= 4 else str(path),
        date=date,
        transcript=transcript,
        participants=participants,
        nexus_refs=nexus_refs,
        jira_refs=jira_refs,
        path=path,
    )

def load_summaries(summaries_dir: pathlib.Path) -> list[Episode]:
    eps = []
    for p in sorted(summaries_dir.glob("*.md")):
        ep = parse_summary(p)
        if ep is not None:
            eps.append(ep)
    return eps
