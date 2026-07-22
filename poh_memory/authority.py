"""Who may authoritatively assert what (pure: yaml read, no graph backend).

Not every statement carries equal weight: a delivery date named by a tech lead
is a commitment, the same date guessed by someone outside that responsibility
is not. The policy maps a role to the aspect classes it may assert.

Three-valued on purpose: True (may assert), False (role is mapped but not for
this class), None (role unknown or no policy — missing information, never
silently treated as "not authoritative").

The policy itself is client data — the engine only reads it.
"""
from __future__ import annotations
import pathlib
import yaml


def load_policy(path) -> dict[str, set[str]]:
    """{role_lowercase: {aspect_class, ...}}. Missing/empty file -> {}."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: dict[str, set[str]] = {}
    for entry in data.get("authority", []):
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        if not role:
            continue
        out[str(role).strip().lower()] = {
            str(a) for a in (entry.get("may_assert") or [])
        }
    return out


def is_authoritative(role: str | None, aspect_kind: str,
                     policy: dict[str, set[str]]) -> bool | None:
    """True / False / None (undecided — unknown role or no policy)."""
    if not role or not policy:
        return None
    allowed = policy.get(str(role).strip().lower())
    if allowed is None:
        return None
    return aspect_kind in allowed
