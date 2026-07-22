"""Plan-shift detection over commitment claims (pure: no graph backend).

A commitment claim carries a comparable `value_norm` (a date, a number). When
the same (subject, aspect) is asserted again later with a different value, the
plan moved — that delta, with who said it and when, is the signal a PO needs
before the change surfaces upstream.

Only `aspect_kind == "commitment"` claims with a `value_norm` participate;
states and opinions are ignored by design.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Shift:
    subject: str
    aspect: str
    from_value: str
    to_value: str
    from_at: str | None
    to_at: str | None
    from_speaker: str | None
    to_speaker: str | None
    from_role: str | None
    to_role: str | None


def _eligible(c: dict) -> bool:
    return c.get("aspect_kind") == "commitment" and c.get("value_norm") is not None


def detect_shifts(claims: list[dict]) -> list[Shift]:
    """Consecutive value changes per (subject, aspect), ordered by valid_at."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for c in claims:
        if not _eligible(c):
            continue
        groups.setdefault((c.get("subject"), c.get("aspect")), []).append(c)

    out: list[Shift] = []
    for (subject, aspect), items in groups.items():
        # `valid_at` may be absent; keep those last but stable.
        items.sort(key=lambda c: (c.get("valid_at") is None, c.get("valid_at") or ""))
        for prev, cur in zip(items, items[1:]):
            if str(prev["value_norm"]) == str(cur["value_norm"]):
                continue
            out.append(Shift(
                subject=subject, aspect=aspect,
                from_value=str(prev["value_norm"]), to_value=str(cur["value_norm"]),
                from_at=prev.get("valid_at"), to_at=cur.get("valid_at"),
                from_speaker=prev.get("speaker"), to_speaker=cur.get("speaker"),
                from_role=prev.get("speaker_role"), to_role=cur.get("speaker_role"),
            ))
    out.sort(key=lambda s: (s.to_at or "", s.subject, s.aspect))
    return out
