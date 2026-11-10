"""Question-influence study: how often does changing one answer change the recommended stack?

For each base project (the built-in presets, optionally plus seeded random projects) and each
question, the engine is re-run with every other value of that one question while all other answers
stay fixed. A run counts as "changed the stack" when at least one of the four layer picks differs
from the base run. Runs where the picks stay the same but the full monthly cost estimate (the four picks
plus supporting services such as video, maps or SMS) moves by more than 10% or the set of warnings
changes are counted separately.

    python tools/question_influence.py --presets                  # 14 presets, about 1 minute
    python tools/question_influence.py --random 1000 --seed 2026  # plus 1,000 random projects
    ... add --write to save report/question_influence.{json,md,svg}

Caveats stated in the output: team skills and platforms are varied as whole sets, which inflates
their rate compared with a single yes/no answer; budget values are in dollars (converted to rupees
for INR bases). The numbers depend on the base projects, so the sample is part of the result.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine.recommender import recommend as full_recommend  # noqa: E402
from engine.kb import LAYERS, field_specs, load_presets  # noqa: E402
from engine.sensitivity import options_for  # noqa: E402

SPECS = field_specs()
QUESTIONS = [k for k, s in SPECS.items() if k != "project_name" and options_for(k, s)]
COST_MOVE = 0.10
OUT_DIR = os.path.join(ROOT, "report")


def recommend(raw: dict) -> dict:
    """The engine's full recommendation without the what-if scenarios (they do not change the picks): the four
    picks, the full minimum monthly cost (the four picks plus every supporting service, with usage-billed lines
    such as video minutes, map loads and SMS) and the warning codes of the full output. Counting only the four
    picks' bill would hide answers such as special workloads, whose effect is the services they add."""
    r = full_recommend(dict(raw), with_counterfactuals=False)
    if not r.get("feasible"):
        return {"picks": {}, "cost": 0.0, "warnings": sorted({w["code"] for w in r["warnings"]})}
    return {"picks": {l: r["stack"][l]["pick"]["id"] for l in LAYERS}, "cost": r["cost"]["total_low"],
            "warnings": sorted({w["code"] for w in r["warnings"]})}


def _summary(r: dict) -> dict:
    return r


def _same_value(a, b) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return sorted(map(str, a)) == sorted(map(str, b))
    return a == b


def study_base(base: dict) -> dict:
    """{question: {runs, picks, cost_or_warnings, layers: {layer: n}}} for one base project."""
    ref = _summary(recommend(base))
    cur = base.get("currency", "USD")
    out = {}
    for key in QUESTIONS:
        runs = picks = soft = 0
        layers = dict.fromkeys(LAYERS, 0)
        for _, value in options_for(key, SPECS[key], cur):
            if _same_value(base.get(key), value):
                continue
            inp = dict(base)
            if value is None:
                inp.pop(key, None)
            else:
                inp[key] = value
            s = _summary(recommend(inp))
            runs += 1
            changed = [l for l in LAYERS if s["picks"].get(l) != ref["picks"].get(l)]
            if changed:
                picks += 1
                for l in changed:
                    layers[l] += 1
            else:
                moved = abs(s["cost"] - ref["cost"]) > COST_MOVE * max(ref["cost"], 1.0)
                if moved or s["warnings"] != ref["warnings"]:
                    soft += 1
        out[key] = {"runs": runs, "picks": picks, "cost_or_warnings": soft, "layers": layers}
    return out


def aggregate(per_base: list[dict]) -> list[dict]:
    rows = []
    for key in QUESTIONS:
        runs = sum(b[key]["runs"] for b in per_base)
        picks = sum(b[key]["picks"] for b in per_base)
        soft = sum(b[key]["cost_or_warnings"] for b in per_base)
        layers = {l: sum(b[key]["layers"][l] for b in per_base) for l in LAYERS}
        bases_moved = sum(1 for b in per_base if b[key]["picks"] > 0)
        rows.append({
            "key": key, "label": SPECS[key]["label"], "runs": runs,
            "pick_change_rate": picks / runs if runs else 0.0,
            "cost_or_warning_only_rate": soft / runs if runs else 0.0,
            "any_effect_rate": (picks + soft) / runs if runs else 0.0,
            "bases_moved_share": bases_moved / len(per_base),
            "layer_rates": {l: layers[l] / runs if runs else 0.0 for l in LAYERS},
        })
    rows.sort(key=lambda r: (-r["pick_change_rate"], -r["any_effect_rate"], r["key"]))
    return rows


def _preset_bases():
    return [dict(p["input"]) for p in load_presets()]


