"""Словарь канонических аспектов (измерений). Чистый (yaml read, без FalkorDB/LLM).
Агент растит словарь при /extract-claims (git-review); здесь — загрузка/проверка.
`is_canonical` совпадает с КАНОНИЧ. ИМЕНЕМ (ключом), НЕ с синонимом.
Спека: docs/superpowers/specs/2026-07-13-poh-claim-vocab-subject-key-design.md"""
from __future__ import annotations
import pathlib
import yaml

VOCAB_RELPATH = pathlib.Path("GROUND/_index/aspect-vocab.yaml")   # относительно корня волта
DEFAULT_VOCAB_PATH = VOCAB_RELPATH                                # cwd = корень волта


def vocab_path_for(nexus_root) -> pathlib.Path:
    """Путь словаря по волту, а не по cwd: движок работает над внешним волтом.

    `nexus_root` = <волт>/GROUND/NEXUS -> поднимаемся до GROUND. Если GROUND в
    пути нет, трактуем `nexus_root` как корень волта.
    """
    p = pathlib.Path(nexus_root)
    for anc in (p, *p.parents):
        if anc.name == "GROUND":
            return anc / "_index" / "aspect-vocab.yaml"
    return p / VOCAB_RELPATH


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
