"""Makes the repo root importable for tests (paf_index / poh_memory / sa_documentation).

The graph+vector tier (poh_memory) needs optional dependencies — see the
`graph` extra in pyproject.toml. When they are absent the markdown tier still
runs in full; the graph-tier tests are skipped rather than reported as errors.

Each test file declares what it actually imports at module level, so a missing
vector dependency no longer hides graph tests that do not need it — and no
longer turns them red either (issue #11).
"""
import importlib.util

_GRAPH = ("falkordb", "graphiti_core")
_PAGERANK = _GRAPH + ("scipy",)          # networkx imports scipy for pagerank
_VECTOR = _GRAPH + ("sentence_transformers",)

# Test file -> modules it needs importable.
_REQUIREMENTS = {
    "tests/test_poh_build.py": _GRAPH,
    "tests/test_poh_config.py": _GRAPH,
    "tests/test_poh_claim_ingest.py": _GRAPH,
    "tests/test_poh_claim_isolation.py": _GRAPH,
    "tests/test_poh_communities.py": _GRAPH,
    "tests/test_poh_communities_ingest.py": _GRAPH,
    "tests/test_poh_embedder.py": _VECTOR,
    "tests/test_poh_impact.py": _PAGERANK,
    "tests/test_poh_insight.py": _PAGERANK,
    "tests/test_poh_reflexion.py": _GRAPH,
    "tests/test_poh_risk.py": _GRAPH,
    "tests/test_poh_supersede.py": _GRAPH,
    "tests/test_poh_supersede_ingest.py": _GRAPH,
}


def _absent(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is None
    except (ImportError, ValueError):   # broken/partial install reads as absent
        return True


collect_ignore = [path for path, mods in _REQUIREMENTS.items()
                  if any(_absent(m) for m in mods)]
