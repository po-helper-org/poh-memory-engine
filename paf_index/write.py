from __future__ import annotations
import re, sys, pathlib
import yaml
from paf_index.derive import DEFAULT_OWNER

_FM_BLOCK = re.compile(r"^(---\s*\n)(.*?)(\n---\s*\n?)(.*)$", re.DOTALL)
_FM_KEYS_ORDER = ["nexus", "node_id", "node_type", "paf_step", "sprint_phase",
                  "kind", "owner", "confidence", "sources", "updated",
                  "ttl_days", "ripeness", "title"]

def upsert_frontmatter_field(text: str, key: str, value) -> str:
    m = _FM_BLOCK.match(text)
    if not m:
        return text
    head, block, tail, body = m.groups()
    val = _scalar(value)
    lines = block.split("\n")
    key_re = re.compile(rf"^{re.escape(key)}\s*:")
    for i, ln in enumerate(lines):
        if key_re.match(ln):
            lines[i] = f"{key}: {val}"
            return head + "\n".join(lines) + tail + body
    lines.append(f"{key}: {val}")
    return head + "\n".join(lines) + tail + body

def _scalar(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(v) for v in value) + "]"
    return str(value)

def render_note(nn, footer: str) -> str:
    fm = nn.frontmatter
    ordered = {k: fm[k] for k in _FM_KEYS_ORDER if k in fm}
    for k, v in fm.items():
        ordered.setdefault(k, v)
    dumped = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{dumped}\n---\n\n# {nn.title}\n\n> {footer}\n"

def render_okr_note(nn) -> str:
    return render_note(nn, "Узел хребта OKR, выведен из KR→epic map.")

def render_episode_note(nn) -> str:
    return render_note(nn, "Эпизод (PULSE-саммари), связи выведены детерминированно.")

def render_task_ref_note(nn) -> str:
    return render_note(nn, "Ссылка на задачу JIRA (medium-trust), тело в JIRA.")

def write_nodes(new_nodes, target_dir: pathlib.Path, render_fn) -> list[pathlib.Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for nn in new_nodes:
        path = target_dir / f"{nn.node_id}.md"
        if path.exists():
            continue
        path.write_text(render_fn(nn), encoding="utf-8")
        written.append(path)
    return written

def write_okr_nodes(new_nodes, okr_dir: pathlib.Path) -> list[pathlib.Path]:
    return write_nodes(new_nodes, okr_dir, render_okr_note)

def apply_edges(edges, nodes_by_id: dict) -> int:
    field_for = {"OWNS": ("owns_node", False), "SERVES": ("serves", False),
                 "DELIVERS": ("delivered_by", True),
                 "MENTIONS": ("mentions", True), "involves": ("involves", True),
                 # Value-axis predicates (FNR-4) — all list-valued, so they go
                 # through the merge branch below (antiklobber of manual edges).
                 "REALIZES": ("realizes", True), "BASED_ON": ("based_on", True),
                 "DEPENDS_ON": ("depends_on", True), "ADDRESSES": ("addresses", True),
                 "SATISFIES": ("satisfies", True), "HAS_NEED": ("has_need", True)}
    # DELIVERS is written on the KR (dst); OWNS/SERVES on the src node
    changes = 0
    grouped: dict[str, dict] = {}
    for e in edges:
        field, is_list = field_for[e.type]
        target_node = e.dst if e.type == "DELIVERS" else e.src
        grouped.setdefault(target_node, {"single": {}, "list": {}})
        if is_list:
            grouped[target_node]["list"].setdefault(field, []).append(e.src if e.type == "DELIVERS" else e.dst)
        else:
            grouped[target_node]["single"][field] = e.dst
    for nid, fields in grouped.items():
        node = nodes_by_id.get(nid)
        if node is None:
            continue
        text = node.path.read_text(encoding="utf-8")
        new_text = text
        for k, v in fields["single"].items():
            new_text = upsert_frontmatter_field(new_text, k, v)
        for k, vs in fields["list"].items():
            # Merge with any pre-existing values (manual/ADR-added edges) rather
            # than overwriting — build owns derived edges but must not clobber
            # links it did not derive.
            existing = node.frontmatter.get(k) or []
            if isinstance(existing, str):
                existing = [existing]
            new_text = upsert_frontmatter_field(new_text, k, sorted(set(existing) | set(vs)))
        if new_text != text:
            node.path.write_text(new_text, encoding="utf-8")
            changes += 1
    return changes

def register_nexus(registry_path: pathlib.Path, slug: str, name: str, purpose: str) -> bool:
    text = registry_path.read_text(encoding="utf-8")
    if re.search(rf"slug:\s*{re.escape(slug)}\s*[,}}]", text):
        return False
    entry = (f'  - {{slug: {slug}, source: custom, owner: {DEFAULT_OWNER}, '
             f'onboarded: partial, name: {name}, purpose: "{purpose}"}}\n')
    registry_path.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")
    return True

def ensure_okr_registered(registry_path: pathlib.Path) -> bool:
    text = registry_path.read_text(encoding="utf-8")
    if re.search(r"slug:\s*okr\s*[,}]", text):
        return False
    entry = (f'  - {{slug: okr, source: custom, owner: {DEFAULT_OWNER}, '
             'onboarded: partial, name: Нексус OKR, '
             'purpose: "хребет целей квартала: OBJ/KR, связи DELIVERS/SERVES"}\n')
    # append under nexus_types list (end of file is safe — YAML list continues)
    registry_path.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")
    return True

def run_gate(ground_dir: pathlib.Path, subdir: pathlib.Path | None = None,
             registry_slugs=None) -> list[str]:
    """Lint GROUND (or a scoped subtree of it, e.g. NEXUS, for perf).

    `ground_dir` must always be the GROUND root — registry slugs are read from
    `<ground_dir>/NEXUS/_registry.yaml`. `subdir`, if given, restricts the
    actual file walk (lint_nodes) to that path, avoiding a full GROUND scan
    (e.g. the large _intake dump) while still resolving registry slugs
    correctly.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "sa_documentation"))
    import validate_ground as vg
    if registry_slugs is None:
        registry_slugs = vg._registry_slugs(str(ground_dir))
    lint_dir = subdir if subdir is not None else ground_dir
    return vg.lint_nodes(str(lint_dir), registry_slugs=registry_slugs)
