"""Loads and validates the curated knowledge base (data/*.json)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAYERS = ("frontend", "backend", "database", "hosting")

# Criteria scored for each layer. Computed criteria (cost, skill_fit, portability,
# data_fit, consistency_fit, region_fit) are derived per project; the rest come from the KB.
LAYER_CRITERIA = {
    "frontend": ["ease", "ops", "maturity", "realtime", "performance", "seo", "velocity",
                 "hiring", "offline", "structure", "interactivity", "skill_fit", "portability"],
    "backend": ["cost", "scalability", "ease", "ops", "maturity", "realtime", "performance",
                "velocity", "hiring", "structure", "skill_fit", "portability", "compliance_maturity"],
    "database": ["cost", "scalability", "ease", "ops", "maturity", "realtime", "performance",
                 "hiring", "offline", "skill_fit", "portability", "data_fit", "consistency_fit"],
    "hosting": ["cost", "scalability", "ease", "ops", "maturity", "realtime", "performance",
                "skill_fit", "portability", "region_fit", "compliance_maturity"],
}
COMPUTED = {"cost", "skill_fit", "portability", "data_fit", "consistency_fit", "region_fit", "compliance_maturity"}

CRITERION_LABELS = {
    "cost": "Cost at your scale",
    "scalability": "Scalability",
    "ease": "Learning curve",
    "ops": "Low ops burden",
    "maturity": "Ecosystem maturity",
    "realtime": "Realtime fit",
    "performance": "Performance / latency",
    "seo": "SEO",
    "velocity": "Development speed",
    "hiring": "Hiring pool",
    "offline": "Offline support",
    "structure": "Structure for large teams",
    "interactivity": "Rich client interactivity",
    "skill_fit": "Team skill match",
    "portability": "Portability (low lock-in)",
    "data_fit": "Data-model fit",
    "consistency_fit": "Consistency fit",
    "region_fit": "Region coverage",
    "compliance_maturity": "Compliance maturity (audit, isolation)",
}

DATA_SHAPES = ["relational", "document", "graph", "time_series", "key_value", "analytical", "vector", "search"]


def _read(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


# A database whose vendor offers no managed service on the cloud that hosts the app (item field
# `self_managed_on`: {provider id: vendor-docs URL showing it}) has to be run by the team there:
# servers, backups, failover, upgrades. That is an operations cost the layer scores cannot see (they
# do not know the host), so each (database, provider) pair becomes a stack rule of this size. It is
# larger than the "a second system to operate" caveat (supabase_timescale, -8): running the primary
# database itself, with backups and failover, is more work than operating one extra managed system.
SELF_MANAGED_DELTA = -12
CLOUD_NAMES = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure"}


def self_managed_rules(items: list[dict]) -> list[dict]:
    """Stack rules derived from the database items' `self_managed_on` maps."""
    out = []
    for it in items:
        for prov, source in (it.get("self_managed_on") or {}).items():
            cloud = CLOUD_NAMES.get(prov, prov)
            out.append({
                "id": f"{it['id']}_self_managed_on_{prov}", "kind": "caveat", "delta": SELF_MANAGED_DELTA,
                "when": {"database": [it["id"]], "hosting_provider": [prov]},
                "note": f"{it['name']} has no managed service on {cloud}, so your team runs it there: servers, backups, "
                        "failover and upgrades.",
                "source": source})
    return out


@lru_cache(maxsize=1)
def load_kb() -> dict:
    kb = {layer: _read(f"kb/{layer}.json")["items"] for layer in LAYERS}
    kb["rules"] = _read("kb/compat_rules.json")["rules"] + self_managed_rules(kb["database"])
    kb["index"] = {item["id"]: dict(item, layer=layer) for layer in LAYERS for item in kb[layer]}
    return kb


@lru_cache(maxsize=1)
def load_questions() -> dict:
    return _read("questions.json")


@lru_cache(maxsize=1)
def load_glossary() -> dict:
    return _read("glossary.json")


@lru_cache(maxsize=1)
def load_presets() -> list:
    return _read("presets.json")["presets"]


def field_specs() -> dict:
    return {f["key"]: f for step in load_questions()["steps"] for f in step["fields"]}


