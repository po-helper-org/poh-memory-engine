"""Makes the repo root importable for tests (paf_index / poh_memory / sa_documentation).

The graph+vector tier (poh_memory) needs optional dependencies — see the
`graph` extra in pyproject.toml. When they are absent the markdown tier still
runs in full; the graph-tier tests are skipped rather than reported as errors.
"""
import importlib.util

_GRAPH_DEPS = ("falkordb", "graphiti_core")
_missing = [m for m in _GRAPH_DEPS if importlib.util.find_spec(m) is None]

# Tests that import the graph backend at module level.
_GRAPH_TIER_TESTS = [
    "tests/test_poh_build.py",
    "tests/test_poh_config.py",
    "tests/test_poh_claim_ingest.py",
    "tests/test_poh_claim_isolation.py",
    "tests/test_poh_communities.py",
    "tests/test_poh_communities_ingest.py",
    "tests/test_poh_embedder.py",
    "tests/test_poh_impact.py",
    "tests/test_poh_insight.py",
    "tests/test_poh_reflexion.py",
    "tests/test_poh_risk.py",
    "tests/test_poh_supersede.py",
    "tests/test_poh_supersede_ingest.py",
]

collect_ignore = _GRAPH_TIER_TESTS if _missing else []
