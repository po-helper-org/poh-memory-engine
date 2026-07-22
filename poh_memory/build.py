# poh_memory/build.py
"""Пересборка графа: guard соединения + ingest + сводка. Обёртка над ingest для
CLI и impact/insight. FalkorDB недоступен -> {ok: False}, не исключение."""
from __future__ import annotations
import pathlib
from falkordb import FalkorDB
from poh_memory.config import FALKOR_HOST, FALKOR_PORT
from poh_memory.ingest import ingest


def build_graph(nexus_root: pathlib.Path, ingest_at: str, graph_name: str = "poh",
                host: str = FALKOR_HOST, port: int = FALKOR_PORT) -> dict:
    try:
        g = FalkorDB(host=host, port=port).select_graph(graph_name)
        g.query("RETURN 1")   # форсируем соединение
    except Exception as e:    # noqa: BLE001 — guard: любая ошибка соединения -> отчёт, не краш
        return {"ok": False, "error": f"FalkorDB недоступен на {host}:{port}: {e}"}
    # чистая пересборка: frontmatter = источник правды, граф производный. Без этого
    # смена/удаление контента копит мусорные узлы (id claim = контент-хэш меняется);
    # claim-слой не реконсилируется (CLAIM-STALE) -> дропаем всё и материализуем заново.
    g.query("MATCH (n) DETACH DELETE n")
    edges = ingest(nexus_root, graph_name, host=host, port=port, ingest_at=ingest_at)
    ent = g.query("MATCH (n:Entity) RETURN count(n)").result_set[0][0]
    clm = g.query("MATCH (c:Claim) RETURN count(c)").result_set[0][0]
    ncomm = g.query("MATCH (n:Entity) WHERE n.community_id IS NOT NULL "
                    "RETURN count(DISTINCT n.community_id)").result_set[0][0]
    return {"ok": True, "edges_ingested": edges, "entities": ent, "claims": clm, "communities": ncomm}
