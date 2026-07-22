"""Фабрика Graphiti на FalkorDB БЕЗ LLM-клиента.

API подтверждён (graphiti-core 0.29):
  Graphiti(graph_driver=FalkorDriver(host,port,database), embedder=..., llm_client=None)
  FalkorDriver(host='localhost', port=6379, ..., database='default_db')
Порт FalkorDB у нас = 6380 (6379 занят нативным redis).
"""
from __future__ import annotations
from graphiti_core import Graphiti
from graphiti_core.driver.falkordb_driver import FalkorDriver
from poh_memory.stubs import NoOpLLMClient, NoOpCrossEncoder

from poh_memory.config import FALKOR_HOST, FALKOR_PORT  # ре-экспорт (обратная совместимость)


def make_graphiti(graph_name: str = "poh", host: str = FALKOR_HOST,
                  port: int = FALKOR_PORT, embedder=None) -> Graphiti:
    """Graphiti на FalkorDB без РАБОЧЕГО LLM-клиента: llm_client=None заставляет
    Graphiti создать дефолтный OpenAI (нужен ключ) — потому подставляем no-op стабы.
    Пишем через add_triplet, читаем прямым обходом; LLM-extract не используется."""
    driver = FalkorDriver(host=host, port=port, database=graph_name)
    return Graphiti(graph_driver=driver, embedder=embedder,
                    llm_client=NoOpLLMClient(), cross_encoder=NoOpCrossEncoder())
