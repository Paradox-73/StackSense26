"""Run scenarios through the engine and print compact summaries.

Run from any folder with the project's venv python:
    python tools/run_scenarios.py --all-presets
    ... run_scenarios.py --file tests/scenarios_extra/consumer.json
    ... run_scenarios.py --file my_scenarios.json            # [{"name": "...", "input": {...}}, ...]
    ... run_scenarios.py --file my_scenarios.json --cf       # include counterfactuals
    ... run_scenarios.py --preset content_site --full        # full Markdown export (what a user/judge reads)
    ... run_scenarios.py --file s.json --json-out out.json   # save full JSON results
Inputs may be any subset of the 26 answers in data/questions.json; missing answers get defaults.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import recommend  # noqa: E402
from engine.export import to_markdown  # noqa: E402
from engine.kb import LAYERS, load_presets  # noqa: E402


def short(s, n=170):
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def summarise(name, inp, r, secs):
    out = []
    out.append(f"\n=== {name}  (engine {secs*1000:.0f} ms) ===")
    p = r.get("profile", {})
    d = r.get("derived", {})
    out.append(
        "INPUT: " + short(json.dumps({k: v for k, v in inp.items() if k != "project_name"}, ensure_ascii=False), 600)
    )
    out.append(
        f"DERIVED: tier={d.get('tier_label')} db_tier={d.get('db_tier_label')} peak_rps={d.get('peak_rps')} "
        f"budget_usd={d.get('budget_usd')} data_12mo_gb={d.get('data_12mo_gb')} mobile={d.get('mobile')} web={d.get('web')}"
    )
    if not r.get("feasible"):
        out.append("INFEASIBLE")
    out.append(f"STACK SCORE: {r.get('stack_score')}   ARCH: {short((r.get('architecture') or {}).get('style'), 120)}")
    for layer in LAYERS:
        L = r["stack"].get(layer) if r.get("stack") else None
        if not L:
            out.append(f"  {layer:9}: (none)")
            continue
        pk = L["pick"]
        ex = L.get("explanation", {}) or {}
        vr = ex.get("vs_runner_up") or {}
        out.append(
            f"  {layer:9}: {pk['name']}  score={pk.get('score')}  conf={ex.get('confidence')}  "
            f"runner-up={vr.get('runner_up')} margin={vr.get('margin')} tie={vr.get('tie')}"
        )
        if L.get("managed_offering"):
            out.append(f"             managed: {short(L['managed_offering'], 120)}")
        for w in (ex.get("why") or [])[:2]:
            out.append(f"             why: {short(w)}")
        for rk in (ex.get("risks") or [])[:2]:
            out.append(f"             risk: {short(rk)}")
        if pk.get("adjustments"):
            out.append(f"             adj: {short(json.dumps(pk['adjustments'], ensure_ascii=False), 220)}")
        exc = L.get("excluded") or []
        if exc:
            out.append(f"             excluded {len(exc)}: " + short("; ".join(f"{e['name']} ({'/'.join(e.get('constraints', []))})" for e in exc), 260))
    comp = r.get("companion")
    if comp:
        out.append(f"COMPANION: {short(json.dumps(comp, ensure_ascii=False), 200)}")
    ss = r.get("supporting_services") or []
    if ss:
        out.append("SUPPORTING: " + short("; ".join(f"{s.get('role')}: {s.get('name')}" for s in ss), 600))
    c = r.get("cost") or {}
    out.append(f"COST: ${c.get('total_low')}-{c.get('total_high')}/mo  status={c.get('status')}  budget_usd={c.get('budget_usd')}")
    for w in r.get("warnings") or []:
        out.append(f"WARN [{w.get('severity')}] {w.get('code')}: {short(w.get('title'), 90)} -> {short(w.get('resolution'), 140)}")
    if r.get("relaxed_layers"):
        out.append(f"RELAXED: {short(json.dumps(r['relaxed_layers'], ensure_ascii=False), 300)}")
    if r.get("tie_break"):
        out.append(f"TIE-BREAK: {short(json.dumps(r['tie_break'], ensure_ascii=False), 300)}")
    for a in (r.get("assumptions") or [])[:6]:
        out.append(f"ASSUME {a.get('field')}={short(a.get('value'), 40)}: {short(a.get('reason'), 120)}")
    for cf in r.get("counterfactuals") or []:
        eff = "; ".join(f"{e['layer']}: {e['from']} -> {e['to']}" for e in cf.get("effects", []))
        out.append(f"CF {cf.get('change')}: {short(eff, 260)}")
    out.append("SUMMARY: " + short(r.get("summary"), 500))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--preset")
    ap.add_argument("--all-presets", action="store_true")
    ap.add_argument("--cf", action="store_true", help="include counterfactual re-runs")
    ap.add_argument("--full", action="store_true", help="print the full Markdown export instead of the summary")
    ap.add_argument("--json-out")
    a = ap.parse_args()
    # Resolve user paths against the caller's folder before switching to the project root.
    if a.file:
        a.file = os.path.abspath(a.file)
    if a.json_out:
        a.json_out = os.path.abspath(a.json_out)
    os.chdir(ROOT)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    presets = {x["id"]: x for x in load_presets()}
    items = []
    if a.all_presets:
        items += [(pid, x["input"]) for pid, x in presets.items()]
    if a.preset:
        items.append((a.preset, presets[a.preset]["input"]))
    if a.file:
        with open(a.file, encoding="utf-8") as fh:
            items += [(s["name"], s["input"]) for s in json.load(fh)]
    if not items:
        ap.print_help()
        return 1
    saved = {}
    for name, inp in items:
        t = time.perf_counter()
        try:
            r = recommend(inp, with_counterfactuals=a.cf or a.full)
        except Exception as e:  # report crashes as findings, keep going
            print(f"\n=== {name} ===\nCRASH: {type(e).__name__}: {e}")
            continue
        secs = time.perf_counter() - t
        saved[name] = r
        print(to_markdown(r) if a.full else summarise(name, inp, r, secs))
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(saved, fh, indent=1, ensure_ascii=False, default=str)
        print(f"\n[saved full JSON for {len(saved)} scenario(s) to {a.json_out}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
