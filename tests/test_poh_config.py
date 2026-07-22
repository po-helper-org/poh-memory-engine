import importlib


def test_defaults(monkeypatch):
    monkeypatch.delenv("FALKOR_HOST", raising=False)
    monkeypatch.delenv("FALKOR_PORT", raising=False)
    import poh_memory.config as cfg
    importlib.reload(cfg)
    assert cfg.FALKOR_HOST == "localhost"
    assert cfg.FALKOR_PORT == 6380


def test_env_override(monkeypatch):
    monkeypatch.setenv("FALKOR_HOST", "falkordb")
    monkeypatch.setenv("FALKOR_PORT", "6379")
    import poh_memory.config as cfg
    importlib.reload(cfg)
    assert cfg.FALKOR_HOST == "falkordb"
    assert cfg.FALKOR_PORT == 6379


def test_client_reexports_config(monkeypatch):
    monkeypatch.delenv("FALKOR_HOST", raising=False)
    monkeypatch.delenv("FALKOR_PORT", raising=False)
    import poh_memory.config as cfg
    import poh_memory.client as client
    importlib.reload(cfg)
    importlib.reload(client)
    assert client.FALKOR_HOST == "localhost"
    assert client.FALKOR_PORT == 6380
