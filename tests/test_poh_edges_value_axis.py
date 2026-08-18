"""Ценностная ось PAF в L2 (Issue #9).

L1 (paf_index.derive) деривит типизированные рёбра ценностной оси из
frontmatter; L2 (poh_memory.edges) обязан читать те же поля с теми же типами,
иначе весь value-контент волта в граф не попадает (в графе остаётся только
OKR-хребет по `serves`).
"""
import pathlib

import pytest

from paf_index.derive import FIELD_PREDICATES
from poh_memory.edges import SEM_FIELDS, semantic_edges

NOTE = """---
node_id: {nid}
node_type: {ntype}
nexus: product
owner: A
sources: ["cortex:VISION.md"]
updated: 2026-07-22
title: {nid}
{extra}---

# {nid}
"""


def _write(root: pathlib.Path, nid: str, ntype: str, extra: str = "") -> None:
    (root / f"{nid}.md").write_text(NOTE.format(nid=nid, ntype=ntype, extra=extra),
                                    encoding="utf-8")


def test_value_axis_predicates_are_read_by_l2():
    """Словарь L2 покрывает ценностную ось L1 — один вокабуляр, не два."""
    for field, etype in FIELD_PREDICATES.items():
        assert SEM_FIELDS.get(field) == etype


def test_semantic_edges_emits_value_axis_edges(tmp_path):
    _write(tmp_path, "f-bft-writer", "feature",
           "realizes: [vp-requirements-speed]\nsatisfies: [kr-1-2]\n")
    _write(tmp_path, "vp-requirements-speed", "value-proposition",
           "addresses: [need-bft-hours]\n")
    _write(tmp_path, "need-bft-hours", "need")

    edges = set(semantic_edges(tmp_path))

    assert ("f-bft-writer", "vp-requirements-speed", "REALIZES") in edges
    assert ("f-bft-writer", "kr-1-2", "SATISFIES") in edges
    assert ("vp-requirements-speed", "need-bft-hours", "ADDRESSES") in edges


def test_ingest_relation_whitelist_covers_value_axis():
    """Второй фильтр: ingest._REL. Уже SEM_FIELDS — рёбра ценностной оси
    доходят до semantic_edges, но молча отбрасываются перед материализацией."""
    pytest.importorskip("falkordb")
    from poh_memory.ingest import _REL

    assert set(SEM_FIELDS.values()) <= _REL


def test_retrieval_graph_relations_cover_value_axis():
    """Третий фильтр: query._SEM_REL. Питает PPR, детект сообществ и метрику
    isolated_nodes — отсекая ценностную ось, все три считают по хребту OKR."""
    pytest.importorskip("falkordb")
    pytest.importorskip("networkx")
    from poh_memory.query import _SEM_REL

    assert set(SEM_FIELDS.values()) <= _SEM_REL
    # правило 2: claim-слой и хабы в retrieval-граф не входят
    assert {"ASSERTS", "ABOUT", "SUPERSEDED_BY", "OWNS"}.isdisjoint(_SEM_REL)


def test_hub_fields_stay_excluded(tmp_path):
    """owns_node / involves — мега-хаб, в L2 не попадают (docstring edges.py)."""
    _write(tmp_path, "f-a", "feature",
           "owns_node: team-aleks-ishmanov\ninvolves: [team-aleks-ishmanov]\n")

    edges = semantic_edges(tmp_path)

    assert edges == []
    assert "owns_node" not in SEM_FIELDS
    assert "involves" not in SEM_FIELDS
