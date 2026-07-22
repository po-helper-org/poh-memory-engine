from poh_memory.contradictions import candidate_pairs


def _c(cid, aspect="a", value="v", polarity="neutral", grounded="node-x", **extra):
    d = {"id": cid, "subject": "s", "aspect": aspect, "value": value,
         "polarity": polarity, "grounded_node": grounded,
         "invalid_at": None, "expired_at": None, "superseded_by": None, "episode": "pulse-ep"}
    d.update(extra)
    return d


def test_same_key_diff_polarity_is_pair():
    pairs = candidate_pairs([_c("1", polarity="positive"), _c("2", polarity="negative")])
    assert len(pairs) == 1
    assert {pairs[0][0]["id"], pairs[0][1]["id"]} == {"1", "2"}


def test_same_key_diff_value_is_pair():
    pairs = candidate_pairs([_c("1", value="A"), _c("2", value="B")])
    assert len(pairs) == 1


def test_same_key_identical_is_not_pair():
    # same polarity AND same value -> not a contradiction candidate
    assert candidate_pairs([_c("1"), _c("2")]) == []


def test_different_aspect_is_not_pair():
    assert candidate_pairs([_c("1", aspect="a1", polarity="positive"),
                            _c("2", aspect="a2", polarity="negative")]) == []


def test_different_grounded_node_is_not_pair():
    assert candidate_pairs([_c("1", grounded="node-x", polarity="positive"),
                            _c("2", grounded="node-y", polarity="negative")]) == []


def test_ungrounded_claim_excluded():
    assert candidate_pairs([_c("1", grounded=None, polarity="positive"),
                            _c("2", grounded=None, polarity="negative")]) == []


def test_singleton_group_no_pair():
    assert candidate_pairs([_c("1", polarity="positive")]) == []


def test_already_resolved_claim_excluded():
    # a claim with any of superseded_by/invalid_at/expired_at set is not re-judged
    assert candidate_pairs([_c("1", polarity="positive", superseded_by="claim-x"),
                            _c("2", polarity="negative")]) == []
    assert candidate_pairs([_c("1", polarity="positive", invalid_at="2026-07-09"),
                            _c("2", polarity="negative")]) == []
    assert candidate_pairs([_c("1", polarity="positive", expired_at="2026-07-11"),
                            _c("2", polarity="negative")]) == []


def test_three_members_yields_all_conflicting_pairs():
    # multi-way not resolved here, but candidate generation surfaces all conflicting pairs
    pairs = candidate_pairs([_c("1", value="A"), _c("2", value="B"), _c("3", value="C")])
    assert len(pairs) == 3


def test_different_subject_same_node_aspect_is_not_pair():
    # same grounded_node + aspect, DIFFERENT subject -> different entities -> NOT a pair
    a = _c("1", polarity="positive")
    b = _c("2", polarity="negative")
    a["subject"] = "Фонд МДТЗК эталон"
    b["subject"] = "Фонд МДТЗК Без Агентов"
    assert candidate_pairs([a, b]) == []


def test_same_subject_node_aspect_diff_polarity_is_pair():
    a = _c("1", polarity="positive")
    b = _c("2", polarity="negative")
    a["subject"] = b["subject"] = "Фонд МДТЗК Без Агентов"
    pairs = candidate_pairs([a, b])
    assert len(pairs) == 1
