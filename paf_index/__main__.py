# paf_index/__main__.py
from __future__ import annotations
import argparse, os, pathlib, datetime
import yaml
from paf_index import frontmatter as fm, okr, derive, reconcile, report, write, episode
from paf_index import gaps as gaps_mod, candidates

# Typed edges that count for KR-spine reachability (MENTIONS excluded — it is a
# weak association, not a value-axis / spine edge). Oracle I4/I6 (FNR-4).
TYPED_EDGE_TYPES = {"OWNS", "SERVES", "DELIVERS", "involves",
                    "REALIZES", "BASED_ON", "DEPENDS_ON",
                    "ADDRESSES", "SATISFIES", "HAS_NEED"}

# Vault layout is client-agnostic: the concrete vault sets POH_VAULT (root) and
# POH_KR_MAP (path to the OKR KR→epic map) via env; defaults are neutral.
ROOT = pathlib.Path(os.environ.get("POH_VAULT", pathlib.Path.cwd()))
NEXUS = ROOT / "GROUND" / "NEXUS"
KRMAP = pathlib.Path(os.environ.get("POH_KR_MAP", ROOT / "ROADMAP" / "kr-epic-map.md"))
REGISTRY = NEXUS / "_registry.yaml"
PULSE = ROOT / "GROUND" / "PULSE" / "summaries"
INDEX = ROOT / "GROUND" / "_index"
CANDIDATES = INDEX / "skeleton-candidates.yaml"
STATUS = INDEX / "skeleton-status.yaml"

def _pipeline(today: str):
    nodes = fm.load_all_nexus_notes(NEXUS)
    rows = okr.parse_kr_epic_map(KRMAP)
    dr = derive.derive(nodes, rows, today)
    rr = reconcile.reconcile(nodes, dr.new_nodes, dr.edges, today)
    eps = episode.load_summaries(PULSE)
    edr = derive.derive_episode_edges(eps, nodes, today)
    vr = derive.derive_value_edges(nodes, today)
    return nodes, dr, rr, edr, vr

