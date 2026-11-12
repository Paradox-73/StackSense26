"""LLM-only baseline for the benchmark: ask a language model for the four picks of each brief, with no rule engine.

    python tools/llm_baseline.py                  # answer every brief not yet in benchmark/llm_baseline.json
    python tools/llm_baseline.py --limit 10       # stop after 10 new briefs (the free tier allows about 50 requests a day)
    python tools/llm_baseline.py --grade          # (re)grade every saved stack with the current rule engine, no network, saved to the file
    python tools/llm_baseline.py --show           # print every metric, no network
    python tools/llm_baseline.py --repeat         # ask the same briefs again (cache bypassed) into llm_baseline_repeat.json
    python tools/llm_baseline.py --repeat --limit 25

The model sees only the brief text and the list of technologies the knowledge base knows, and answers with one
technology id per layer. Picks are scored with the same rule as tools/bench.py (top-1 = the key's best pick,
acceptable = any pick at least 2 of 3 labeller personas accept). The file is written after every brief and briefs already
in it are skipped, so an interrupted or rate-limited run continues where it stopped. Answers are also saved in
benchmark/llm_baseline_cache/, so a repeated run costs no requests. Needs STACKSENSE_LLM_API_KEY or OPENROUTER_API_KEY (see README).

Agreement with the key is not the only measure. Each saved stack is also graded by the rule engine (offline, with
baseline_grading.grade_stack): hard requirements the stack breaks, minimum monthly cost against the engine's,
over-budget (INR budgets converted at the engine's own rate), and the engine's score gap. The engine's own stack is
graded the same way as a self-check. --repeat measures how often the model gives the same stack twice.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import bench  # noqa: E402
from engine import llm  # noqa: E402
from engine.kb import LAYERS  # noqa: E402
from baseline_grading import (SYSTEM_PROMPT, allowed_options, build_messages, engine_pick_ids,  # noqa: E402,F401
                              grade_stack, read_picks)

OUT_PATH = os.path.join(ROOT, "benchmark", "llm_baseline.json")
REPEAT_PATH = os.path.join(ROOT, "benchmark", "llm_baseline_repeat.json")
# This experiment asks the model for a stack, which the engine never does, so its saved answers live here and not in
# data/llm_cache/ (the engine's own description reader and summary).
CACHE_DIR = os.path.join(ROOT, "benchmark", "llm_baseline_cache")


def score_picks(brief: dict, picks: dict[str, str | None]) -> dict:
    """Score picks with bench.py's rule. An invalid pick counts as a miss."""
    got = {}
    for layer, pick in picks.items():
        ids = {pick or "invalid"}  # an invalid pick matches nothing in the key
        if pick in bench.NONE_IDS:
            ids.add("none")
        got[layer] = ids
    row = bench.score_ids(brief, got)
    for layer in LAYERS:
        row["layers"][layer]["pick"] = picks[layer]
    return row


def load_saved(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"description": __doc__.split("\n")[0], "briefs": {}}


GRADE_KEYS = ("ok", "complete", "breaks", "gap", "cost_low", "engine_cost_low", "cost_diff", "budget_usd", "over_budget", "over_by")


def _compact(g: dict) -> dict:
    return {k: g[k] for k in GRADE_KEYS if k in g} if g.get("ok") else {"ok": False, "error": g.get("error")}


def grade_row(brief: dict, row: dict, engine_ids: dict | None = None) -> None:
    """Add the engine's grade of the model's stack (row["grade"]) and of the engine's own stack (row["engine_grade"])."""
    picks = {layer: row["layers"][layer]["pick"] for layer in LAYERS}
    row["grade"] = _compact(grade_stack(brief["input"], picks))
    engine_ids = engine_ids or engine_pick_ids(brief["input"])
    row["engine_picks"] = engine_ids
    row["engine_grade"] = _compact(grade_stack(brief["input"], engine_ids))


def grade_all(saved: dict, out=print, force: bool = False) -> int:
    """Grade every answered brief that has no grade yet (every brief with force=True, since a rule change makes
    old grades stale). Offline. Returns how many were graded."""
    key = {b["id"]: b for b in bench.load_key()["briefs"]}
    n = 0
    for bid, row in saved["briefs"].items():
        if not force and "grade" in row and "engine_grade" in row:
            continue
        grade_row(key[bid], row)
        n += 1
        out(f"graded {bid}")
    saved["metrics"] = metrics(saved)
    return n


