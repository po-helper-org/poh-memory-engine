"""No-op LLM/cross-encoder клиенты — Graphiti требует их на init, но на нашем
пути (add_triplet + прямой обход) они не вызываются. Если вызовутся — явная ошибка,
значит путь ушёл в LLM-экстракцию (которую мы делаем агентом Claude Code, не тут).
"""
from __future__ import annotations
from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.cross_encoder.client import CrossEncoderClient


class NoOpLLMClient(LLMClient):
    def __init__(self):
        super().__init__(config=LLMConfig(api_key="noop"), cache=False)

    async def _generate_response(self, messages, response_model=None,
                                 max_tokens=16384, model_size=None):
        raise NotImplementedError(
            "NoOpLLMClient вызван — путь ушёл в LLM-экстракцию Graphiti; "
            "в po-helper экстракция делается агентом Claude Code, не тут.")


class NoOpCrossEncoder(CrossEncoderClient):
    async def rank(self, query, passages):
        return [(p, 1.0) for p in passages]
