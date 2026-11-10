"""'Not sure' support: for each answer the user marked unknown, re-run the engine across that
answer's plausible values (one field at a time, every other answer held fixed) and report, per
layer, whether the pick is ROBUST (the same for every value) or DEPENDS (which values flip it, to what).

Unknown fields are held at their documented default in the base run, exactly as the main
recommendation treats them. Total engine runs are capped so the call stays fast (~25 ms per run).
"""
from __future__ import annotations

import json
from collections import OrderedDict
from copy import deepcopy

from .kb import LAYERS, field_specs, load_kb
from .profile import INR_PER_USD
from .explain import layer_views, switch_reason
from .recommender import _core, _picks

MAX_RUNS = 48
_CACHE: OrderedDict[str, dict] = OrderedDict()
_CACHE_SIZE = 1024

# Plausible values for numeric answers, chosen to straddle the engine's own thresholds
# (scale tiers at 1k/10k/100k/1M/10M DAU, budget bands at $50/$300/$2k, team bands at 1/3/10/30).
NUMERIC_OPTIONS = {
    "dau": [100, 1000, 10000, 100000, 1000000, 10000000],
    "budget_monthly": [0, 25, 100, 500, 2000, 10000],
    "team_size": [1, 3, 6, 12, 40],
    "timeline_weeks": [4, 12, 26, 52],
    "latency_target_ms": [50, 150, 300, 1000],
    "data_volume_gb": [1, 50, 1000, 20000],
    "data_growth_gb_month": [0.1, 1, 20, 500],
    "peak_rps": [None, 50, 500, 5000],
    "peak_concurrent": [None, 100, 1000, 10000, 100000],
}
UNITS = {"dau": "users/day", "budget_monthly": "/month", "team_size": "people", "timeline_weeks": "weeks",
         "latency_target_ms": "ms", "data_volume_gb": "GB", "data_growth_gb_month": "GB/month", "peak_rps": "req/s",
         "peak_concurrent": "online at once"}

SKILL_SETS = [
    ("No relevant skills", []), ("JavaScript / TypeScript", ["javascript", "typescript", "react", "node"]),
    ("Python", ["python"]), ("Java", ["java", "spring"]), ("Go", ["go"]), ("C# / .NET", ["csharp"]), ("PHP", ["php"]),
]
PLATFORM_SETS = [("Web only", ["web"]), ("Web + iOS + Android", ["web", "ios", "android"]), ("iOS + Android only", ["ios", "android"])]


def _compact(n: float) -> str:
    a = abs(n)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if a >= div:
            v = n / div
            return f"{v:.0f}{suf}" if v == int(v) else f"{v:.1f}{suf}"
    return f"{n:g}"


def _num_label(key: str, v, currency: str) -> str:
    if v is None:
        return "not stated" if key == "peak_concurrent" else "derived from users"
    if key == "budget_monthly":
        sym = "₹" if currency == "INR" else "$"
        return f"{sym}{_compact(v)}/month" if v else f"{sym}0 (free tiers)"
    return f"{_compact(v)} {UNITS.get(key, '')}".strip()


def options_for(key: str, spec: dict, currency: str = "USD") -> list[tuple[str, object]]:
    """(label, value) pairs the engine should try for an unknown answer."""
    if key == "currency":
        # The unit the budget is written in, not a fact about the project: the same budget in rupees or dollars
        # gives the same stack (tools/fuzz.py inr_rate_invariant). Varying it alone would only re-read the number.
        return []
    t = spec["type"]
    if t == "select":
        return [(o["label"], o["value"]) for o in spec["options"]]
    if t == "bool":
        return [("No", False), ("Yes", True)]
    if t == "number":
        vals = NUMERIC_OPTIONS.get(key)
        if vals is None:
            return []
        if key == "budget_monthly" and currency == "INR":
            vals = [v * INR_PER_USD for v in vals]
        return [(_num_label(key, v, currency), v) for v in vals]
    if t == "multiselect":
        if key == "team_skills":
            return list(SKILL_SETS)
        if key == "platforms":
            return list(PLATFORM_SETS)
        if key == "compliance":
            return [("None", [])] + [(o["label"], [o["value"]]) for o in spec["options"]]
        if key == "special_workloads":
            # Grouped by what they change: most only add a service and its cost; live location raises realtime and
            # users' code needs long-running workers (engine/profile.py). The two that can move a pick come last, so
            # thinning (which keeps the first and last values) still tests them.
            labels = {o["value"]: o["label"] for o in spec["options"]}
            services = [v for v in labels if v not in ("live_location", "user_code")]
            return [("None", []), ("Uploads, video, search or SMS (adds services)", services),
                    (labels["live_location"], ["live_location"]), (labels["user_code"], ["user_code"])]
        if key in ("priorities", "existing_systems"):
            return [("None", [])] + [(o["label"], [o["value"]]) for o in spec["options"]]
        if key == "user_actions":
            return [("Read only", ["read"]), ("Read, sign in and post", ["read", "sign_in", "post"]),
                    ("Also pay", ["read", "sign_in", "post", "pay"])]
        if key == "data_shapes":
            return [(o["label"], [o["value"]]) for o in spec["options"]]
        if key == "regions":
            return [(o["label"], [o["value"]]) for o in spec["options"]]
    return []  # free text (project name) cannot change the stack


