import pathlib

from paf_index.frontmatter import load_note
from paf_index.derive import Edge
from paf_index.write import apply_edges

TODAY = "2026-07-14"


def _write(tmp, node_id, **fm):
    lines = [f"node_id: {node_id}", "node_type: initiative", "nexus: product"]
    for k, v in fm.items():
        if isinstance(v, list):
            v = "[" + ", ".join(v) + "]"
        lines.append(f"{k}: {v}")
    p = tmp / f"{node_id}.md"
    p.write_text("---\n" + "\n".join(lines) + "\n---\n\n# body\n", encoding="utf-8")
    return load_note(p)


def test_based_on_written_and_merged(tmp_path):
    src = _write(tmp_path, "init-x", based_on=["manual-keep"])
    dst = _write(tmp_path, "svc-y", node_type="service")
    nodes_by_id = {"init-x": src, "svc-y": dst}
    edges = [Edge("BASED_ON", "init-x", "svc-y", "based_on frontmatter",
                  "high", TODAY, TODAY)]

    apply_edges(edges, nodes_by_id)

    reloaded = load_note(src.path)
    assert set(reloaded.frontmatter["based_on"]) == {"manual-keep", "svc-y"}


def test_all_value_predicates_in_field_for(tmp_path):
    a = _write(tmp_path, "a")
    b = _write(tmp_path, "b", node_type="need")
    nodes_by_id = {"a": a, "b": b}
    for pred, field in [("REALIZES", "realizes"), ("ADDRESSES", "addresses"),
                        ("SATISFIES", "satisfies"), ("HAS_NEED", "has_need"),
                        ("DEPENDS_ON", "depends_on")]:
        apply_edges([Edge(pred, "a", "b", "x", "high", TODAY, TODAY)], nodes_by_id)
        a = load_note(a.path)
        nodes_by_id["a"] = a
        assert "b" in a.frontmatter[field], f"{pred} not written to {field}"