# Conditions a knowledge-base strength or weakness line can carry, so a line is shown only where it
# applies (no "Mumbai regions" for North American users, no Next.js adapter note on a Nuxt stack).
# A line is a string (always shown) or {"text": ..., "when": {...}}; "when" is one condition set
# (all keys must hold) or a list of them (any set may hold).
LINE_CONDITIONS = ("stack_any", "stack_none", "app_type", "realtime", "seo", "compliance_any", "cloud_preference",
                   "india", "eu", "multi_region")


def _cond_holds(key: str, val, stack: set, p: dict) -> bool:
    comp, regions = set(p.get("compliance", [])), set(p.get("regions", []))
    if key == "stack_any":
        return bool(stack & set(val))
    if key == "stack_none":
        return not stack & set(val)
    if key == "compliance_any":
        return bool(comp & set(val))
    if key == "india":
        return bool(regions & {"india", "global"} or comp & {"dpdp", "data_residency_india"}) == val
    if key == "eu":
        return bool(regions & {"europe", "global"} or comp & {"gdpr", "data_residency_eu"}) == val
    if key == "multi_region":
        return ("global" in regions or len(regions) > 1) == val
    return p.get(key) in val


def relevant_lines(lines: list, stack: set, p: dict | None) -> list[str]:
    """Texts of the lines that apply to this stack and these answers. With no answers (p None), only
    unconditional lines."""
    out = []
    for x in lines:
        if isinstance(x, str):
            out.append(x)
            continue
        if p is None:
            continue
        sets = x["when"] if isinstance(x["when"], list) else [x["when"]]
        if any(all(_cond_holds(k, v, stack, p) for k, v in s.items()) for s in sets):
            out.append(x["text"])
    return out


