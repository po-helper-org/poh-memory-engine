# poh_memory — граф памяти PO-Helper

Слой памяти помощника (EPIC-POH-LINKS, L2/L3). Строит **граф смысла** из размеченного
контекста vault и отвечает на вопросы, на которые файловый граф Obsidian ответить не может:
где риск, где противоречие, чем закрыта цель, какой вопрос не закрыт.

## Не путать с графом Obsidian

Обе штуки называются «граф», но меряют разное.

| | Граф Obsidian | Граф poh |
|:---|:---|:---|
| Узел | любой `.md` файл | размеченный frontmatter-узел с `node_id` (цель/эпик/KR/утверждение) |
| Ребро | любой `[[wikilink]]` / тег | **типизированная** связь: SERVES / DELIVERS / MENTIONS / ASSERTS / ABOUT / SUPERSEDED_BY |
| Узел без связи | показывается (зелёный шум) | **не существует** — не минтится |
| Дедуп | нет | по `node_id` (десятки файлов → один узел) |
| Что хранит | *что с чем соединено* | *что это значит и что из этого следует* |
| Размер | тысячи точек | сотни (дистиллят, не помойка) |

Большое число точек в Obsidian ≠ больше знаний. Это плотность файлов. Ценность poh — в
типах рёбер и claim-слое, которых у Obsidian нет в принципе.

## Что считается узлом

Единица узла = **канонический `node_id` из спайна** (`paf_index.frontmatter`), не файл.

- `edges.py` читает только узлы, которые распознал `paf_index` (структурный frontmatter
  с `node_id`), и дедупит по `node_id`.
- Узел минтится **только если он конец семантического ребра** (`serves` / `delivered_by` /
  `mentions` во frontmatter) или эпизод/grounded-узел claim'а. Изолированных узлов нет.
- Заметка без структурного frontmatter и без этих полей для движка **невидима**.

Отсюда компактность: poh видит не заметки, а размеченные узлы Нексусов.

## Типы узлов и рёбер

**Узлы:** `Entity` (цели/эпики/KR/системы), `Claim` (типизированное утверждение со встречи).

**Рёбра:**
- `SERVES` / `DELIVERS` / `MENTIONS` — семантические, из frontmatter (`serves` / `delivered_by` / `mentions`); несут `valid_at` (temporal).
- `ASSERTS` — эпизод (встреча) утверждает claim.
- `ABOUT` — claim привязан («про») к узлу графа. Claim без `ABOUT` = висящий (открытый вопрос).
- `SUPERSEDED_BY` — claim вытеснен более свежим (temporal-слой).

## Зачем создавали — что умеет, а Obsidian нет

Помощник отвечает на вопросы, требующие обхода графа по смыслу:

- **«Чем закрыта kr-X?»** → рёбра DELIVERS/SERVES.
- **«Какие факты со встреч относятся к этой цели?»** → обход в 3 прыжка `Claim -[ABOUT]-> Entity -[DELIVERS|SERVES]-> KR`.
- **«Где симптом → причина → эталон?»** → polarity на claim'ах (negative/positive/neutral).
- **«Какой вопрос я не закрыл?»** → claim без ABOUT (висящий).
- **«Что под риском / что противоречит / что устарело?»** → модули `risk`, `contradictions`, `supersede`.

### Живой пример (3 прыжка)

Запрос связывает цель ↔ систему ↔ живые факты со встречи за 1.3 мс:

```cypher
MATCH (c:Claim)-[:ABOUT]->(e:Entity)-[:DELIVERS|SERVES]->(kr:Entity)
RETURN c.subject, c.polarity, e.summary, kr.name
```

Результат: 4 утверждения про фонды со встречи 06.07 → узел `system-extapi-go` → служит `kr-1-5`.
Помощник отвечает: *«По kr-1-5 идёт шлюз extapi_go. Эталон — фонд МДТЗК (positive), но был
инцидент БДТ (negative), причина — неправильный тип фонда „Без Агентов“.»* Obsidian тут даёт
только точки без смысла.

## Модули

| Модуль | Назначение |
|:---|:---|
| `ingest.py` | инъекция спайна+эпизодов в FalkorDB (Cypher MERGE, детерм., ноль ключей) |
| `edges.py` | чтение семантических рёбер из frontmatter (`serves`/`delivered_by`/`mentions`) |
| `claims.py` | извлечение claim'ов из эпизодов |
| `vectors.py` | LanceDB-индекс эмбеддингов (bge-m3, dim 1024) |
| `query.py` | запросы к графу, `text_to_replica` |
| `supersede.py` | temporal-вытеснение claim'ов |
| `contradictions.py` | поиск противоречий |
| `communities.py` | кластеризация узлов (community_id) |
| `risk.py` | синтез типизированных рисков |
| `impact.py` | анализ влияния изменений |
| `reflexion.py` | верификация понятности графа |

## Runtime

- **Движок:** FalkorDB (Redis-граф, Cypher), Docker, порт **6380** (6379 занят нативным redis).
- **Граф:** `poh` (боевой), остальные `poh_*` — тестовые.
- **Эмбеддинги:** `BAAI/bge-m3`, dim 1024, качается при первом прогоне (~2.2 ГБ).
- **LanceDB-индекс:** `GROUND/_index/poh-lancedb` (пересбираемый, не в git).
- Runtime **не в git** — пересборка venv/FalkorDB/модели вручную.

### Просмотр графа

```bash
# текстом
docker exec falkordb-poh redis-cli GRAPH.QUERY poh "MATCH (n) RETURN labels(n)[0], count(n)"

# визуально в браузере (FalkorDB Browser, если проброшен порт 3000)
open http://localhost:3000
```

### Наполнение + запрос

```bash
"$HOME/.cache/poh-venv/bin/python" -c "import pathlib; \
from poh_memory.ingest import ingest; from poh_memory.vectors import build_index; \
from poh_memory.query import text_to_replica; \
ingest(pathlib.Path('GROUND/NEXUS'),'poh'); build_index(pathlib.Path('GROUND/NEXUS')); \
print(text_to_replica('poh','каталог кино',5,2))"
```

## Текущее ограничение

Движок наполнен узко — прогнан по `GROUND/NEXUS` (цели/эпики), почти не трогал живые
данные (PULSE-эпизоды, summaries). Отсюда мало claim'ов. Ценность растёт линейно с
наполнением: разбери десятки встреч в PULSE — и цепочки «цель ↔ система ↔ разговор ↔
инцидент» пойдут сотнями, риски и противоречия движок начнёт ловить автоматически.
