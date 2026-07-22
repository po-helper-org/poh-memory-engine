"""Claim fields that carry commitment semantics (author role, aspect class,
typed value) — the basis for detecting plan shifts and weighing authority."""
import pathlib

from paf_index.frontmatter import Node
from poh_memory.claims import parse_claims


def _node(claims):
    return Node(
        node_id="pulse-ep-1", node_type="episode", nexus="pulse", owner=None,
        full_name=None, sources=[], manages=[], reports_to=None,
        collaborates_with=[], updated=None, ttl_days=None, confidence=None,
        ripeness=None, path=pathlib.Path("pulse-ep-1.md"),
        frontmatter={"node_id": "pulse-ep-1", "claims": claims},
    )


def _base(**over):
    c = {"subject": "Эпик А", "aspect": "срок поставки", "value": "конец июля"}
    c.update(over)
    return c


def test_commitment_fields_parsed():
    n = _node([_base(aspect_kind="commitment", value_type="date",
                     value_norm="2026-07-31", speaker="Петров Пётр",
                     speaker_role="техлид")])
    c = parse_claims(n)[0]
    assert c["aspect_kind"] == "commitment"
    assert c["value_type"] == "date"
    assert c["value_norm"] == "2026-07-31"
    assert c["speaker_role"] == "техлид"


def test_defaults_are_backward_compatible():
    # Existing claims carry none of the new fields and must keep working.
    c = parse_claims(_node([_base()]))[0]
    assert c["aspect_kind"] == "state"
    assert c["value_type"] == "text"
    assert c["value_norm"] is None
    assert c["speaker_role"] is None


def test_unknown_aspect_kind_falls_back_to_state():
    c = parse_claims(_node([_base(aspect_kind="wishful")]))[0]
    assert c["aspect_kind"] == "state"


def test_id_unaffected_by_new_fields():
    # id derives from subject|aspect|value|episode — adding commitment metadata
    # must not remint the claim (idempotent MERGE).
    plain = parse_claims(_node([_base()]))[0]
    rich = parse_claims(_node([_base(aspect_kind="commitment", value_norm="2026-07-31")]))[0]
    assert plain["id"] == rich["id"]
