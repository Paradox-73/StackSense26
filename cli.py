"""Command-line access to the engine.

    python cli.py --list                 # list presets
    python cli.py --preset startup_mvp   # print Markdown report for a preset
    python cli.py --input my.json --json # JSON output for a custom input file
    python cli.py --all                  # one-line summary for every preset
    python cli.py --preset hipaa_telehealth --adr   # one decision record per layer
    python cli.py --scenario scenarios/public/P2.json                    # standard scenario file -> output JSON
    python cli.py --scenario scenarios/public --out outputs --no-llm     # every file in a folder -> outputs/<id>_output.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from engine import recommend
from engine.export import to_adr, to_markdown
from engine.kb import LAYERS, load_presets


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="StackSense tech-stack recommender")
    ap.add_argument("--preset")
    ap.add_argument("--input")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--adr", action="store_true", help="print architecture decision records instead of the report")
    ap.add_argument("--scenario", help="a scenario file in the standard schema (problem statement section 3.2), or a "
                                       "folder of them")
    ap.add_argument("--out", help="with --scenario: an output file, or a folder for <scenario_id>_output.json files; "
                                  "without it the output JSON is printed")
    ap.add_argument("--no-llm", action="store_true", help="switch every language-model feature off (STACKSENSE_LLM=off)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.no_llm:
        os.environ["STACKSENSE_LLM"] = "off"
    if a.scenario:
        return run_scenarios(Path(a.scenario), a.out)
    presets = {x["id"]: x for x in load_presets()}
    if a.list:
        for pid, x in presets.items():
            print(f"{pid:24} {x['name']}")
        return 0
    if a.all:
        for pid, x in presets.items():
            r = recommend(x["input"], with_counterfactuals=False)
            if not r["feasible"]:
                print(f"{pid:24} INFEASIBLE")
                continue
            picks = " | ".join(f"{r['stack'][l]['pick']['name']}" for l in LAYERS)
            crit = sum(1 for w in r["warnings"] if w["severity"] == "critical")
            print(f"{pid:24} {r['stack_score']:6.1f}  {picks}  [${r['cost']['total_low']:,.0f}-{r['cost']['total_high']:,.0f}] crit={crit}")
        return 0
    if a.preset:
        data = presets[a.preset]["input"]
    elif a.input:
        with open(a.input, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        ap.print_help()
        return 1
    r = recommend(data)
    print(json.dumps(r, indent=2, ensure_ascii=False, default=str) if a.json else to_adr(r) if a.adr else to_markdown(r))
    return 0


def run_scenarios(src: Path, out: str | None) -> int:
    """Run each standard scenario file and write (or print) its section 4 output JSON."""
    from engine.standard import run_text
    files = sorted(src.glob("*.json")) if src.is_dir() else [src] if src.is_file() else []
    if not files:
        print(f"no scenario files found at {src}", file=sys.stderr)
        return 1
    folder = out and (len(files) > 1 or src.is_dir() or not out.lower().endswith(".json"))
    for f in files:
        result = run_text(f.read_text(encoding="utf-8-sig"))
        text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if not out:
            sys.stdout.write(text)
            continue
        sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(result.get("scenario_id") or f.stem))
        dest = Path(out) / f"{sid}_output.json" if folder else Path(out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        picks = " | ".join(result["stack"][l]["choice"] for l in LAYERS) if result.get("stack") else "no stack"
        print(f"{sid:10} {result['status']:17} {picks}  -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