def _median(values: list[float]) -> float | None:
    v = sorted(values)
    return round((v[len(v) // 2] + v[(len(v) - 1) // 2]) / 2, 2) if v else None


def metrics(saved: dict) -> dict:
    """Hard-requirement breaks, over-budget, cost and score gap over the graded briefs, for the model and for the engine."""
    rows = [(bid, r) for bid, r in saved["briefs"].items() if r.get("grade", {}).get("ok")]
    out: dict = {"graded": len(rows)}
    if not rows:
        return out
    broken = [(bid, r["grade"]["breaks"]) for bid, r in rows if r["grade"]["breaks"]]
    per_layer = {l: sum(1 for _, b in broken if l in b) for l in LAYERS}
    complete = [r for _, r in rows if r["grade"]["complete"]]
    egrades = [r["engine_grade"] for _, r in rows if r.get("engine_grade", {}).get("ok")]
    cheaper = sum(1 for r in complete if r["grade"]["cost_diff"] < 0)
    out |= {
        "llm_breaks": {"briefs": len(broken), "by_layer": per_layer,
                       "cases": [{"id": bid, "layer": l, "pick": saved["briefs"][bid]["layers"][l]["pick"], "reasons": rs}
                                 for bid, b in broken for l, rs in b.items()]},
        "llm_over_budget": sum(1 for _, r in rows if r["grade"]["over_budget"]),
        "llm_complete": len(complete),
        "llm_cost_diff_mean": round(sum(r["grade"]["cost_diff"] for r in complete) / len(complete), 2) if complete else None,
        "llm_cost_diff_median": _median([r["grade"]["cost_diff"] for r in complete]),
        "llm_cheaper_than_engine": cheaper,
        "llm_over_budget_engine_fits": sum(1 for _, r in rows if r["grade"]["over_budget"] and not r["engine_grade"].get("over_budget", True)),
        "llm_gap_mean": round(sum(r["grade"]["gap"] for r in complete) / len(complete), 2) if complete else None,
        "llm_gap_max": max((r["grade"]["gap"] for r in complete), default=None),
        "llm_same_stack_as_engine": sum(1 for _, r in rows if all(r["layers"][l]["pick"] == r["engine_picks"][l] for l in LAYERS)),
        "engine_check": {"graded": len(egrades), "breaks": sum(1 for g in egrades if g["breaks"]),
                         "over_budget": sum(1 for g in egrades if g["over_budget"]),
                         "max_abs_gap": max((abs(g["gap"]) for g in egrades), default=None)},
    }
    return out


def save(path: str, saved: dict) -> None:
    """Write the result file (briefs in key order, then the hit rates over all briefs done so far)."""
    rows = list(saved["briefs"].values())
    saved["done"] = len(rows)
    saved["rates"] = bench.split_rates(rows) if rows else {}
    if any("grade" in r for r in rows):
        saved["metrics"] = metrics(saved)
    _write(path, saved)


def _write(path: str, saved: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def run(path: str = OUT_PATH, limit: int | None = None, out=print) -> dict:
    """Answer the briefs that are not in the file yet. Stops at `limit` new briefs or when no model answers."""
    key = bench.load_key()
    options = allowed_options()
    saved = load_saved(path)
    done_now = 0
    for brief in key["briefs"]:
        if brief["id"] in saved["briefs"]:
            continue
        if limit is not None and done_now >= limit:
            break
        try:
            data, reply = llm.chat_json(build_messages(brief["brief"], options))
        except llm.LLMError as err:
            out(f"stopped at {brief['id']}: {err}. Run again later; finished briefs are kept.")
            break
        row = score_picks(brief, read_picks(data, options))
        row["model"] = reply.model
        grade_row(brief, row)
        saved["briefs"][brief["id"]] = row
        saved["models_chain"] = llm.models()
        save(path, saved)
        done_now += 1
        out(f"{brief['id']} {reply.model}{' (cached)' if reply.cached else ''}: "
            + " ".join(f"{layer[:2]}={row['layers'][layer]['pick']}" for layer in LAYERS))
    return saved


def run_repeat(path: str = REPEAT_PATH, first_path: str = OUT_PATH, limit: int | None = None, out=print) -> dict:
    """Ask the briefs of the first run again, bypassing the disk cache, and keep the new stacks in `path`.
    Resumable: briefs already in `path` are skipped. Stops at `limit` new briefs or when no model answers."""
    first = load_saved(first_path)
    options = allowed_options()
    key = {b["id"]: b for b in bench.load_key()["briefs"]}
    saved = load_saved(path)
    saved["description"] = "Second asking of the same briefs with the cache bypassed (repeatability of the LLM-only baseline)."
    done_now = 0
    for bid in first["briefs"]:
        if bid in saved["briefs"]:
            continue
        if limit is not None and done_now >= limit:
            break
        try:
            data, reply = llm.chat_json(build_messages(key[bid]["brief"], options), use_cache=False)
        except llm.LLMError as err:
            out(f"stopped at {bid}: {err}. Run again later; finished briefs are kept.")
            break
        picks = read_picks(data, options)
        saved["briefs"][bid] = {"id": bid, "model": reply.model, "picks": picks}
        saved["models_chain"] = llm.models()
        saved["done"] = len(saved["briefs"])
        _write(path, saved)
        done_now += 1
        same = all(picks[l] == first["briefs"][bid]["layers"][l]["pick"] for l in LAYERS)
        out(f"{bid} {reply.model}: {'same stack' if same else 'different stack'}")
    return saved


def repeat_metrics(first: dict, repeat: dict | None) -> dict:
    """How often the second asking gave the same stack (all four layers) and the same pick per layer."""
    repeat = repeat or {}
    ids = [b for b in repeat.get("briefs", {}) if b in first["briefs"]]
    if not ids:
        return {"asked": 0}
    def same_layer(b, l):
        return repeat["briefs"][b]["picks"][l] == first["briefs"][b]["layers"][l]["pick"]
    return {"asked": len(ids), "same_stack": sum(1 for b in ids if all(same_layer(b, l) for l in LAYERS)),
            "same_by_layer": {l: sum(1 for b in ids if same_layer(b, l)) for l in LAYERS},
            "same_model": sum(1 for b in ids if repeat["briefs"][b]["model"] == first["briefs"][b].get("model"))}


def show(saved: dict, out=print, repeat: dict | None = None) -> None:
    """Print every metric: hit rates against the key, the engine's grade of the stacks, and repeatability."""
    done = list(saved["briefs"].values())
    if not done:
        out("no briefs answered yet")
        return
    ids = {r["id"] for r in done}
    engine_rows = [r for r in bench.run() if r["id"] in ids]
    out(f"{len(done)} briefs answered by the LLM-only baseline (same briefs for both rows)")
    for name, rows in (("rule engine", engine_rows), ("LLM only", done)):
        c = bench.rates(rows)["all"]
        out(f"  {name:12} top-1 {bench.pct(c['top1']):16} acceptable {bench.pct(c['acceptable'])}")
    m = saved.get("metrics") or metrics(saved)
    if not m.get("graded"):
        out("not graded yet: run with --grade")
    else:
        b = m["llm_breaks"]
        out(f"graded by the rule engine ({m['graded']} briefs)")
        out(f"  hard-requirement breaks: LLM {b['briefs']} briefs ({', '.join(f'{l} {n}' for l, n in b['by_layer'].items())}); "
            f"engine {m['engine_check']['breaks']} (graded the same way)")
        for c in b["cases"]:
            out(f"    {c['id']} {c['layer']}={c['pick']}: {'; '.join(c['reasons'])}")
        out(f"  over budget (INR converted at the engine's rate): LLM {m['llm_over_budget']}, engine {m['engine_check']['over_budget']}; "
            f"over budget where the engine's own stack fits: {m['llm_over_budget_engine_fits']}")
        out(f"  minimum monthly cost vs the engine's stack: mean {m['llm_cost_diff_mean']:+} USD, median {m['llm_cost_diff_median']:+} USD, LLM cheaper in {m['llm_cheaper_than_engine']} of {m['llm_complete']}")
        out(f"  engine score gap (engine minus LLM stack): mean {m['llm_gap_mean']}, max {m['llm_gap_max']}")
        out(f"  same stack as the engine: {m['llm_same_stack_as_engine']} of {m['graded']}")
    r = repeat_metrics(saved, repeat)
    if not r["asked"]:
        out("repeatability: not measured yet (run --repeat)")
    else:
        out(f"repeatability: same stack twice in {r['same_stack']} of {r['asked']} briefs "
            f"(per layer: {', '.join(f'{l} {n}' for l, n in r['same_by_layer'].items())}); same model both times in {r['same_model']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, help="answer at most this many new briefs")
    ap.add_argument("--out", default=OUT_PATH, help="result file (default benchmark/llm_baseline.json)")
    ap.add_argument("--repeat-out", default=REPEAT_PATH, help="repeat file (default benchmark/llm_baseline_repeat.json)")
    ap.add_argument("--show", action="store_true", help="print every metric, make no requests")
    ap.add_argument("--grade", action="store_true", help="grade the saved stacks with the rule engine and save; no requests")
    ap.add_argument("--repeat", action="store_true", help="ask the same briefs again, cache bypassed (resumable)")
    args = ap.parse_args()
    llm.CACHE_DIR = Path(CACHE_DIR)
    if not bench.verify_hash():
        print("ANSWER KEY HASH MISMATCH: tests/benchmark/answer_key.json changed", file=sys.stderr)
        return 2
    if args.grade:
        saved = load_saved(args.out)
        grade_all(saved, force=True)
        save(args.out, saved)
    elif not args.show:
        if not llm.available():
            print("No API key: set STACKSENSE_LLM_API_KEY or OPENROUTER_API_KEY (or put it in .env).", file=sys.stderr)
            return 1
        if args.repeat:
            run_repeat(args.repeat_out, args.out, args.limit)
        else:
            run(args.out, args.limit)
    saved = load_saved(args.out)
    if args.show:
        grade_all(saved, out=lambda *_: None)  # in memory only
    show(saved, repeat=load_saved(args.repeat_out) if os.path.exists(args.repeat_out) else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
