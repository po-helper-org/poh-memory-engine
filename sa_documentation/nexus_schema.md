# Nexus Schema — конвенция Node для Obsidian-Нексуса (Phase 0)

> Конкретная реализация столпа «Нексус» [S1] III.1 поверх Obsidian: каждая нота хранилища = **Узел (Node)** Нексуса. Метаданные — в **YAML frontmatter**. Это превращает vault в живой граф контекста (цифровой профиль продукта), который читает Кортекс (RAG) и который не гниёт в документацию (логика wilting).
> Базируется на `docs/AI-PROCESSES/STEP-0-FOUNDATION/1.nexus-setup.md` (Node schema) и `operating-model.md` (столп 1, 4).
> Принцип: **ноль галлюцинаций** — Узел без `sources` = workslop, не попадает в Нексус [S2] III.7.

---

## 1. Зачем

PAF сознательно «не фиксирует технологию» [S1]. Эта конвенция — **минимально-трассевая реализация Нексуса на том, что уже есть** (Obsidian vault + frontmatter), без Neo4j/отдельной БД. Шаг Phase 0 из аудита STEP-0: «Obsidian-as-Nexus».

- markdown-нота = Узел; **wiki-links** = рёбра графа; **frontmatter** = Node schema.
- Кортекс (Claude Code + ruflo RAG) читает frontmatter → знает тип/владельца/CP/спелость каждого Узла без разбора тела.

---

## 2. Frontmatter Node schema

Каждая нота-Узел начинается YAML-блоком `--- ... ---` со следующими ключами:

| Ключ | Тип | Описание | Обязательный |
|---|---|---|---|
| `nexus` | open slug | **open slug** (любой из `GROUND/NEXUS/_registry.yaml`); дефолтный минимум в [[nexus_catalog]] | ✅ |
| `node_id` | string | Стабильный идентификатор (ascii, нижний регистр, напр. `aip-7-overview`) | ✅ |
| `node_type` | enum | Тип узла (см. §3) | ✅ |
| `paf_step` | int\|null | Шаг AI-PROCESSES (0–8) или `null` для мета-узлов | ✅ |
| `sprint_phase` | enum\|null | `pulse`\|`scout`\|`bunch`\|`pitch`\|`execute`\|`harvest` \| `null` | — |
| `kind` | enum | `normative` (метод/каркас — CP = traceability to PAF) \| `empirical` (контекст продукта — CP = evidence) | ✅ |
| `owner` | string | RACI Accountable (роль PAF) | ✅ |
| `confidence` | float 0–1 | Confidence Point Узла. normative: 1.0 = полностью трассируется до [S1]–[S4]; empirical: уровень валидационных доказательств | ✅ |
| `sources` | list[string] | Источники (`[S1]`,`[S2]`, URL, RB-STEP-N.M, интервью #N, аналитика). **Узел без `sources` = workslop** | ✅ |
| `updated` | date ISO | Дата последнего обновления (YYYY-MM-DD) | ✅ |
| `ttl_days` | int | Срок актуальности в днях. normative: 365; empirical: market/customer=90, growth=60 | ✅ |
| `ripeness` | enum | `fresh` \| `ripening` \| `wilting` — вычисляется из `updated`+`ttl_days` (см. §4) | ✅ |
| `tags` | list[string] | Доп. теги (Obsidian), напр. `[fit-point]`, `[sprint-engine]` | — |

### 2.1 Кастомные Nexus-типы

Поле `nexus` — **открытый slug**, не фиксированный enum: значение берётся из реестра клиента `GROUND/NEXUS/_registry.yaml`. Дефолтный минимальный набор (market/customer/product/growth) и опциональные PAF-типы (ops-model, company) определены в [[nexus_catalog]].

Клиент определяет **кастомные** Нексусы под своё решение (напр. `sellers`, `buyers`, `supply-chain`):
- Команда: `/paf-nexus-create` → интервью (name, slug, purpose, owner из roster, seed_questions, опц. paf_step, опц. schema_extensions) → создаёт `GROUND/NEXUS/<slug>/` и регистрирует в `GROUND/NEXUS/_registry.yaml` (`source: custom`).
- Гвардраилы: slug уникален; конфликт с дефолтными / мастер-каталогом [[nexus_catalog]] → предупреждение; owner должен быть из roster.
- **`schema_extensions`** — опц. тип-специфичные поля поверх базовой Node schema (§2). Напр. кастомный Нексус `sellers` может добавить поле `quota_attainment` — оно живёт рядом с `nexus`/`confidence`/`sources`, но не заменяет их.
- Узлы кастомного Нексуса подчиняются **тем же правилам** Node schema: `sources` (Узел без sources = workslop), `confidence` (Confidence Point), `updated`/`ttl_days`, `ripeness` (wilting логика §4). `kind` = `normative` \| `empirical` по природе узла.

### 2.2 Empirical узлы клиента (GROUND Vault)

Узлы контекста продукта клиента живут в `GROUND/` (GROUND Vault) и имеют `kind: empirical` — это допущения и факты, не методология.

| Аспект | Значение |
|---|---|
| `kind` | `empirical` |
| `sources` | `["onboarding:<doc>"]` (из ингестии доков, Phase A) \| `["onboarding:interview"]` (из интервью, Phase B) \| последующие: аналитика, эксперимент, интервью Steps 1–8 |
| `confidence` по умолчанию | **0.2–0.4** (допущение онбординга, **не валидировано**). CP поднимают Steps 1–8 (интервью/эксперименты → 0.5–1.0). |
| `ttl_days` | короче, чем у normative (365): **market/customer = 90, growth = 60**. Быстрее wilting → раньше триггерит обновление/верификацию. |

В тело каждого такого узла ставится пометка:

> ⚠️ **допущение клиента (онбординг)**, требует валидации в Steps 1–8. CP отражает уровень доверия к допущению, не подтверждённый факт.

> Онбординг цифровизует, **не валидирует** [S1] Принцип 4, [S2] III.7. Не выдавать допущения за факты. См. [[nexus_catalog]] (seed_questions для интервью) и [[ground_schema]] (структура GROUND Vault).

---

## 3. `node_type` — валидные значения

| Значение | Где | Пример |
|---|---|---|
| `spine` | Хребет фреймворка | README.md |
| `operating-model` | Правила игры | operating-model.md |
| `gates` | Fit-точки/гейты | fit-points.md |
| `bootstrap` | Step 0 Foundation | STEP-0-FOUNDATION/* |
| `step-overview` | overview шага | STEP-N-*/overview.md |
| `sprint-phase` | Фаза цикла Sprint | STEP-N-*/{pulse,scout,bunch,pitch,execute,harvest}.md |
| `person` | Нексус `team` — персона | GROUND/NEXUS/team/*.md |

---

## 4. Wilting и Context Ripeness (вычисляемые метрики)

### `ripeness` Узла (из `updated` + `ttl_days`)
Пусть `age = today − updated` (в днях), `p = age / ttl_days`:
- `p < 0.5` → **fresh**
- `0.5 ≤ p < 1.0` → **ripening**
- `p ≥ 1.0` → **wilting** (Кортекс флагирует, требует обновления/верификации)

> Шаг Phase 2 (ruflo): `hooks_route` триггерит пересчёт `ripeness` по событию времени; Wilting-детектор-агент помечает протухшие Узлы.

### Context Ripeness Нексуса = **полнота × актуальность** [S1] III.1
Для Нексуса X (набор его Узлов):
```
completeness(X) = (число Узлов с заполненными обязательными полями) / (всего Узлов X)
freshness(X)    = weighted_mean( freshness_score(узел), weight=confidence )
                  где freshness_score = clamp(1 − p, 0, 1)
ContextRipeness(X) = completeness(X) × freshness(X)
```
- **Целевой порог** Context Ripeness ≥ 0.6 для перехода между шагами (см. `docs/AI-PROCESSES/fit-points.md`).
- Pulse-агент в начале каждого шага читает `Context Ripeness` по всем 4 Нексусам → заполняет шаблон Progress Pulse (`STEP-0-FOUNDATION/4.progress-pulse.md`).

---

## 5. Как Кортекс читает/пишет

- **Чтение (RAG):** ruflo `memory_search` / GraphRAG по frontmatter → поиск Узлов по `nexus`, `node_type`, `confidence`, `ripeness`. Напр. «все wilting-Узлы market с CP<0.5».
- **Запись:** Nexus-Builder-агент создаёт/обновляет Узел, проставляя `updated=now`, пересчитывает `ripeness`, требует `sources[]`.
- **Phase 1 (Claude Code):** агенты читают frontmatter напрямую из vault.
- **Phase 2 (ruflo):** `memory_store` индексирует Узлы; `hooks_route` → event-driven wilting.

---

## 6. Пилот: AI-PROCESSES как первый Нексус

AI-PROCESSES — это **продукт** (сам фреймворк). Его 64 ноты = **Нексус продукта** (`nexus: product`, `kind: normative`). Каждая нота получает frontmatter по этой конвенции:
- `owner` по RACI из `1.nexus-setup.md`: market→Portfolio Manager, customer→Product Engineer, product→Product Engineer, growth→Growth Engineer.
- `nexus` по шагу: Step 1→product, 2→customer, 3→market, 4→product, 5→growth, 6→growth, 7→product, 8→growth.
- `confidence: 1.0` (всё трассируется до [S1]–[S4]); `ttl_days: 365` (normative); `ripeness: fresh`.

> Пилот доказывает: schema работает на реальных нотах. Для **empirical** контекста (реальный продукт) — те же ключи, но `confidence`/`sources` отражают интервью/аналитику, `ttl_days` короче.
>
> **Разделение:** AI-PROCESSES — **normative** Nexus фреймворка (`kind: normative`, `confidence: 1.0`, трассируется до [S1]–[S4]); GROUND Vault клиента — **empirical** (`kind: empirical`, low-CP допущения онбординга, см. §2.2). Коробка не смешивает методологию с контекстом клиента.

---

## 7. Пример frontmatter (sprint-phase)

```yaml
---
nexus: product
node_id: aip-7-harvest
node_type: sprint-phase
paf_step: 7
sprint_phase: harvest
kind: normative
owner: Product Engineer
confidence: 1.0
sources: ["[S1]", "[S2]", "[S3]", "[S4]", "RB-STEP-7"]
updated: 2026-06-20
ttl_days: 365
ripeness: fresh
tags: [pmf, fit-point]
---
```

---
**Version:** 1.2 (v4: добавлен node_type: person для team-нексуса) · **Last updated:** 2026-06-24 · **Связанные:** [[nexus_catalog]] · [[naming_conventions]] · [[ground_schema]] · [[docs/AI-PROCESSES/operating-model|operating-model]] · [[docs/AI-PROCESSES/STEP-0-FOUNDATION/1.nexus-setup|1.nexus-setup]]
