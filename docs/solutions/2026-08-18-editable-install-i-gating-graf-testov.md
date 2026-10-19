---
title: Editable-установка падала на плоском layout, а отсутствие scipy прятало граф-тесты
date: 2026-08-18
kind: bug
area: packaging
prs: [14]
adr: []
tags: [pyproject, setuptools, editable-install, conftest, gating]
source: retro
---

# Editable-установка падала на плоском layout, а отсутствие scipy прятало граф-тесты

## Ситуация

Путь установки из README — `pip install -e ".[graph]"` — не работал. На свежем окружении
editable-установка падала ещё на получении build-требований (`ERROR: Failed to build ...
when getting requirements to build editable`). У тех, кто установку всё же осилил,
падало 5 граф-тестов с `ModuleNotFoundError: scipy` и `sentence_transformers`, при этом
другие граф-тесты молча скипались: blanket-скип в `conftest.py` гейтил все граф-тесты
по одной паре модулей, и отсутствие вектор-зависимости прятало тесты, которым она
не нужна.

## Причина

Две дыры на одном пути:

- В `pyproject.toml` не было `[build-system]` и явного списка пакетов. Репо — плоский
  layout с тремя top-level каталогами (`paf_index`, `poh_memory`, `sa_documentation`),
  auto-discovery setuptools на нём спотыкается, и на Python 3.14 (разрешён
  `requires-python = ">=3.11"`) сборка падала до установки.
- Extra `graph` не перечислял фактических зависимостей: `networkx` импортит `scipy`
  для pagerank (PPR в `query`/`impact`/`insight`), `poh_memory/embedder.py` требует
  `sentence-transformers` для локального bge-m3 — и всё это приходилось ставить руками.
- `conftest.py` скипал граф-тесты одной корзиной по паре `falkordb`/`graphiti_core`,
  поэтому частичная установка выглядела то красными тестами, то тихо пропавшими.

## Решение

- `pyproject.toml`: объявлен `[build-system]` (setuptools) с явным списком пакетов;
  extra `graph` дополнен `scipy` и `sentence-transformers`.
- `conftest.py`: вместо blanket-списка `_GRAPH_TIER_TESTS` — карта `_REQUIREMENTS`:
  каждый из 13 граф-тестов объявляет модули, которые реально импортит (группы `_GRAPH`,
  `_PAGERANK` со scipy, `_VECTOR` со sentence-transformers). Хелпер `_absent` трактует
  битую/частичную установку (ImportError/ValueError при импорте) как «модуля нет» —
  коллекция не падает, тест просто не собирается.

## Как проверить

Editable-установка на чистом venv Python 3.14 — проходит, `import paf_index,
sa_documentation` работает. Прогон на окружении с `falkordb`/`networkx`/`scipy`/
`graphiti-core` и поднятым FalkorDB: 170 passed, 1 failed (оставшееся падение —
vocab-поиск от cwd, закрыт отдельным PR), embedder-тесты корректно скипаются, если
`sentence-transformers` не ставили (тянет torch и ~2.2 ГБ модели).

## Уроки

`pip install -e .` из README — это тест упаковки, и его надо гонять на чистом venv
новейшего разрешённого Python: auto-discovery setuptools ломается ровно там, где
разработчик не работает ежедневно. Зависимости extras обязаны быть полными: если
библиотека импортит пакет транзитивно-опционально (networkx → scipy для pagerank),
он должен быть в соответствующем extra, а не в голове установившего. Скип граф-тестов
«корзиной» прячет красное: гейт сбора тестов должен быть побитовым — файл к фактически
импортируемым им модулям.
