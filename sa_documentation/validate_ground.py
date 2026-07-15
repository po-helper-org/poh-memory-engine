"""Валидатор GROUND Vault.

Два уровня проверки:
  1. validate_ground(dir) — структура config.yaml + NEXUS/_registry.yaml (hard errors).
  2. lint_nodes(dir)      — линтер узлов-нот: frontmatter, целостность рёбер графа,
                            дрейф ripeness (workslop / wilting / dangling edges).

См. sa_documentation/ground_schema.md, nexus_schema.md и spec
docs/superpowers/specs/2026-06-21-paf-team-os-design.md (§7, §2.2).
"""
import datetime
import pathlib
import re

import yaml

# --- Node schema (nexus_schema.md §2, §3, §4) ---------------------------------

# Обязательные ключи frontmatter (ключ должен присутствовать; значение может быть null
# только там, где схема это разрешает — paf_step/sprint_phase).
REQUIRED_KEYS = [
    "nexus", "node_id", "node_type", "kind", "owner",
    "confidence", "sources", "updated", "ttl_days", "ripeness",
]
NODE_TYPES = {
    "spine", "operating-model", "gates", "bootstrap",
    "step-overview", "sprint-phase", "person",
    "system-component",  # кастомный тип system-нексуса (см. GROUND/NEXUS/system/_index.md)
    # EPIC-POH-LINKS spine (FNR-3):
    "objective", "key-result", "epic", "task",
    "episode", "risk", "decision", "component-ref",
    # Value-axis types (FNR-4): Phase 1 spine + Phase 2 rungs.
    "product", "service", "interface", "platform",
    "feature", "value-proposition", "need", "segment",
    # Transitional types present in enriched graph (pre-FNR-4), pending retype.
    "initiative", "entity", "concept",
}
KINDS = {"normative", "empirical"}
RIPENESS = {"fresh", "ripening", "wilting"}
# Поля-рёбра графа: ссылаются на node_id других узлов.
EDGE_FIELDS_SINGLE = ["reports_to", "owns_node", "serves"]
EDGE_FIELDS_LIST = ["manages", "collaborates_with", "delivered_by", "mentions", "involves",
                    # Value-axis edge fields (FNR-4) — linted for dangling refs.
                    "realizes", "based_on", "depends_on", "addresses", "satisfies", "has_need"]

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Ноды-заглушки MOC (пустой sources допустим до онбординга).
_INDEX_STEMS = {"_index", "_registry"}


def validate_ground(ground_dir):
    """Проверить структуру GROUND (config + registry). Список строк-ошибок (пустой = OK)."""
    errs = []
    ground_dir = pathlib.Path(ground_dir)
    cfg_p = ground_dir / "config.yaml"
    reg_p = ground_dir / "NEXUS/_registry.yaml"

    if not cfg_p.exists():
        return [f"missing {cfg_p}"]

    cfg = yaml.safe_load(cfg_p.read_text()) or {}

    slug = (cfg.get("product") or {}).get("slug", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(slug)):
        errs.append(f"product.slug invalid ascii-slug: {slug!r}")

    roster = (cfg.get("team") or {}).get("roster") or {}
    if not roster.get("product_engineer"):
        errs.append("team.roster.product_engineer is required")

    if reg_p.exists():
        reg = yaml.safe_load(reg_p.read_text()) or {}
        for t in reg.get("nexus_types", []) or []:
            s = t.get("slug", "")
            if not re.fullmatch(r"[a-z][a-z0-9-]*", str(s)):
                errs.append(f"nexus slug invalid: {s!r}")
            if t.get("source") not in ("default", "custom"):
                errs.append(f"nexus {s!r} source must be default|custom")

    return errs


# --- Node linter --------------------------------------------------------------

def _registry_slugs(ground_dir):
    reg_p = pathlib.Path(ground_dir) / "NEXUS/_registry.yaml"
    if not reg_p.exists():
        return set()
    reg = yaml.safe_load(reg_p.read_text()) or {}
    return {t.get("slug") for t in (reg.get("nexus_types") or []) if t.get("slug")}


def _parse_frontmatter(text):
    """Вернуть dict frontmatter, None (нет блока) или 'PARSE_ERROR'."""
    m = _FM_RE.match(text)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return "PARSE_ERROR"


def _as_date(val):
    """Привести updated к datetime.date (YAML может дать date или строку)."""
    if isinstance(val, datetime.date):
        return val
    if isinstance(val, str):
        try:
            return datetime.date.fromisoformat(val.strip())
        except ValueError:
            return None
    return None


def _compute_ripeness(updated, ttl_days, today):
    if not isinstance(ttl_days, (int, float)) or ttl_days <= 0:
        return None
    d = _as_date(updated)
    if d is None:
        return None
    p = (today - d).days / ttl_days
    if p < 0.5:
        return "fresh"
    if p < 1.0:
        return "ripening"
    return "wilting"


def _iter_node_files(ground_dir):
    for p in sorted(pathlib.Path(ground_dir).rglob("*.md")):
        if p.name == "_template.md":
            continue
        yield p