def _run_full(raw: dict) -> dict:
    """Picks plus the per-layer views needed to explain a switch (cached by answers)."""
    key = json.dumps(raw, sort_keys=True, default=str)
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return hit
    core = _core(raw)
    picks = _picks(core)
    hit = {"picks": picks, "views": layer_views(core) if picks else None}
    _CACHE[key] = hit
    if len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return hit


def _run(raw: dict) -> dict[str, str]:
    return _run_full(raw)["picks"]


def _thin(opts: list, keep: int) -> list:
    """Keep `keep` options spread evenly, always including the first and last."""
    if keep >= len(opts):
        return opts
    keep = max(2, keep)
    idx = sorted({round(i * (len(opts) - 1) / (keep - 1)) for i in range(keep)})
    return [opts[i] for i in idx]


def sensitivity(answers: dict | None, unknown: list[str] | None, max_runs: int = MAX_RUNS) -> dict:
    specs = field_specs()
    kb = load_kb()
    base_raw = deepcopy(answers or {})
    unknown = [k for k in dict.fromkeys(unknown or []) if k in specs]
    for k in unknown:  # 'Not sure' = use the documented default
        base_raw[k] = deepcopy(specs[k].get("default"))
    currency = str(base_raw.get("currency") or "USD")
    name = lambda i: kb["index"][i]["name"] if i else None  # noqa: E731

    base_full = _run_full(base_raw)
    base = base_full["picks"]
    out = {"unknown": unknown, "base": {l: name(base.get(l)) for l in LAYERS}, "feasible": bool(base),
           "fields": [], "robust_layers": [], "depends": {}, "runs": 1, "capped": False, "skipped": []}

    plans = [(k, options_for(k, specs[k], currency)) for k in unknown]
    plans = [(k, o) for k, o in plans if len(o) >= 2]
    total = sum(len(o) for _, o in plans)
    budget = max_runs - 1
    out["skipped"] = []
    if total > budget and plans:
        out["capped"] = True
        if 2 * len(plans) > budget:  # too many unknowns: test the first ones (the UI sends the most decisive first)
            out["skipped"] = [k for k, _ in plans[budget // 2:]]
            plans = plans[:budget // 2]
        per = max(2, budget // len(plans))
        plans = [(k, _thin(o, per)) for k, o in plans]

    for key, opts in plans:
        spec = specs[key]
        rows = []
        for label, value in opts:
            if out["runs"] >= max_runs:
                out["capped"] = True
                break
            raw = deepcopy(base_raw)
            raw[key] = deepcopy(value)
            full = _run_full(raw)
            picks = full["picks"]
            out["runs"] += 1
            rows.append({"label": label, "value": value, "picks": {l: picks.get(l) for l in LAYERS}, "views": full["views"],
                         "feasible": bool(picks), "is_default": value == spec.get("default")})
        layers = {}
        for l in LAYERS:
            ids = [r["picks"][l] for r in rows]
            distinct = list(dict.fromkeys(ids))
            def why(i, l=l):
                """Cause of the switch from the base pick, taken from the first tested value that gives pick i."""
                r = next(r for r in rows if r["picks"][l] == i)
                if not i or not base.get(l) or i == base[l] or not r["views"]:
                    return None
                return switch_reason(base[l], i, base_full["views"][l], r["views"][l])
            groups = [{"pick_id": i, "pick": name(i), "why": why(i),
                       "options": [{"label": r["label"], "value": r["value"]} for r in rows if r["picks"][l] == i]}
                      for i in distinct]
            segments = []
            if spec["type"] == "number":  # ordered: contiguous runs of the same pick
                for r in rows:
                    if segments and segments[-1]["pick_id"] == r["picks"][l]:
                        segments[-1]["to"] = r["value"]
                        segments[-1]["to_label"] = r["label"]
                    else:
                        segments.append({"pick_id": r["picks"][l], "pick": name(r["picks"][l]), "why": why(r["picks"][l]),
                                         "from": r["value"], "to": r["value"],
                                         "from_label": r["label"], "to_label": r["label"]})
            layers[l] = {"robust": len(distinct) <= 1, "groups": groups, "segments": segments}
        matters = [l for l in LAYERS if not layers[l]["robust"]]
        for r in rows:
            r.pop("views", None)
        out["fields"].append({"key": key, "label": spec["label"], "type": spec["type"], "ordered": spec["type"] == "number",
                              "tested": len(rows), "layers": layers, "matters": matters,
                              "infeasible_options": [r["label"] for r in rows if not r["feasible"]]})
        for l in matters:
            out["depends"].setdefault(l, []).append(key)

    out["robust_layers"] = [l for l in LAYERS if l not in out["depends"]]
    return out


# ---------------------------------------------------------------------------- "ask next"
NEXT_MAX_RUNS = 110
# Answers the app type already implies; asking them again would only repeat what the engine assumes.
IMPLIED_BY_APP = {"mobile_first": {"platforms"}, "realtime_collab": {"realtime"}, "fintech": {"consistency"},
                  "content_site": {"seo", "user_actions"}, "iot_telemetry": {"data_shapes", "read_write"},
                  "analytics_dashboard": {"data_shapes", "read_write"}}
_NEXT_CACHE: OrderedDict[str, list] = OrderedDict()


def picks_for(raw: dict) -> dict:
    """The recommended pick per layer for these answers, without the explanation."""
    return _picks(_core(raw, light=True))


def _cache_key(raw: dict) -> str:
    return json.dumps(raw, sort_keys=True, default=str)


def _remember(key: str, picks: dict) -> None:
    _NEXT_CACHE[key] = picks
    if len(_NEXT_CACHE) > _CACHE_SIZE:
        _NEXT_CACHE.popitem(last=False)


def _picks_cached(raw: dict) -> dict:
    key = _cache_key(raw)
    hit = _NEXT_CACHE.get(key)
    if hit is None:
        hit = picks_for(raw)
        _remember(key, hit)
    return hit


def _run_all(raws: list[dict], pool) -> None:
    """Fill the cache for every answer set in `raws`, over the worker pool when there is one."""
    todo = {}
    for raw in raws:
        key = _cache_key(raw)
        if key not in _NEXT_CACHE:
            todo.setdefault(key, raw)
    if pool is not None and len(todo) >= 8:
        try:
            keys = list(todo)
            size = max(1, len(keys) // (4 * getattr(pool, "_max_workers", 4)))
            for key, picks in zip(keys, pool.map(picks_for, [todo[k] for k in keys], chunksize=size)):
                _remember(key, picks)
            return
        except Exception:  # a worker died: do the rest here
            pass
    for key, raw in todo.items():
        if key not in _NEXT_CACHE:
            _remember(key, picks_for(raw))


def next_questions(answers: dict | None, pool=None) -> dict:
    """Rank the unanswered questions by how many layers one answer could still change. Each unanswered
    question is tried at its plausible values while every given answer stays fixed; a question that
    changes no layer in any run is reported as settled. `pool` (see engine/parallel.py) spreads the runs
    over worker processes; the result is the same without it."""
    specs = field_specs()
    base_raw = deepcopy(answers or {})
    currency = str(base_raw.get("currency") or "USD")
    app = str(base_raw.get("app_type") or specs["app_type"]["default"])
    locked = sorted(k for k in IMPLIED_BY_APP.get(app, ()) if k not in base_raw)
    open_keys = [k for k in specs if k != "project_name" and k not in base_raw and k not in locked]
    plans = [(k, options_for(k, specs[k], currency)) for k in open_keys]
    plans = [(k, o) for k, o in plans if len(o) >= 2]
    per = max(2, (NEXT_MAX_RUNS - 1) // max(1, len(plans)))
    plans = [(k, _thin(o, per)) for k, o in plans]
    base = _picks_cached(base_raw)
    _run_all([{**deepcopy(base_raw), key: deepcopy(value)} for key, opts in plans for _label, value in opts], pool)
    runs, ranked, settled = 1, [], []
    for key, opts in plans:
        flipped, changed_runs = set(), 0
        for _label, value in opts:
            raw = deepcopy(base_raw)
            raw[key] = deepcopy(value)
            picks = _picks_cached(raw)
            runs += 1
            diff = {l for l in LAYERS if picks.get(l) != base.get(l)}
            flipped |= diff
            changed_runs += bool(diff)
        row = {"key": key, "label": specs[key]["label"], "can_change": [l for l in LAYERS if l in flipped],
               "tested": len(opts), "changed": changed_runs}
        (ranked if flipped else settled).append(row)
    ranked.sort(key=lambda r: (-len(r["can_change"]), -r["changed"]))
    return {"base": {l: base.get(l) for l in LAYERS}, "ranked": ranked, "settled_questions": settled,
            "locked": locked, "runs": runs, "settled": not ranked,
            "note": ("No single remaining answer changes your stack." if not ranked else
                     f"{len(ranked)} unanswered question(s) can still change a pick.")}
