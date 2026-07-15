import datetime
import pathlib
import textwrap

from sa_documentation.validate_ground import lint_nodes, validate_ground

ROOT = pathlib.Path(__file__).parent
TODAY = datetime.date(2026, 7, 3)


def test_ok():
    errs = validate_ground(ROOT / "fixtures/ground_ok")
    assert errs == [], f"unexpected errors: {errs}"


def test_bad():
    errs = validate_ground(ROOT / "fixtures/ground_bad")
    assert errs and any("product_engineer" in e or "slug" in e.lower() for e in errs)


# --- node linter --------------------------------------------------------------

def _node(**over):
    fm = {
        "nexus": "problem",
        "node_id": "n-1",
        "node_type": "step-overview",
        "kind": "empirical",
        "owner": "PO",
        "confidence": 0.4,
        "sources": '["onboarding:interview"]',
        "updated": "2026-07-01",
        "ttl_days": 90,
        "ripeness": "fresh",
    }
    fm.update(over)
    lines = "\n".join(f"{k}: {v}" for k, v in fm.items() if v is not None)
    return f"---\n{lines}\n---\n\n# body\n"


def _vault(tmp_path, files):
    (tmp_path / "NEXUS").mkdir()
    (tmp_path / "NEXUS/_registry.yaml").write_text(
        "nexus_types:\n  - {slug: problem, source: custom, onboarded: partial}\n"
    )
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text))
    return tmp_path


def test_node_ok(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node()})
    assert lint_nodes(tmp_path, today=TODAY) == []


def test_missing_required_key(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(confidence=None)})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("confidence" in i and i.startswith("ERROR") for i in issues)


def test_empty_sources_is_workslop_error(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(sources="[]")})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("workslop" in i and i.startswith("ERROR") for i in issues)


def test_empty_sources_index_is_warn(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/_index.md": _node(node_id="idx", sources="[]")})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("MOC-заглушка" in i and i.startswith("WARN") for i in issues)
    assert not any(i.startswith("ERROR") for i in issues)


def test_nexus_not_in_registry(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(nexus="ghost")})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("нет в _registry" in i for i in issues)


def test_bad_confidence_range(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(confidence=1.5)})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("confidence" in i and i.startswith("ERROR") for i in issues)


def test_dangling_edge(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(reports_to="team-ghost")})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("висячее ребро" in i for i in issues)


def test_valid_edge_resolves(tmp_path):
    _vault(tmp_path, {
        "NEXUS/problem/a.md": _node(node_id="a", reports_to="b"),
        "NEXUS/problem/b.md": _node(node_id="b"),
    })
    issues = lint_nodes(tmp_path, today=TODAY)
    assert not any("висячее ребро" in i for i in issues)


def test_ripeness_drift_and_wilting(tmp_path):
    # updated давно + короткий ttl → фактически wilting, но заявлено fresh.
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(updated="2026-01-01", ttl_days=30)})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("ripeness=" in i and "wilting" in i for i in issues)
    assert any("узел wilting" in i for i in issues)


def test_duplicate_node_id(tmp_path):
    _vault(tmp_path, {
        "NEXUS/problem/a.md": _node(node_id="dup"),
        "NEXUS/problem/b.md": _node(node_id="dup"),
    })
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("дубликат node_id" in i for i in issues)


# --- FNR-4: value-axis node types + edge fields -------------------------------

def test_value_axis_node_type_valid(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(node_type="service")})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert not any(i.startswith("ERROR") and "node_type" in i for i in issues)


def test_value_axis_dangling_edge_caught(tmp_path):
    _vault(tmp_path, {"NEXUS/problem/a.md": _node(based_on="[svc-ghost]")})
    issues = lint_nodes(tmp_path, today=TODAY)
    assert any("висячее ребро" in i and "svc-ghost" in i for i in issues)
