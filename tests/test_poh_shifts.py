"""Plan-shift detection: a commitment whose value changed over time."""
from poh_memory.shifts import detect_shifts


def _claim(**over):
    c = {"subject": "Эпик А", "aspect": "срок поставки", "value": "…",
         "aspect_kind": "commitment", "value_type": "date",
         "value_norm": "2026-07-31", "valid_at": "2026-07-01",
         "speaker": "Петров Пётр", "speaker_role": "техлид"}
    c.update(over)
    return c


def test_changed_commitment_is_a_shift():
    claims = [_claim(), _claim(value_norm="2026-08-14", valid_at="2026-07-15")]
    s = detect_shifts(claims)[0]
    assert (s.from_value, s.to_value) == ("2026-07-31", "2026-08-14")
    assert (s.from_at, s.to_at) == ("2026-07-01", "2026-07-15")
    assert s.subject == "Эпик А"
    assert s.to_speaker == "Петров Пётр"


def test_repeated_same_value_is_not_a_shift():
    claims = [_claim(), _claim(valid_at="2026-07-15")]
    assert detect_shifts(claims) == []


def test_non_commitment_is_ignored():
    claims = [_claim(aspect_kind="state"),
              _claim(aspect_kind="state", value_norm="2026-08-14", valid_at="2026-07-15")]
    assert detect_shifts(claims) == []


def test_claim_without_norm_value_is_ignored():
    claims = [_claim(value_norm=None),
              _claim(value_norm=None, valid_at="2026-07-15")]
    assert detect_shifts(claims) == []


def test_different_subjects_do_not_mix():
    claims = [_claim(), _claim(subject="Эпик Б", value_norm="2026-09-01", valid_at="2026-07-15")]
    assert detect_shifts(claims) == []


def test_shifts_ordered_by_time_regardless_of_input_order():
    claims = [_claim(value_norm="2026-08-14", valid_at="2026-07-15"), _claim()]
    s = detect_shifts(claims)[0]
    assert s.from_at == "2026-07-01"