def lint_nodes(ground_dir, registry_slugs=None, today=None):
    """Пролинтить узлы-ноты GROUND. Возвращает список 'SEVERITY: rel_path: msg'.

    SEVERITY: ERROR (ломает схему/граф) | WARN (качество/свежесть).
    Линтуются только .md-файлы с YAML-frontmatter; файлы без него (README, top-MOC) — пропускаются.
    """
    ground_dir = pathlib.Path(ground_dir)
    if registry_slugs is None:
        registry_slugs = _registry_slugs(ground_dir)
    if today is None:
        today = datetime.date.today()

    issues = []
    nodes = {}            # node_id -> rel_path
    parsed = []           # (rel_path, is_index, frontmatter)

    # Проход 1: собрать node_id и распарсить.
    for p in _iter_node_files(ground_dir):
        rel = p.relative_to(ground_dir).as_posix()
        fm = _parse_frontmatter(p.read_text())
        if fm is None:
            continue  # не узел (нет frontmatter)
        if fm == "PARSE_ERROR":
            issues.append(f"ERROR: {rel}: frontmatter YAML не парсится")
            continue
        is_index = p.stem in _INDEX_STEMS
        nid = fm.get("node_id")
        if nid:
            if nid in nodes:
                issues.append(f"ERROR: {rel}: дубликат node_id {nid!r} (также {nodes[nid]})")
            else:
                nodes[nid] = rel
        parsed.append((rel, is_index, fm))

    # Проход 2: проверить каждый узел.
    for rel, is_index, fm in parsed:
        # Обязательные ключи.
        for k in REQUIRED_KEYS:
            if k not in fm:
                issues.append(f"ERROR: {rel}: отсутствует обязательный ключ frontmatter {k!r}")

        nexus = fm.get("nexus")
        if nexus is not None and registry_slugs and nexus not in registry_slugs:
            issues.append(f"ERROR: {rel}: nexus {nexus!r} нет в _registry.yaml")

        nt = fm.get("node_type")
        if nt is not None and nt not in NODE_TYPES:
            issues.append(f"ERROR: {rel}: node_type {nt!r} невалиден (ожидается {sorted(NODE_TYPES)})")

        kind = fm.get("kind")
        if kind is not None and kind not in KINDS:
            issues.append(f"ERROR: {rel}: kind {kind!r} должен быть normative|empirical")

        conf = fm.get("confidence")
        if conf is not None and (not isinstance(conf, (int, float)) or not 0 <= conf <= 1):
            issues.append(f"ERROR: {rel}: confidence {conf!r} должен быть числом 0..1")

        rip = fm.get("ripeness")
        if rip is not None and rip not in RIPENESS:
            issues.append(f"ERROR: {rel}: ripeness {rip!r} должен быть fresh|ripening|wilting")

        # sources: узел без источников = workslop. Для MOC-заглушек — только WARN.
        srcs = fm.get("sources")
        if not srcs:
            sev = "WARN" if is_index else "ERROR"
            note = " (MOC-заглушка до онбординга)" if is_index else " (workslop — узел без источника)"
            issues.append(f"{sev}: {rel}: пустой sources{note}")

        # Дрейф ripeness: заявленный vs вычисленный из updated+ttl_days.
        computed = _compute_ripeness(fm.get("updated"), fm.get("ttl_days"), today)
        if computed and rip and computed != rip:
            issues.append(
                f"WARN: {rel}: ripeness={rip!r}, но по updated+ttl_days сейчас {computed!r} "
                f"(пересчитать / обновить узел)"
            )
        if computed == "wilting":
            issues.append(f"WARN: {rel}: узел wilting (протух по ttl_days) — требует верификации")

        # Целостность рёбер графа.
        for f in EDGE_FIELDS_SINGLE:
            tgt = fm.get(f)
            if tgt and tgt not in nodes:
                issues.append(f"ERROR: {rel}: {f} -> {tgt!r} — висячее ребро (нет такого node_id)")
        for f in EDGE_FIELDS_LIST:
            if f == "delivered_by":
                continue  # epic keys (JIRA), not node_ids — resolved in a later increment
            for tgt in (fm.get(f) or []):
                if tgt and tgt not in nodes:
                    issues.append(f"ERROR: {rel}: {f} -> {tgt!r} — висячее ребро (нет такого node_id)")

    return issues


if __name__ == "__main__":
    import sys

    d = sys.argv[1] if len(sys.argv) > 1 else "GROUND"
    struct = validate_ground(d)
    node_issues = lint_nodes(d)

    print("== STRUCTURE (config + registry) ==")
    print("\n".join(struct) or "OK")

    errors = [i for i in node_issues if i.startswith("ERROR")]
    warns = [i for i in node_issues if i.startswith("WARN")]
    print(f"\n== NODES == ({len(errors)} errors, {len(warns)} warnings)")
    print("\n".join(node_issues) or "OK")

    sys.exit(1 if (struct or errors) else 0)
