"""Try to break it: run thousands of seeded random projects and check rules that must always hold.

    python tools/fuzz.py                          # 10,000 profiles, seed 2026, growth rule on 1,000
    python tools/fuzz.py --seed 7 --n 500 --growth-n 100
    python tools/fuzz.py --json-out violations.json

The checker reads the knowledge base JSON files in data/kb/ directly and does not reuse the engine's
filters, so a bug in a filter cannot hide itself. Profiles come from tools/profiles.py (values drawn
from data/questions.json) plus small edits of the presets. Exit code 1 if any rule is violated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter
from copy import deepcopy
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from engine import recommend  # noqa: E402
from profiles import random_input, INR_PER_USD  # noqa: E402

LAYERS = ["frontend", "backend", "database", "hosting"]
RESIDENCY = {"data_residency_india": "india", "data_residency_eu": "europe"}
REORDERABLE = ["platforms", "regions", "team_skills", "compliance"]  # data_shapes is ordered (first = primary)
GROWTH_DAU = [100, 300, 1_000, 3_000, 10_000, 30_000, 100_000, 300_000, 1_000_000, 3_000_000, 10_000_000]


def _load_kb() -> dict[str, dict]:
    items = {}
    for p in sorted((ROOT / "data" / "kb").glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "id" in v[0]:
                for it in v:
                    items[it["id"]] = it
    return items


KB = _load_kb()
RULES = {
    "hipaa_baa": "HIPAA project: host, BaaS and managed-only database all offer a BAA",
    "pci_host": "PCI DSS project: host and managed-only database are PCI DSS attested",
    "residency_region": "Data-residency project: host, BaaS and managed-only database have that region",
    "on_prem": "On-prem project: on-prem host, no FaaS or cloud-only BaaS, no managed-only database",
    "mobile_frontend": "Mobile-only project (no web platform) gets a mobile frontend",
    "strong_consistency": "Strong consistency never gets an eventually consistent primary database (unless all data is analytical or search, or the stated or app-type main shape is and consistency was not answered)",
    "worker_host": "Work that needs long-running processes (user-submitted code, jobs over 15 minutes, GPU work) gets a host that runs them, with GPUs for GPU work",
    "same_input_same_hash": "The same input twice gives byte-identical output",
    "rename_invariant": "Renaming the project changes nothing",
    "reorder_invariant": "Reordering unordered lists (platforms, regions, skills, compliance) changes nothing",
    "inr_rate_invariant": "A USD budget and the same budget in INR at the planning rate give the same stack",
    "relaxed_warned": "Every relaxed layer has a RELAXED_CONSTRAINT warning",
    "no_exception": "The engine never raises and a feasible result has all four picks",
    "no_flip_back": "As daily users grow, no layer returns to a pick it had already left",
}


def _run(inp: dict) -> dict:
    return recommend(deepcopy(inp), with_counterfactuals=False)


def _hash(r: dict) -> str:
    return hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()


def _picks(r: dict) -> dict | None:
    if not r.get("feasible"):
        return None
    return {l: r["stack"][l]["pick"]["id"] for l in LAYERS}


def _same_decision(a: dict, b: dict) -> bool:
    return _picks(a) == _picks(b) and a.get("feasible") == b.get("feasible")


def constraint_violations(inp: dict, r: dict) -> dict[str, list[str]]:
    """Hard-constraint rules, checked against raw KB facts. Returns {rule: [message, ...]}."""
    out: dict[str, list[str]] = {}

    def bad(rule: str, msg: str) -> None:
        out.setdefault(rule, []).append(msg)

    p = r["profile"]
    picks = _picks(r)
    if picks is None:
        return out
    it = {l: KB[picks[l]] for l in LAYERS}
    comp = set(p.get("compliance") or [])
    host, be, db, fe = it["hosting"], it["backend"], it["database"], it["frontend"]
    is_baas = be.get("kind") == "baas"
    if "hipaa" in comp:
        if not (host.get("compliance") or {}).get("hipaa"):
            bad("hipaa_baa", f"host {host['id']} has no BAA")
        if is_baas and not (be.get("compliance") or {}).get("hipaa"):
            bad("hipaa_baa", f"BaaS {be['id']} has no BAA")
        if db.get("managed_only") and not (db.get("compliance") or {}).get("hipaa"):
            bad("hipaa_baa", f"managed database {db['id']} has no BAA")
    if "pci_dss" in comp:
        if not (host.get("compliance") or {}).get("pci"):
            bad("pci_host", f"host {host['id']} is not PCI DSS attested")
        if db.get("managed_only") and not (db.get("compliance") or {}).get("pci"):
            bad("pci_host", f"managed database {db['id']} is not PCI DSS attested")
    for flag, region in RESIDENCY.items():
        if flag in comp:
            if region not in (host.get("regions") or []):
                bad("residency_region", f"host {host['id']} has no {region} region")
            if is_baas and region not in (be.get("regions") or []):
                bad("residency_region", f"BaaS {be['id']} has no {region} region")
            if db.get("managed_only") and region not in (db.get("regions") or []):
                bad("residency_region", f"managed database {db['id']} has no {region} region")
    if p.get("deployment") == "on_prem":
        if not host.get("on_prem"):
            bad("on_prem", f"host {host['id']} is not on-prem")
        if be.get("kind") == "faas" or (is_baas and not be.get("self_hostable")):
            bad("on_prem", f"backend {be['id']} cannot run on-prem")
        if db.get("managed_only"):
            bad("on_prem", f"database {db['id']} is cloud-only")
    needs_workers = "user_code" in (p.get("special_workloads") or []) or p.get("background_work") in ("long", "gpu")
    if needs_workers and not (host.get("runs") or {}).get("long_running"):
        bad("worker_host", f"host {host['id']} runs no long-running workers")
    if p.get("background_work") == "gpu" and not (host.get("runs") or {}).get("gpu"):
        bad("worker_host", f"host {host['id']} has no GPUs")
    plats = set(p.get("platforms") or [])
    if plats and "web" not in plats and fe.get("kind") != "mobile":
        bad("mobile_frontend", f"frontend {fe['id']} for platforms {sorted(plats)}")
    # Analytical data and a search index are read in bulk or through an index, not records that a transaction
    # must protect, so a project whose only data shapes are these has no system of record for strong consistency to bind.
    # An unanswered consistency question does not bind when the stated (or app-type default) main shape is analytical or search: the
    # project may keep that data in a store built for it, with its records in a secondary store.
    shapes = p.get("data_shapes") or ["relational"]
    records = [s for s in shapes if s not in ("analytical", "search")]
    defaulted = set((r.get("derived") or {}).get("defaulted") or [])
    app_set = set((r.get("derived") or {}).get("app_defaulted") or [])
    stated = "data_shapes" not in defaulted or "data_shapes" in app_set  # stated, or set by the app type's own default
    binds = not ("consistency" in defaulted and stated and shapes[0] in ("analytical", "search"))
    if p.get("consistency") == "strong" and db.get("consistency") == "eventual" and records and binds:
        bad("strong_consistency", f"database {db['id']} is eventually consistent")
    warned = {f for w in r.get("warnings", []) if w.get("code") == "RELAXED_CONSTRAINT" for f in w.get("fields", [])}
    for layer in (r.get("relaxed_layers") or {}):
        if layer not in warned:
            bad("relaxed_warned", f"{layer} relaxed without a warning")
    return out


def check_profile(inp: dict) -> dict[str, list[str]]:
    """All single-profile rules (everything except no_flip_back)."""
    try:
        r = _run(inp)
    except Exception as e:  # noqa: BLE001 - any crash is a finding
        return {"no_exception": [f"{type(e).__name__}: {e}"]}
    out = constraint_violations(inp, r)
    if r.get("feasible") and any(not r["stack"].get(l) for l in LAYERS):
        out.setdefault("no_exception", []).append("feasible result is missing a layer")
    if _hash(_run(inp)) != _hash(r):
        out.setdefault("same_input_same_hash", []).append("two runs differ")
    renamed = dict(inp, project_name=(inp.get("project_name") or "") + " (renamed)")
    if not _same_decision(_run(renamed), r):
        out.setdefault("rename_invariant", []).append(f"{_picks(r)} -> {_picks(_run(renamed))}")
    reordered = deepcopy(inp)
    changed = False
    for k in REORDERABLE:
        if isinstance(reordered.get(k), list) and len(reordered[k]) > 1:
            reordered[k] = list(reversed(reordered[k]))
            changed = True
    if changed:
        r2 = _run(reordered)
        if not _same_decision(r2, r):
            out.setdefault("reorder_invariant", []).append(f"{_picks(r)} -> {_picks(r2)}")
    if inp.get("currency", "USD") == "USD" and isinstance(inp.get("budget_monthly"), (int, float)):
        inr = dict(inp, currency="INR", budget_monthly=inp["budget_monthly"] * INR_PER_USD)
        r3 = _run(inr)
        if not _same_decision(r3, r):
            out.setdefault("inr_rate_invariant", []).append(f"{_picks(r)} -> {_picks(r3)}")
    return out


def check_growth(inp: dict) -> dict[str, list[str]]:
    """no_flip_back: walk daily users up a ladder; a layer may change, but never back to an earlier pick."""
    base = {k: v for k, v in inp.items() if k != "peak_rps"}  # let peak load follow the users
    seq = []
    for dau in GROWTH_DAU:
        r = _run(dict(base, dau=dau))
        seq.append(_picks(r))
    out: dict[str, list[str]] = {}
    for l in LAYERS:
        path = [s[l] for s in seq if s]
        left: set[str] = set()
        for prev, cur in zip(path, path[1:]):
            if cur != prev:
                left.add(prev)
                if cur in left:
                    out.setdefault("no_flip_back", []).append(f"{l}: " + " -> ".join(_dedupe(path)))
                    break
    return out


def _dedupe(path: list[str]) -> list[str]:
    return [x for i, x in enumerate(path) if i == 0 or x != path[i - 1]]


def preset_variants(rng: random.Random) -> list[dict]:
    """Small edits of every preset: one answer re-drawn at random."""
    from engine.kb import load_presets
    out = []
    for p in load_presets():
        for _ in range(5):
            v = deepcopy(p["input"])
            donor = random_input(rng, omit_p=0)
            k = rng.choice([k for k in donor if k != "project_name"])
            v[k] = donor[k]
            if k == "budget_monthly" and v.get("currency") == "INR" and donor.get("currency") != "INR":
                v[k] = donor[k] * INR_PER_USD
            out.append(v)
    return out


def build_profiles(seed: int, n: int) -> list[dict]:
    rng = random.Random(seed)
    variants = preset_variants(rng)
    return (variants + [random_input(rng) for _ in range(max(0, n - len(variants)))])[:n]


def _job(args):
    kind, i, inp = args
    return kind, i, (check_profile(inp) if kind == "profile" else check_growth(inp))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--n", type=int, default=10_000)
    ap.add_argument("--growth-n", type=int, default=1_000, help="profiles walked up the users ladder")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--json-out", help="save every violation with its input")
    ap.add_argument("--summary-out", help="save the counts per rule (used by the report: report/fuzz_summary.json)")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    profiles = build_profiles(a.seed, a.n)
    growth = build_profiles(a.seed + 1, a.growth_n)
    jobs = [("profile", i, x) for i, x in enumerate(profiles)] + [("growth", i, x) for i, x in enumerate(growth)]
    t0 = time.time()
    counts, examples, saved = Counter(), {}, []
    with Pool(a.workers) as pool:
        for done, (kind, i, res) in enumerate(pool.imap_unordered(_job, jobs, chunksize=8), 1):
            src = profiles[i] if kind == "profile" else growth[i]
            for rule, msgs in res.items():
                counts[rule] += 1
                examples.setdefault(rule, (msgs[0], src))
                saved.append({"rule": rule, "messages": msgs, "input": src})
            if done % 1000 == 0:
                print(f"  {done:,}/{len(jobs):,} checked, {sum(counts.values())} violations", flush=True)
    secs = time.time() - t0
    print(f"\n{len(profiles):,} projects / {len(RULES)} rules / seed {a.seed} "
          f"(growth rule on {len(growth):,}) in {secs:.0f} s")
    for rule, text in RULES.items():
        print(f"  {counts[rule]:6,}  {rule:22} {text}")
        if rule in examples:
            msg, src = examples[rule]
            print(f"          e.g. {msg}")
    total = sum(counts.values())
    print(f"\n{total} violations")
    if a.summary_out:
        Path(a.summary_out).write_text(json.dumps({
            "seed": a.seed, "projects": len(profiles), "growth_projects": len(growth), "rules": len(RULES),
            "violations": {r: counts[r] for r in RULES}, "total_violations": total,
        }, indent=1) + "\n", encoding="utf-8")
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(saved, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"saved to {a.json_out}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
