"""Score-noise study over the presets: how often each layer keeps its pick when every knowledge-base
score is shifted by seeded random noise (+/-0.25 and +/-0.5). Prints a Markdown table.

    python tools/robustness_report.py [--runs 30]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.kb import LAYERS, load_presets  # noqa: E402
from engine.robustness import NOISE_LEVELS, robustness  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=30)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    lv = " / ".join(f"±{n:g}" for n in NOISE_LEVELS)
    print(f"| Preset | " + " | ".join(f"{l.title()} ({lv})" for l in LAYERS) + " |")
    print("|---|" + "---|" * len(LAYERS))
    for p in load_presets():
        r = robustness(p["input"], runs=a.runs)
        if not r["feasible"]:
            print(f"| {p['id']} | infeasible |")
            continue
        cells = []
        for l in LAYERS:
            pct = " / ".join(f"{x['held_pct']}%" for x in r["layers"][l])
            cells.append(f"{r['base'][l]}: {pct}")
        print(f"| {p['id']} | " + " | ".join(cells) + " |")
    print(f"\nEach cell: the pick and how often it held over {a.runs} seeded runs per noise level.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
