from __future__ import annotations
import re, pathlib
from dataclasses import dataclass

_JIRA_RE = re.compile(r"[A-Z]{2,}-\d+")
_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")

@dataclass
class KrRow:
    kr_id: str
    title: str
    epic_key: str | None
    objective_id: str

def parse_kr_epic_map(path: pathlib.Path) -> list[KrRow]:
    rows: list[KrRow] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 3:
            continue
        kr, title, epic = cells[0], cells[1], cells[2]
        # skip header + separator rows
        if kr in ("KR", "") or set(kr) <= set("-: "):
            continue
        if not re.match(r"^\d+(\.\d+)*", kr):
            continue
        jira = _JIRA_RE.search(epic)
        rows.append(KrRow(
            kr_id=kr,
            title=title,
            epic_key=jira.group(0) if jira else None,
            objective_id=kr.split(".")[0],
        ))
    return rows
