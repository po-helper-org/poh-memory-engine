# paf_index/report.py
from __future__ import annotations
from collections import Counter

def render_report(derive_result, reconcile_report, n_nodes: int, episode_result=None,
                  gate_result=None, invariants=None, candidate_counts=None) -> str:
    dr, rr = derive_result, reconcile_report
    by_type = Counter(e.type for e in dr.edges)
    lines = ["# Отчёт скелета paf_index", ""]
    lines.append(f"- Узлов прочитано: {n_nodes}")
    lines.append(f"- Новых узлов хребта: {len(dr.new_nodes)}")
    lines.append(f"- Рёбра: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    lines.append(f"- Owner не разрешён (в очередь): {len(dr.unresolved_owners)}")
    lines.append(f"- Изолированные узлы: {len(rr.isolated)}")
    lines.append(f"- Workslop (без sources): {len(rr.workslop)}")
    lines.append(f"- Dangling рёбра: {len(rr.dangling)}")
    lines.append("")
    lines.append("## ContextRipeness по нексусам")
    for nx, v in sorted(rr.context_ripeness.items(), key=lambda kv: kv[1]):
        flag = "OK" if v >= 0.6 else "низкая"
        lines.append(f"- {nx}: {v} ({flag})")
    if dr.unresolved_owners:
        lines.append("")
        lines.append("## Очередь: неразрешённые owner")
        for nid, owner in dr.unresolved_owners[:50]:
            lines.append(f"- {nid}: {owner}")
    if episode_result is not None:
        er = episode_result
        et = Counter(e.type for e in er.edges)
        lines.append("")
        lines.append("## Эпизоды")
        lines.append(f"- Эпизодов: {len(er.new_nodes)}")
        lines.append(f"- Рёбра эпизодов: " + ", ".join(f"{k}={v}" for k, v in sorted(et.items())))
        lines.append(f"- Участник не разрешён (в очередь): {len(er.unresolved_participants)}")
        lines.append(f"- Dangling refs (в очередь): {len(er.dangling_refs)}")
        for eid, raw in er.unresolved_participants[:50]:
            lines.append(f"  - {eid}: {raw}")
        for eid, ref in er.dangling_refs[:50]:
            lines.append(f"  - {eid}: ref {ref}")
        mentions = [e for e in er.edges if e.type == "MENTIONS"]
        nexus_high = sum(1 for e in mentions if e.confidence == "high")
        jira_medium = sum(1 for e in mentions if e.confidence == "medium")
        lines.append("")
        lines.append("## Заземление")
        lines.append(f"- nexus/high: {nexus_high}")
        lines.append(f"- jira/medium: {jira_medium}")
        lines.append(f"- не заземлено: {len(er.dangling_refs)}")
    if gate_result is not None:
        lines.append("")
        lines.append("## Скелет-гейт")
        lines.append(f"- Готов: {'да' if gate_result.passed else 'НЕТ'} (ripeness_min={gate_result.ripeness_min})")
        for r in gate_result.reasons:
            lines.append(f"  - {r}")
        if invariants is not None:
            lines.append(f"- KR без OWNS→person: {len(invariants['kr_without_owns'])}")
            lines.append(f"- Сироты спайна: {len(invariants['spine_orphans'])}")
            lines.append(f"- Противоречия владения: {len(invariants['ownership_contradictions'])}")
        if candidate_counts is not None:
            lines.append("- Кандидаты: " + ", ".join(f"{k}={v}" for k, v in sorted(candidate_counts.items())))
    return "\n".join(lines) + "\n"