def run(n_random: int, seed: int, workers: int):
    bases = _preset_bases()
    n_presets = len(bases)
    if n_random:
        from profiles import profiles
        bases += profiles(seed, n_random)
    t = time.time()
    if workers > 1 and len(bases) > 4:
        with Pool(workers) as pool:
            per_base = pool.map(study_base, bases, chunksize=2)
    else:
        per_base = [study_base(b) for b in bases]
    return {
        "bases": {"presets": n_presets, "random": n_random, "seed": seed},
        "engine_runs": sum(v["runs"] for b in per_base for v in b.values()),
        "seconds": round(time.time() - t, 1),
        "all": aggregate(per_base),
        "presets_only": aggregate(per_base[:n_presets]),
        "random_only": aggregate(per_base[n_presets:]) if n_random else [],
    }


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def table(rows: list[dict]) -> str:
    out = ["| Question | Changed a pick | Changed only cost or warnings | Projects where it changed a pick | Frontend | Backend | Database | Hosting |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lr = r["layer_rates"]
        out.append(f"| {r['label']} | {pct(r['pick_change_rate'])} | {pct(r['cost_or_warning_only_rate'])} | {pct(r['bases_moved_share'])} | "
                   + " | ".join(pct(lr[l]) for l in LAYERS) + " |")
    return "\n".join(out)


def svg_chart(rows: list[dict], title: str) -> str:
    row_h, left, width, top = 22, 230, 760, 54
    h = top + row_h * len(rows) + 40
    bar_w = width - left - 70
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {h}" role="img" aria-label="{title}" font-family="system-ui, sans-serif" font-size="12">',
             '<style>.t{fill:#1f2937}.m{fill:#6b7280}.p{fill:#2563eb}.s{fill:#93c5fd}@media (prefers-color-scheme: dark){.t{fill:#e5e7eb}.m{fill:#9ca3af}.p{fill:#60a5fa}.s{fill:#1e3a8a}}</style>',
             f'<text x="12" y="20" class="t" font-size="14" font-weight="600">{title}</text>',
             f'<rect x="{left}" y="32" width="10" height="10" class="p"/><text x="{left + 16}" y="41" class="m">changed at least one pick</text>',
             f'<rect x="{left + 190}" y="32" width="10" height="10" class="s"/><text x="{left + 206}" y="41" class="m">changed only cost or warnings</text>']
    for i, r in enumerate(rows):
        y = top + i * row_h
        w1 = bar_w * r["pick_change_rate"]
        w2 = bar_w * r["cost_or_warning_only_rate"]
        parts.append(f'<text x="{left - 8}" y="{y + 13}" text-anchor="end" class="t">{html.escape(r["label"][:34])}</text>')
        parts.append(f'<rect x="{left}" y="{y + 2}" width="{w1:.1f}" height="14" class="p"/>')
        parts.append(f'<rect x="{left + w1:.1f}" y="{y + 2}" width="{w2:.1f}" height="14" class="s"/>')
        parts.append(f'<text x="{left + w1 + w2 + 6:.1f}" y="{y + 13}" class="m">{pct(r["pick_change_rate"])}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def markdown(res: dict) -> str:
    b = res["bases"]
    rows = res["all"]
    zero = [r for r in rows if r["pick_change_rate"] == 0]
    lines = [
        "# Question influence",
        "",
        f"Method: {b['presets']} preset projects" + (f" and {b['random']} seeded random projects (seed {b['seed']})" if b["random"] else "")
        + ". For each project and each question, the engine was re-run with every other value of that one question, all other answers held fixed "
        f"({res['engine_runs']:,} engine runs in {res['seconds']} s). A run counts as changing the stack when at least one of the four picks differs from the base run.",
        "",
        "Caveats: team skills and platforms are varied as whole sets, which inflates their rate compared with a single yes/no answer. "
        "Budget is varied from $0 to $10,000. Rates depend on the base projects, so the sample is part of the result.",
        "",
        table(rows),
        "",
    ]
    if zero:
        lines += ["Questions that never changed a pick in this sample: " + ", ".join(r["label"] for r in zero) + ".", ""]
    if res["random_only"]:
        lines += ["## Presets only", "", table(res["presets_only"]), ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--presets", action="store_true", help="presets only (fast)")
    ap.add_argument("--random", type=int, default=0, help="add N seeded random projects")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--write", action="store_true", help="write report/question_influence.{json,md,svg}")
    args = ap.parse_args()
    res = run(0 if args.presets else args.random, args.seed, args.workers)
    print(markdown(res))
    if args.write:
        with open(os.path.join(OUT_DIR, "question_influence.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, sort_keys=True)
        with open(os.path.join(OUT_DIR, "question_influence.md"), "w", encoding="utf-8") as f:
            f.write(markdown(res))
        label = "How often one answer changes the stack"
        with open(os.path.join(OUT_DIR, "question_influence.svg"), "w", encoding="utf-8") as f:
            f.write(svg_chart(res["all"], label))
        print(f"\nwrote report/question_influence.json, .md, .svg ({res['seconds']} s)", file=sys.stderr)


if __name__ == "__main__":
    main()