def main() -> int:
    ap = argparse.ArgumentParser(prog="paf_index")
    ap.add_argument("command", choices=["report", "build", "gaps", "promote", "gate"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = datetime.date.today().isoformat()
    nodes, dr, rr, edr, vr = _pipeline(today)

    if args.command == "report" or args.dry_run:
        # Deviation C: report / --dry-run are strictly read-only — no writes,
        # no registry mutation, no gate side effects.
        print(report.render_report(dr, rr, n_nodes=len(nodes), episode_result=edr))
        return 0

    if args.command == "gaps":
        all_edges = dr.edges + edr.edges + vr.edges
        gs = gaps_mod.find_gaps(nodes, all_edges)
        added = candidates.seed_gaps(CANDIDATES, gs)
        print(f"Дыр: {len(gs)}; новых в очередь: {added}. Очередь: {CANDIDATES}")
        for g in gs:
            print(f"- {g.src} [{g.reason}] {g.title}")
        print("\nВарианты KR (dst):")
        for nid, t in gaps_mod.kr_choices(dr.new_nodes, nodes):
            print(f"- {nid}: {t}")
        # Reachability to KR spine over typed edges (oracle I4/I6, FNR-4).
        # Denominator = value-axis content only (scaffolding excluded).
        rep = gaps_mod.reachability_from_kr(nodes, all_edges,
                                            edge_types=TYPED_EDGE_TYPES,
                                            content_filter=gaps_mod.is_value_content)
        n_content = sum(1 for n in nodes if gaps_mod.is_value_content(n))
        print(f"\nДостижимость value-контента от хребта KR (типизир. рёбра): "
              f"{rep.fraction:.1%} ({n_content - len(rep.unreachable)}/{n_content}); "
              f"недостижимо: {len(rep.unreachable)}")
        for nid in rep.unreachable[:20]:
            print(f"  - сирота: {nid}")
        # Value-axis coverage (oracle I5): content nodes with no value-axis edge.
        va = gaps_mod.value_axis_gaps(nodes, all_edges,
                                      content_filter=gaps_mod.is_value_content)
        print(f"\nБез ценностного ребра (I5): {len(va)}/{n_content} контент-узлов")
        return 0

    if args.command == "promote":
        nodes_by_id = {n.node_id: n for n in nodes}
        for n in fm.load_all_nexus_notes(NEXUS / "okr"):
            nodes_by_id[n.node_id] = n
        for n in fm.load_all_nexus_notes(NEXUS / "pulse"):
            nodes_by_id[n.node_id] = n
        changed, issues, skipped = candidates.promote(
            CANDIDATES, nodes_by_id, today,
            run_gate_fn=lambda: write.run_gate(ROOT / "GROUND", subdir=NEXUS))
        print(f"Изменено нот: {changed}. Пропущено: {len(skipped)}. Проблем гейта: {len(issues)}.")
        for s in skipped:
            print(f"- пропущен: {s}")
        return 0

    if args.command == "gate":
        all_edges = dr.edges + edr.edges + vr.edges
        inv = reconcile.check_invariants(nodes, dr.new_nodes, all_edges)
        gr = reconcile.gate(rr, inv)
        cand_counts: dict[str, int] = {}
        for c in candidates.load_candidates(CANDIDATES):
            cand_counts[c.status] = cand_counts.get(c.status, 0) + 1
        INDEX.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(
            yaml.safe_dump(reconcile.status_dict(gr, today), allow_unicode=True, sort_keys=False),
            encoding="utf-8")
        print(report.render_report(dr, rr, n_nodes=len(nodes), episode_result=edr,
                                    gate_result=gr, invariants=inv, candidate_counts=cand_counts))
        return 0

    # build (writes)
    write.ensure_okr_registered(REGISTRY)
    write.write_okr_nodes(dr.new_nodes, NEXUS / "okr")
    write.register_nexus(REGISTRY, "pulse", "Нексус PULSE (эпизоды)",
                         "оперативные эпизоды встреч: MENTIONS/involves")
    ep_nodes = [n for n in edr.new_nodes if n.node_type == "episode"]
    task_nodes = [n for n in edr.new_nodes if n.node_type == "task"]
    write.write_nodes(ep_nodes, NEXUS / "pulse", write.render_episode_note)
    if task_nodes:
        write.register_nexus(REGISTRY, "jira", "Нексус JIRA (ссылки на задачи)",
                             "лёгкие task-ref узлы для заземления на плоскость JIRA (medium-trust)")
        write.write_nodes(task_nodes, NEXUS / "jira", write.render_task_ref_note)

    # Deviation A: SERVES targets the new KR node (src) and the new OBJ node
    # (dst, no field written on it), DELIVERS targets the new KR node (dst).
    # Both are brand-new notes that don't exist in `nodes` (loaded before the
    # write above). Without merging the freshly-written OKR notes into
    # nodes_by_id, apply_edges silently drops SERVES/DELIVERS because
    # nodes_by_id.get(nid) returns None for them.
    # Merge freshly-written OKR + episode notes into nodes_by_id before apply_edges
    # (same reason as the OKR deviation: edges target brand-new notes).
    nodes_by_id = {n.node_id: n for n in nodes}
    for n in fm.load_all_nexus_notes(NEXUS / "okr"):
        nodes_by_id[n.node_id] = n
    for n in fm.load_all_nexus_notes(NEXUS / "pulse"):
        nodes_by_id[n.node_id] = n
    for n in fm.load_all_nexus_notes(NEXUS / "jira"):
        nodes_by_id[n.node_id] = n
    changed = write.apply_edges(dr.edges + edr.edges + vr.edges, nodes_by_id)

    # Deviation B: gate must be scoped to NEXUS, not the full GROUND tree —
    # GROUND also contains the ~5000-file _intake dump, and linting that
    # blows past a 2-minute budget. Registry slugs still come from the real
    # GROUND/NEXUS/_registry.yaml (includes 'okr' after ensure_okr_registered
    # above); only the file walk is scoped down to NEXUS.
    issues = write.run_gate(ROOT / "GROUND", subdir=NEXUS)

    print(report.render_report(dr, rr, n_nodes=len(nodes), episode_result=edr))
    print(f"\nИзменено нот: {changed}. Проблем гейта: {len(issues)}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
