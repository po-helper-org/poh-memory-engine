import logging
from types import SimpleNamespace
from poh_memory.claims import parse_claims, claim_id


def _node(node_id, claims):
    return SimpleNamespace(node_id=node_id, frontmatter={"claims": claims} if claims is not None else {})


def test_parse_valid_claim_full():
    node = _node("pulse-2026-07-06-x", [{
        "subject": "Фонд МДТЗК Без Агентов", "aspect": "вывод в B2B", "value": "не должен",
        "polarity": "negative", "speaker": "Петров", "grounded_node": "ownership-live-acme-gateways",
        "confidence": 0.8,
    }])
    [c] = parse_claims(node)
    assert c["subject"] == "Фонд МДТЗК Без Агентов"
    assert c["aspect"] == "вывод в B2B"
    assert c["value"] == "не должен"
    assert c["polarity"] == "negative"
    assert c["speaker"] == "Петров"
    assert c["grounded_node"] == "ownership-live-acme-gateways"
    assert c["confidence"] == 0.8
    assert c["episode"] == "pulse-2026-07-06-x"
    assert c["id"] == claim_id("Фонд МДТЗК Без Агентов", "вывод в B2B", "не должен", "pulse-2026-07-06-x")


def test_defaults_and_derived_id_ignores_frontmatter_id():
    node = _node("pulse-ep", [{"id": "AGENT-PROVIDED-IGNORED", "subject": "s", "aspect": "a", "value": "v"}])
    [c] = parse_claims(node)
    assert c["polarity"] == "neutral"
    assert c["speaker"] is None
    assert c["grounded_node"] is None
    assert c["confidence"] is None
    assert c["id"] == claim_id("s", "a", "v", "pulse-ep")   # НЕ "AGENT-PROVIDED-IGNORED"


def test_missing_required_field_dropped():
    node = _node("pulse-ep", [
        {"subject": "s", "aspect": "a"},                 # нет value -> отброшен
        {"subject": "s2", "aspect": "a2", "value": "v2"},
    ])
    claims = parse_claims(node)
    assert len(claims) == 1
    assert claims[0]["subject"] == "s2"


def test_no_claims_field():
    assert parse_claims(_node("pulse-ep", None)) == []


def test_id_deterministic_same_content():
    a = claim_id("s", "a", "v", "ep")
    b = claim_id("s", "a", "v", "ep")
    assert a == b and a.startswith("claim-ep-")


def test_parse_reads_supersession_fields():
    node = _node("pulse-ep", [{
        "subject": "s", "aspect": "a", "value": "v",
        "superseded_by": "claim-pulse-new-abc12345", "invalid_at": "2026-07-09",
    }])
    [c] = parse_claims(node)
    assert c["superseded_by"] == "claim-pulse-new-abc12345"
    assert c["invalid_at"] == "2026-07-09"
    assert c["expired_at"] is None


def test_parse_supersession_defaults_null():
    node = _node("pulse-ep", [{"subject": "s", "aspect": "a", "value": "v"}])
    [c] = parse_claims(node)
    assert c["invalid_at"] is None
    assert c["expired_at"] is None
    assert c["superseded_by"] is None


def test_parse_both_invalid_and_expired_reset_to_null(caplog):
    node = _node("pulse-ep", [{
        "subject": "s", "aspect": "a", "value": "v",
        "invalid_at": "2026-07-09", "expired_at": "2026-07-11",
    }])
    with caplog.at_level(logging.WARNING):
        [c] = parse_claims(node)
    assert c["invalid_at"] is None      # обе сброшены — не гадаем
    assert c["expired_at"] is None
    assert any("both invalid_at and expired_at" in r.message for r in caplog.records)
