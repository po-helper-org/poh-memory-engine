"""Whether a speaker's role may authoritatively assert a given aspect class."""
import textwrap

from poh_memory.authority import load_policy, is_authoritative

POLICY_YAML = textwrap.dedent("""
    authority:
      - role: техлид
        may_assert: [commitment]
      - role: product owner
        may_assert: [acceptance, scope]
""")


def _policy(tmp_path):
    p = tmp_path / "authority.yaml"
    p.write_text(POLICY_YAML, encoding="utf-8")
    return load_policy(p)


def test_role_listed_for_class_is_authoritative(tmp_path):
    assert is_authoritative("техлид", "commitment", _policy(tmp_path)) is True


def test_role_not_listed_for_class_is_not_authoritative(tmp_path):
    assert is_authoritative("product owner", "commitment", _policy(tmp_path)) is False


def test_unknown_role_is_undecided_not_false(tmp_path):
    # An unmapped role must not be silently treated as non-authoritative —
    # it is missing information, and the report must say so.
    assert is_authoritative("аналитик", "commitment", _policy(tmp_path)) is None


def test_missing_role_is_undecided(tmp_path):
    assert is_authoritative(None, "commitment", _policy(tmp_path)) is None


def test_absent_policy_file_leaves_everything_undecided(tmp_path):
    empty = load_policy(tmp_path / "nope.yaml")
    assert is_authoritative("техлид", "commitment", empty) is None


def test_role_match_is_case_insensitive(tmp_path):
    assert is_authoritative("ТехЛид", "commitment", _policy(tmp_path)) is True
