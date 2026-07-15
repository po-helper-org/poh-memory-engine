# poh-memory-engine

Движок памяти **Kortex** — построение и обслуживание графа знаний по правилам и принципам методологии **PAF** (Product Adaptive Framework, productframework.ru, CC BY-SA 4.0).

## Миссия

Переход от **.md файловой структуры** Kortex к **гибридному хранилищу (граф + вектор)** и повышение эффективности AI-агента в работе с контекстом.

Носитель истины — markdown в git (Node schema во frontmatter). Граф и вектор-индекс — **производные и пересобираемые** артефакты поверх него. Движок детерминированно выводит типизированные связи из frontmatter, гейтит материализацию (ноль workslop / ноль висячих рёбер) и измеряет связность графа с хребтом целей (OKR).

## Что здесь есть (текущее состояние)

- **`paf_index/`** — детерминированный пайплайн: загрузка нот → деривация типизированных рёбер (хребет OKR + ценностная ось PAF) → проводка во frontmatter → гейт валидации → отчёты.
  - `frontmatter.py` — Node schema, парсинг frontmatter.
  - `derive.py` — деривация рёбер: `OWNS`/`SERVES`/`DELIVERS` (хребет) + ценностная ось `REALIZES`/`BASED_ON`/`DEPENDS_ON`/`ADDRESSES`/`SATISFIES`/`HAS_NEED`.
  - `write.py` — проводка рёбер во frontmatter (merge-ветка = антиклоббер ручных связей).
  - `gaps.py` — детектор достижимости от хребта KR (оракул связности I4/I6), фильтр каркаса.
  - `episode.py`/`okr.py`/`ground.py`/`resolve.py`/`reconcile.py`/`candidates.py`/`report.py` — эпизоды, OKR-хребет, заземление, согласование, очередь кандидатов, отчёты.
- **`sa_documentation/`** — схема, каталог, валидатор, дизайн-спеки.
  - `nexus_schema.md` / `nexus_catalog.md` / `ground_schema.md` / `naming_conventions.md` — модель данных PAF.
  - `validate_ground.py` — гейт: обязательные поля, `NODE_TYPES` enum, workslop, висячие рёбра, wilting/ripeness.
  - `FNR/` — дизайн-спеки (task → concept → debate → system_requirements) по пайплайну System Analyst.
  - `architecture/` — C4-диаграммы и арх-описание.
  - `tests/` — pytest-набор.

## Целевая архитектура (roadmap)

| Слой | Сейчас | Цель |
|---|---|---|
| Истина | markdown в git | markdown в git (без изменений) |
| Типы узлов | скелет + ценностная ось PAF | полная entity-модель PAF (Feature/Need/ValueProposition/Segment) |
| Рёбра | типизированные из frontmatter | + семантическая деривация (LLM на неоднозначном) |
| Хранилище | frontmatter | **граф (FalkorDB/Neo4j) + вектор (HNSW/bge-m3)** |
| Навигация | обход по типизир. рёбрам | PPR + PathRAG, вес ребра по типу |

См. `sa_documentation/FNR/FNR_4/ideal-model-plan-fact.md` — тест-оракул (модель данных PAF) + план/факт-леджер.

## Быстрый старт

```bash
python3 -m pytest sa_documentation/tests/ -q
```

Пайплайн (над git-волтом Kortex, задаётся снаружи):

```bash
python3 -m paf_index report --dry-run   # read-only отчёт
python3 -m paf_index gaps                # дыры + достижимость от KR
python3 -m paf_index gate                # гейт материализации
python3 -m paf_index build               # выводит + пишет рёбра во frontmatter
```

## Границы репозитория

Только **движок**. Клиентский контент (GROUND-волт, ROADMAP, BFT-документы конкретного продукта) — **вне** этого репозитория; движок работает над волтом, задаваемым снаружи.

## Атрибуция

Реализует методологию **PAF** (Тихомиров С., https://productframework.ru, CC BY-SA 4.0). Производные методологических материалов лицензируются реципрокно (CC BY-SA 4.0).
