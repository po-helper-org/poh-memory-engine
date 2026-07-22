"""Генерация кандидат-пар противоречащих claim'ов (Temporal #2b-II).

Чистая детерминированная группировка — без FalkorDB, без LLM. Из плоского списка
claim-dict (как из claims.episode_claims) отбирает заземлённые, ещё не разрешённые
claim'ы, группирует по (grounded_node, aspect) и формирует пары с расходящимся
polarity ИЛИ value. Агент /reconcile-claims судит каждую пару.
Спека: docs/superpowers/specs/2026-07-11-poh-temporal-claim-contradiction-design.md
"""
from __future__ import annotations
from itertools import combinations


def _resolved(c: dict) -> bool:
    """Claim уже вытеснен/размечен -> не пере-судим (идемпотентность по подтверждённым)."""
    return bool(c.get("superseded_by") or c.get("invalid_at") or c.get("expired_at"))


def candidate_pairs(claims: list[dict]) -> list[tuple[dict, dict]]:
    """Группировка заземлённых, неразрешённых claim'ов в (grounded_node, subject, aspect),
    формирование пар с расходящимся polarity ИЛИ value.

    Требует ровно claim-dict (dict shape, produced by poh_memory.claims.parse_claims
    или episode_claims), со гарантией наличия aspect/polarity/value; ручной словарь
    без этих ключей вызовет KeyError. """
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for c in claims:
        gn = c.get("grounded_node")
        if not gn:
            continue                      # незаземлённые пропускаем
        if _resolved(c):
            # resolved — claim'ы с superseded_by/invalid_at/expired_at = уже размеченные,
            # не пере-судим (идемпотентность); resolved глобален по claim (одна aspect)
            continue
        groups.setdefault((gn, c["subject"], c["aspect"]), []).append(c)
    pairs: list[tuple[dict, dict]] = []
    for members in groups.values():
        if len(members) < 2:
            continue                      # одиночные — не пара
        for a, b in combinations(members, 2):
            if a["polarity"] != b["polarity"] or a["value"] != b["value"]:
                pairs.append((a, b))
    return pairs
