import pathlib
from poh_memory.vocab import load_aspect_vocab, canonical_aspects, is_canonical

VOCAB_YAML = """aspects:
  - canonical: "каналы вывода / B2B-маршрутизация"
    synonyms: ["каналы вывода", "вывод в B2B-шлюз"]
    note: "куда выводится фонд"
  - canonical: "актуальность/жизненный цикл"
    synonyms: ["актуальность и отслеживание"]
"""


def test_load_parses_canonical_and_synonyms(tmp_path):
    p = tmp_path / "v.yaml"
    p.write_text(VOCAB_YAML, encoding="utf-8")
    vocab = load_aspect_vocab(p)
    assert set(vocab.keys()) == {"каналы вывода / B2B-маршрутизация", "актуальность/жизненный цикл"}
    assert vocab["каналы вывода / B2B-маршрутизация"] == {"каналы вывода", "вывод в B2B-шлюз"}


def test_canonical_not_in_own_synonym_set(tmp_path):
    p = tmp_path / "v.yaml"
    p.write_text(VOCAB_YAML, encoding="utf-8")
    vocab = load_aspect_vocab(p)
    canon = "каналы вывода / B2B-маршрутизация"
    assert canon not in vocab[canon]   # каноническое имя НЕ входит в свой set синонимов


def test_canonical_aspects_returns_keys(tmp_path):
    p = tmp_path / "v.yaml"
    p.write_text(VOCAB_YAML, encoding="utf-8")
    assert canonical_aspects(load_aspect_vocab(p)) == {
        "каналы вывода / B2B-маршрутизация", "актуальность/жизненный цикл"}


def test_is_canonical_true_for_canonical_false_for_synonym(tmp_path):
    p = tmp_path / "v.yaml"
    p.write_text(VOCAB_YAML, encoding="utf-8")
    vocab = load_aspect_vocab(p)
    assert is_canonical("каналы вывода / B2B-маршрутизация", vocab) is True
    assert is_canonical("вывод в B2B-шлюз", vocab) is False   # синоним НЕ канонич.
    assert is_canonical("что-то новое", vocab) is False


def test_missing_file_returns_empty(tmp_path):
    assert load_aspect_vocab(tmp_path / "nope.yaml") == {}
