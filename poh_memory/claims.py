"""Парс типизированных claim'ов из frontmatter эпизодов (Temporal #2b-I).

Claim = реифицированный факт, извлечённый агентом /extract-claims и записанный в
`claims:` frontmatter pulse-заметки. Здесь — детерминированный парс/нормализация
(без FalkorDB, без LLM). id деривируется от контента (не позиция) для идемпотентного
MERGE в ingest. Спека: docs/superpowers/specs/2026-07-10-poh-temporal-claim-extraction-design.md
"""
from __future__ import annotations
import hashlib
import logging
import pathlib
from paf_index import frontmatter as fm

log = logging.getLogger(__name__)


def claim_id(subject: str, aspect: str, value: str, episode: str) -> str:
    h = hashlib.sha1(f"{subject}|{aspect}|{value}|{episode}".encode("utf-8")).hexdigest()[:8]
    return f"claim-{episode}-{h}"


# Aspect classes: a commitment is a promise with a comparable value (a date, a
# number) whose change over time is a plan shift; a state is an assertion about
# how things are; an opinion carries no commitment.
ASPECT_KINDS = {"commitment", "state", "opinion"}
VALUE_TYPES = {"date", "number", "text"}


def _enum(raw, allowed: set[str], default: str) -> str:
    """Controlled value with a safe fallback — unknown input never breaks ingest."""
    v = str(raw) if raw is not None else ""
    return v if v in allowed else default


def parse_claims(node) -> list[dict]:
    """node: paf_index.frontmatter.Node. Возвращает нормализованные claim-dict'ы."""
    raw = node.frontmatter.get("claims")
    if not raw:
        return []
    out = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        subject, aspect, value = c.get("subject"), c.get("aspect"), c.get("value")
        if not (subject and aspect and value):
            continue  # обязательные поля
        subject, aspect, value = str(subject), str(aspect), str(value)
        invalid_at = c.get("invalid_at")
        expired_at = c.get("expired_at")
        if invalid_at and expired_at:
            log.warning("claim (%s|%s|%s) episode %s: both invalid_at and expired_at set — resetting both to null",
                        subject, aspect, value, node.node_id)
            invalid_at = expired_at = None
        out.append({
            "id": claim_id(subject, aspect, value, node.node_id),   # деривируется, frontmatter-id игнорируется
            "subject": subject,
            "aspect": aspect,
            "value": value,
            "polarity": str(c.get("polarity") or "neutral"),
            "speaker": c.get("speaker"),
            # Commitment semantics: who may assert this, and is the value
            # comparable over time (basis for detecting plan shifts).
            "speaker_role": c.get("speaker_role"),
            "aspect_kind": _enum(c.get("aspect_kind"), ASPECT_KINDS, "state"),
            "value_type": _enum(c.get("value_type"), VALUE_TYPES, "text"),
            "value_norm": c.get("value_norm"),
            "grounded_node": c.get("grounded_node"),
            "confidence": c.get("confidence"),
            "episode": node.node_id,
            "invalid_at": invalid_at,                       # #2b-II: supersession-аннотации
            "expired_at": expired_at,
            "superseded_by": c.get("superseded_by"),
        })
    return out


def episode_claims(nexus_root: pathlib.Path) -> list[dict]:
    """Все claim'ы всех эпизодов (nexus_root/pulse). Плоский список."""
    pulse = nexus_root / "pulse"
    if not pulse.exists():
        return []
    out: list[dict] = []
    for node in fm.load_all_nexus_notes(pulse):
        out.extend(parse_claims(node))
    return out
