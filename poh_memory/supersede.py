"""Механическая supersession: реконсиляция edge-set на re-ingest (Temporal #2a).

Ребро, которое было в графе, но frontmatter больше НЕ утверждает (нет в asserted),
получает invalid_at=ingest_at. Граница = дата билда — принятая неточность (событийную
дату выставит агент #2b). expired_at НЕ трогаем. Реактивацию утверждённых рёбер делает
сам ingest (MERGE пишет invalid_at=null). Спека:
docs/superpowers/specs/2026-07-10-poh-temporal-supersession-mechanical-design.md
"""
from __future__ import annotations
from poh_memory.edges import SEM_FIELDS

_REL = set(SEM_FIELDS.values())  # {"SERVES", "DELIVERS", "MENTIONS"} — белый список для интерполяции


def reconcile_edges(graph, asserted: set[tuple[str, str, str]], ingest_at: str) -> int:
    """Стампит invalid_at=ingest_at на DB-рёбра вне asserted. Возвращает число инвалидированных."""
    rows = graph.query(
        "MATCH (a)-[r]->(b) RETURN a.name, type(r), b.name, r.invalid_at"
    ).result_set
    n = 0
    for src, etype, dst, invalid_at in rows:
        if not (src and dst):
            continue
        if etype not in _REL:                      # безопасность интерполяции + скоуп семантич. рёбер
            continue
        if (src, etype, dst) in asserted:           # ещё утверждается -> активно
            continue
        if invalid_at is not None:                  # уже инвалидировано -> не перезаписывать
            continue
        graph.query(
            f"MATCH (a:Entity {{name:$s}})-[r:{etype}]->(b:Entity {{name:$d}}) "
            f"SET r.invalid_at=$iv",
            {"s": src, "d": dst, "iv": ingest_at},
        )
        n += 1
    return n
