"""Словарь канонических аспектов (измерений). Чистый (yaml read, без FalkorDB/LLM).
Агент растит словарь при /extract-claims (git-review); здесь — загрузка/проверка.
`is_canonical` совпадает с КАНОНИЧ. ИМЕНЕМ (ключом), НЕ с синонимом.
Спека: docs/superpowers/specs/2026-07-13-poh-claim-vocab-subject-key-design.md"""
from __future__ import annotations
import pathlib
import yaml

DEFAULT_VOCAB_PATH = pathlib.Path("GROUND/_index/aspect-vocab.yaml")   # относительно cwd (репо-корень)


def load_aspect_vocab(path=DEFAULT_VOCAB_PATH) -> dict[str, set[str]]:
    """{canonical: {synonyms...}}. Отсутствующий/пустой файл -> {}.
    Каноническое имя в set синонимов НЕ включается."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: dict[str, set[str]] = {}
    for entry in data.get("aspects", []):
        if not isinstance(entry, dict):
            continue
        canon = entry.get("canonical")
        if not canon:
            continue
        out[str(canon)] = {str(s) for s in (entry.get("synonyms") or [])}
    return out


def canonical_aspects(vocab: dict[str, set[str]]) -> set[str]:
    return set(vocab.keys())


def is_canonical(aspect: str, vocab: dict[str, set[str]]) -> bool:
    """True только если aspect == каноническое имя (ключ). Синоним -> False."""
    return aspect in vocab