def validate_kb(kb: dict | None = None) -> list[str]:
    """Return a list of schema problems (empty list = valid). Used by tests and at startup."""
    kb = kb or load_kb()
    problems: list[str] = []
    for layer in LAYERS:
        needed = [c for c in LAYER_CRITERIA[layer] if c not in COMPUTED]
        for item in kb[layer]:
            tid = item.get("id", "?")
            for key in ("id", "name", "summary", "scores", "strengths", "weaknesses", "sources"):
                if key not in item:
                    problems.append(f"{layer}/{tid}: missing '{key}'")
            for crit in needed:
                val = item.get("scores", {}).get(crit)
                if not isinstance(val, (int, float)) or not 1 <= val <= 5:
                    problems.append(f"{layer}/{tid}: score '{crit}' missing or out of 1-5")
            for key in ("strengths", "weaknesses"):
                for x in item.get(key, []):
                    if isinstance(x, str):
                        continue
                    sets = x.get("when") if isinstance(x, dict) else None
                    sets = sets if isinstance(sets, list) else [sets]
                    if not isinstance(x.get("text") if isinstance(x, dict) else None, str) or not all(
                            isinstance(s, dict) and s and set(s) <= set(LINE_CONDITIONS) for s in sets):
                        problems.append(f"{layer}/{tid}: bad {key} line {x!r}")
            if not item.get("sources") or not all(str(s).startswith("https://") for s in item["sources"]):
                problems.append(f"{layer}/{tid}: needs https sources")
            if layer in ("backend", "database", "hosting"):
                cost = item.get("cost_usd")
                if not cost or len(cost) != 6 or any(lo > hi for lo, hi in cost):
                    problems.append(f"{layer}/{tid}: cost_usd must be 6 [lo, hi] bands")
                if "scale_ceiling" not in item:
                    problems.append(f"{layer}/{tid}: missing scale_ceiling")
            for ep in item.get("entry_plans", []):
                if not (isinstance(ep.get("max_tier"), int) and 0 <= ep["max_tier"] <= 5 and ep.get("max_data_gb", 0) > 0
                        and isinstance(ep.get("usd"), (int, float)) and ep["usd"] >= 0
                        and ep.get("name") and ep.get("limits") and ep.get("source") in item.get("sources", [])
                        and all(isinstance(ep.get(k, 0), (int, float)) and ep.get(k, 0) >= 0 for k in ("included_gb", "usd_per_gb"))
                        and ep.get("max_compute_tier", 5) in range(6)):
                    problems.append(f"{layer}/{tid}: entry plan {ep.get('name')!r} needs name, usd, limits, max_tier 0-5, "
                                    "max_data_gb and a source listed in the item's sources")
            ws = item.get("without_shape")
            if ws and not (ws.get("shape") in DATA_SHAPES and set(ws.get("models", {})) <= set(DATA_SHAPES)
                           and ws.get("why") and ws.get("source") in item.get("sources", [])):
                problems.append(f"{layer}/{tid}: without_shape needs a known shape, model overrides for known shapes, "
                                "a why and a source listed in the item's sources")
            sr = item.get("server_rendering")
            if sr and not (sr.get("client_alternative") in {x["id"] for x in kb[layer]} and sr.get("own_skills")
                           and sr.get("why") and sr.get("source") in item.get("sources", [])):
                problems.append(f"{layer}/{tid}: server_rendering needs a client_alternative in the same layer, own_skills, "
                                "a why and a source listed in the item's sources")
            pl = item.get("platform_languages")
            if pl and not (pl.get("why") and pl.get("ios") and pl.get("android")
                           and pl.get("sources") and set(pl["sources"]) <= set(item.get("sources", []))):
                problems.append(f"{layer}/{tid}: platform_languages needs ios, android, a why and sources listed in the "
                                "item's sources")
            if layer == "database":
                if set(item.get("models", {})) != set(DATA_SHAPES):
                    problems.append(f"{layer}/{tid}: models must cover {DATA_SHAPES}")
                if item.get("consistency") not in ("strong", "tunable", "eventual"):
                    problems.append(f"{layer}/{tid}: bad consistency")
                sor = item.get("system_of_record")
                if sor is not None and not (isinstance(sor.get("shapes"), list) and set(sor["shapes"]) <= set(DATA_SHAPES)
                                            and sor.get("why") and sor.get("source") in item.get("sources", [])
                                            and sor.get("regulated", False) is False):
                    problems.append(f"{layer}/{tid}: system_of_record needs known shapes, a why and a source listed in "
                                    "the item's sources (regulated may only be false)")
                for prov, src in (item.get("self_managed_on") or {}).items():
                    if prov not in (item.get("managed_offerings") or {}):
                        problems.append(f"{layer}/{tid}: self_managed_on '{prov}' needs a managed_offerings entry naming the self-managed setup")
                    if src not in item.get("sources", []):
                        problems.append(f"{layer}/{tid}: self_managed_on '{prov}' source must be one of the item's sources")
            if layer == "hosting":
                if "regions" not in item or "compliance" not in item:
                    problems.append(f"{layer}/{tid}: hosting needs regions + compliance")
                sla = item.get("sla")
                if sla is not None and not (isinstance(sla.get("percent"), (int, float)) and 90 <= sla["percent"] <= 100
                                            and sla.get("scope") and sla.get("source") in item.get("sources", [])):
                    problems.append(f"{layer}/{tid}: sla needs a percent, a scope and a source listed in the item's sources")
                stz = item.get("scale_to_zero")
                if stz is not None and not (stz.get("why") and stz.get("source") in item.get("sources", [])):
                    problems.append(f"{layer}/{tid}: scale_to_zero needs a why and a source listed in the item's sources")
            if layer == "hosting" or item.get("kind") == "baas":
                mat = item.get("compliance", {}).get("maturity")
                if not isinstance(mat, (int, float)) or not 1 <= mat <= 5:
                    problems.append(f"{layer}/{tid}: compliance.maturity missing or out of 1-5")
                if not all(str(s).startswith("https://") for s in item.get("compliance", {}).get("maturity_sources", [None])):
                    problems.append(f"{layer}/{tid}: compliance.maturity_sources must be https URLs")
    ids = set(kb["index"])
    for rule in kb["rules"]:
        for part in ("when", "not"):
            for key, vals in rule.get(part, {}).items():
                if key in LAYERS:
                    for v in vals:
                        if v not in ids:
                            problems.append(f"rule {rule['id']}: unknown id '{v}'")
    return problems
