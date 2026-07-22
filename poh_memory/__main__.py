# poh_memory/__main__.py
"""CLI: `python -m poh_memory build` (цепочка L1 paf_index -> L2/L3 граф) или
`graph` (только граф). ingest_at = дата сборки. L1 самостоятелен (subprocess)."""
from __future__ import annotations
import argparse, datetime, pathlib, subprocess, sys
from poh_memory.build import build_graph


def main() -> int:
    ap = argparse.ArgumentParser(prog="poh_memory")
    ap.add_argument("command", choices=["build", "graph"])
    args = ap.parse_args()
    root = pathlib.Path.cwd()
    nexus = root / "GROUND" / "NEXUS"
    today = datetime.date.today().isoformat()

    if args.command == "build":
        r = subprocess.run([sys.executable, "-m", "paf_index", "build"], cwd=str(root))
        if r.returncode != 0:
            print(f"L1 (paf_index build) упал (код {r.returncode}); граф не строим.")
            return r.returncode

    res = build_graph(nexus, today)
    if not res["ok"]:
        print(f"Граф пропущен: {res['error']}. Запусти FalkorDB и повтори.")
        return 1
    print(f"Граф собран: {res['entities']} узлов, {res['claims']} claim'ов, "
          f"{res['edges_ingested']} семантич. рёбер, {res['communities']} сообществ "
          f"(ingest_at={today}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
