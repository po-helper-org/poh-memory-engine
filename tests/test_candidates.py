import pathlib
from paf_index import candidates as C, frontmatter as fm
from paf_index.gaps import Gap

def test_seed_and_roundtrip(tmp_path):
    p = tmp_path / "q.yaml"
    n = C.seed_gaps(p, [Gap("system-a", "no-serves", "A"), Gap("x-iso", "isolated", "X")])
    assert n == 2
    items = C.load_candidates(p)
    assert {c.src for c in items} == {"system-a", "x-iso"}
    assert all(c.status == "open" for c in items)

def test_seed_idempotent_and_preserves_progress(tmp_path):
    p = tmp_path / "q.yaml"
    C.seed_gaps(p, [Gap("system-a", "no-serves", "A")])
    items = C.load_candidates(p)
    items[0].dst = "kr-1-3"; items[0].status = "approved"
    C.save_candidates(p, items)
    added = C.seed_gaps(p, [Gap("system-a", "no-serves", "A")])
    assert added == 0
    again = C.load_candidates(p)
    assert again[0].status == "approved"
    assert again[0].dst == "kr-1-3"

def test_seed_marks_resolved_when_gap_gone(tmp_path):
    p = tmp_path / "q.yaml"
    C.seed_gaps(p, [Gap("system-a", "no-serves", "A")])
    C.seed_gaps(p, [])
    items = C.load_candidates(p)
    assert items[0].status == "resolved"

def _mk_note(tmp_path, node_id, node_type):
    p = tmp_path / f"{node_id}.md"
    p.write_text(
        f"---\nnexus: system\nnode_id: {node_id}\nnode_type: {node_type}\n"
        f"kind: empirical\nowner: X\nconfidence: 0.5\nsources: [s]\n"
        f"updated: '2026-07-09'\nttl_days: 90\nripeness: fresh\n---\n\n# {node_id}\n",
        encoding="utf-8")
    return fm.load_note(p)

def test_promote_only_approved_and_idempotent(tmp_path):
    src = _mk_note(tmp_path, "system-a", "system-component")
    kr = _mk_note(tmp_path, "kr-1-3", "key-result")
    nodes_by_id = {src.node_id: src, kr.node_id: kr}
    items = [C.Candidate("system-a", "no-serves", "A", dst="kr-1-3",
                         confidence=0.7, rationale="r", status="approved")]
    C.save_candidates(tmp_path / "q.yaml", items)
    changed, issues, skipped = C.promote(tmp_path / "q.yaml", nodes_by_id, "2026-07-09")
    assert changed == 1 and issues == [] and skipped == []
    assert "serves: kr-1-3" in src.path.read_text(encoding="utf-8")
    assert C.load_candidates(tmp_path / "q.yaml")[0].status == "promoted"
    changed2, _, _ = C.promote(tmp_path / "q.yaml", nodes_by_id, "2026-07-09")
    assert changed2 == 0

def test_promote_skips_bad_dst(tmp_path):
    src = _mk_note(tmp_path, "system-a", "system-component")
    nodes_by_id = {src.node_id: src}
    items = [C.Candidate("system-a", "no-serves", "A", dst=None, status="approved")]
    C.save_candidates(tmp_path / "q.yaml", items)
    changed, issues, skipped = C.promote(tmp_path / "q.yaml", nodes_by_id, "2026-07-09")
    assert changed == 0 and skipped == ["system-a"]
