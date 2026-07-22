"""Чистый битемпоральный предикат as-of. Без FalkorDB — тестируется изолированно.

Метки ребра (все ISO-строки или None):
  valid_at   — событийное «факт стал истинным» (null = вне времени / всегда).
  invalid_at — событийное «факт перестал быть истинным» (null в #1).
  expired_at — транзакционное «запись вытеснена» (null в #1).
ISO YYYY-MM-DD сравнивается лексикографически.
"""
from __future__ import annotations


def active_at(props: dict, t: str | None) -> bool:
    """Активно ли ребро на момент t. t=None => «текущее» (не-invalidated, не-expired)."""
    if props.get("expired_at") is not None:
        return False
    invalid_at = props.get("invalid_at")
    if t is None:
        return invalid_at is None
    valid_at = props.get("valid_at")
    if valid_at is not None and valid_at > t:
        return False
    if invalid_at is not None and invalid_at <= t:
        return False
    return True
