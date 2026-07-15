# GROUND Vault — Schema

Схема валидации GROUND Vault: `config.yaml` (§7 spec) + `NEXUS/_registry.yaml` (§2.2 spec).
Валидатор: `sa_documentation/validate_ground.py` (`validate_ground(ground_dir) -> list[str]`).

> Spec: `docs/superpowers/specs/2026-06-21-paf-team-os-design.md` (§7, §2.2).

---

## `GROUND/config.yaml`

Генерируется скиллом `/paf-init` (one-shot). Описывает клиента и его продуктовый контекст.

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `company` | string | да | Имя компании клиента. |
| `product.name` | string | да | Название продукта. |
| `product.slug` | ascii-slug | да | Slug продукта. Паттерн: `[a-z0-9][a-z0-9-]*` (без пробелов, кириллицы, заглавных). |
| `product.idea` | string | да | Краткая идея продукта (1–2 предложения). |
| `team.size` | int | да | Размер команды. |
| `team.roster.product_engineer` | string | **ДА (обязателен)** | Продуктовый инженер. Значение — имя человека. Не может быть null/пустым. |
| `team.roster.product_ops` | string \| `"Cortex"` \| null | нет | Product Ops (человек или делегировано Кортексу). |
| `team.roster.growth_engineer` | string \| `"Cortex"` \| null | нет | Growth Engineer. |
| `team.roster.portfolio_manager` | string \| `"Cortex"` \| null | нет | Portfolio Manager. |
| `team.roster.discovery_launcher_pm` | string \| `"Cortex"` \| null | нет | Discovery Launcher PM. |
| `team.roster.ai_ux_designer` | string \| `"Cortex"` \| null | нет | AI/UX Designer. |
| `cortex.phase_target` | int | да | Целевая фаза Кортекса (по умолч. 2). |
| `cortex.ruflo_mcp` | bool | да | Включён ли ruflo MCP. |
| `cortex.obsidian` | bool | да | Obsidian-режим (markdown frontmatter). |
| `onboarding.status` | enum | да | `init` \| `in_progress` \| `done`. |
| `onboarding.sources_ingested` | list[string] | нет | Ингестированные источники (из `_intake/`). |
| `onboarding.baseline_cr` | map | нет | Baseline Context Ripeness по Нексусам. |
| `onboarding.onboarded_at` | date \| null | нет | Дата завершения онбординга. |
| `nexus.catalog` | string | да | Источник каталога (по умолч. `master`). |
| `nexus.custom_count` | int | да | Кол-во кастомных Нексусов (из `_registry.yaml`, `source: custom`). |
| `created` | date | да | Дата создания GROUND (`/paf-init`). |
| `paf_step` | int | да | Текущий шаг PAF (0 = до Step-1-IDEA). |

**Правила валидации (текущая версия валидатора):**
1. `product.slug` обязан матчить `[a-z0-9][a-z0-9-]*`.
2. `team.roster.product_engineer` обязателен (не null/пусто). Остальные роли — optional.

---

## `GROUND/NEXUS/_registry.yaml`

Реестр Нексусов, инстанцированных для данного клиента: дефолтные (`source: default`, создаются `/paf-init`) + кастомные (`source: custom`, добавляются `/paf-nexus-create`). `/paf-onboard` работает по всему реестру.

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `nexus_types[].slug` | ascii-slug | да | Slug Нексуса. Паттерн: `[a-z][a-z0-9-]*`. Уникален. |
| `nexus_types[].source` | enum | да | `default` \| `custom`. |
| `nexus_types[].name` | string | нет | Человекочитаемое имя (обычно для кастомных, напр. «Нексус продавцов»). |
| `nexus_types[].owner` | string | нет | Владелец из `team.roster`. |
| `nexus_types[].purpose` | string | нет | Назначение Нексуса. |
| `nexus_types[].onboarded` | enum | да | `todo` \| `partial` \| `done` — статус онбординга (обновляет `/paf-onboard` Phase C). |

**Правила валидации (текущая версия валидатора):**
1. Каждый `slug` матчит `[a-z][a-z0-9-]*` (без заглавных/пробелов).
2. `source` ∈ {`default`, `custom`}.

---

## Валидный пример (оба файла)

`GROUND/config.yaml`:
```yaml
company: ACME
product:
  name: Billing
  slug: acme-billing          # ascii-slug
  idea: Подписочный биллинг для SMB с автоинвойсами.
team:
  size: 3
  roster:
    product_engineer: Jane    # ОБЯЗАТЕЛЕН
    product_ops: Cortex
    growth_engineer: Cortex
cortex:
  phase_target: 2
  ruflo_mcp: true
  obsidian: true
onboarding:
  status: init                # init | in_progress | done
  sources_ingested: []
  baseline_cr: {}
  onboarded_at: null
nexus:
  catalog: master
  custom_count: 0
created: 2026-06-21
paf_step: 0
```

`GROUND/NEXUS/_registry.yaml`:
```yaml
nexus_types:
  - {slug: market,   source: default, onboarded: todo}
  - {slug: customer, source: default, onboarded: todo}
  - {slug: product,  source: default, onboarded: todo}
  - {slug: growth,   source: default, onboarded: todo}
  # кастомные (добавлены /paf-nexus-create):
  - {slug: sellers, source: custom, name: Нексус продавцов, owner: Growth Engineer, purpose: "...", onboarded: todo}
```

---

## Использование валидатора

Два уровня проверки:

1. **`validate_ground(dir)`** — структура `config.yaml` + `NEXUS/_registry.yaml` (hard errors, см. выше).
2. **`lint_nodes(dir)`** — линтер узлов-нот по [[nexus_schema]] §2–4: обязательные ключи frontmatter, `nexus ∈ registry`, валидность `node_type`/`kind`/`confidence`/`ripeness`, непустой `sources` (workslop-правило), **целостность рёбер графа** (`reports_to`/`manages`/`collaborates_with` → существующий `node_id`), **дрейф `ripeness`** (заявленный vs вычисленный из `updated`+`ttl_days`) и wilting-узлы. Возвращает строки `ERROR:`/`WARN:`. Пустой `sources` у MOC-заглушек (`_index`) — WARN, у контент-узлов — ERROR.

```python
from sa_documentation.validate_ground import validate_ground, lint_nodes

struct = validate_ground("GROUND")          # config + registry
nodes = lint_nodes("GROUND")                 # узлы + рёбра + свежесть
for i in struct + nodes:
    print(i)
```

CLI (печатает обе секции, exit 1 при hard errors):
```bash
python3 -m sa_documentation.validate_ground GROUND
```
