"""Env-конфиг FalkorDB host/port. Лёгкий (только stdlib): build-путь импортит
host/port ОТСЮДА, минуя client.py, который на import тянет graphiti_core/openai.
Дефолты = локальная разработка; docker-compose переопределяет через env."""
from __future__ import annotations
import os

FALKOR_HOST = os.environ.get("FALKOR_HOST", "localhost")
FALKOR_PORT = int(os.environ.get("FALKOR_PORT", "6380"))
