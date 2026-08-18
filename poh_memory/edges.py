"""Чтение СЕМАНТИЧЕСКИХ рёбер из материализованного frontmatter vault.

Правило 1: граф = фактические frontmatter-рёбра (хребет + ценностная ось PAF),
НЕ пере-деривка (иначе теряются материализованные рёбра инкремента-5).
Правило 2: только семантические рёбра; owns_node/involves ИСКЛЮЧЕНЫ (единый
владелец = мега-хаб, губит многошаг).
Правило 3: вокабуляр ценностной оси берётся из paf_index.derive.FIELD_PREDICATES —
один источник на оба яруса. Разойдись они, L2 молча терял бы value-контент:
узел минтится только как конец семантического ребра.
"""
from __future__ import annotations
import pathlib
from paf_index import frontmatter as fm
from paf_index.derive import FIELD_PREDICATES

# Хребет OKR (serves/delivered_by) + слабая ассоциация (mentions) + ценностная
# ось PAF (realizes/based_on/depends_on/addresses/satisfies/has_need).
SEM_FIELDS = {"serves": "SERVES", "delivered_by": "DELIVERS", "mentions": "MENTIONS",
              **FIELD_PREDICATES}


def _all_nodes(nexus_root: pathlib.Path):
    nodes = list(fm.load_all_nexus_notes(nexus_root))
    for sub in ("okr", "pulse", "jira"):
        p = nexus_root / sub
        if p.exists():
            nodes += list(fm.load_all_nexus_notes(p))
    return list({n.node_id: n for n in nodes}.values())


def semantic_edges(nexus_root: pathlib.Path) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for n in _all_nodes(nexus_root):
        for field, etype in SEM_FIELDS.items():
            v = n.frontmatter.get(field)
            if not v:
                continue
            for dst in ([v] if isinstance(v, str) else v):
                out.append((n.node_id, str(dst), etype))
    return out


def node_titles(nexus_root: pathlib.Path) -> dict[str, str]:
    return {n.node_id: str(n.frontmatter.get("title") or n.node_id)
            for n in _all_nodes(nexus_root)}
