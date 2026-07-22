# tests/test_poh_temporal.py
from poh_memory.temporal import active_at


def test_valid_at_null_always_active():
    assert active_at({"valid_at": None, "invalid_at": None, "expired_at": None}, "2026-01-01") is True
    assert active_at({"valid_at": None, "invalid_at": None, "expired_at": None}, None) is True


def test_valid_at_bounds():
    props = {"valid_at": "2026-07-09", "invalid_at": None, "expired_at": None}
    assert active_at(props, "2026-07-10") is True   # T после valid_at
    assert active_at(props, "2026-07-09") is True   # T == valid_at (<=)
    assert active_at(props, "2026-07-08") is False  # T до valid_at


def test_invalid_at_bounds():
    props = {"valid_at": "2026-01-01", "invalid_at": "2026-07-09", "expired_at": None}
    assert active_at(props, "2026-07-08") is True   # до инвалидации
    assert active_at(props, "2026-07-09") is False  # в момент инвалидации (invalid_at > t ложно)
    assert active_at(props, "2026-07-10") is False  # после


def test_expired_at_set_never_active():
    props = {"valid_at": None, "invalid_at": None, "expired_at": "2026-07-09"}
    assert active_at(props, "2026-07-10") is False
    assert active_at(props, None) is False


def test_current_ignores_valid_at_but_respects_invalid():
    # t=None = «текущее»: valid_at не фильтрует, но invalidated исключается
    assert active_at({"valid_at": "2099-01-01", "invalid_at": None, "expired_at": None}, None) is True
    assert active_at({"valid_at": None, "invalid_at": "2026-07-09", "expired_at": None}, None) is False


def test_claim_kind_changed_invalid_at_windows():
    # kind=changed -> invalid_at set (= valid_at вытесняющего). as-of ДО границы видит, current — нет.
    props = {"valid_at": "2026-07-01", "invalid_at": "2026-07-09", "expired_at": None}
    assert active_at(props, "2026-07-05") is True     # до invalid_at
    assert active_at(props, "2026-07-10") is False    # после
    assert active_at(props, None) is False            # current: invalidated


def test_claim_kind_wrong_expired_at_hides_from_all_asof():
    # kind=wrong -> expired_at set. active_at False при ЛЮБОМ t (в т.ч. прошлом).
    props = {"valid_at": "2026-07-01", "invalid_at": None, "expired_at": "2026-07-11"}
    assert active_at(props, "2026-06-01") is False    # даже as-of до valid_at
    assert active_at(props, "2026-07-05") is False
    assert active_at(props, None) is False
