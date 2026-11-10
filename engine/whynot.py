"""'Why not X?': fix ("pin") one layer, or the whole stack, to technologies the user names, re-run the
stack search, and compare with the recommendation: the point gap, the criteria and rules behind it,
the cost difference, and the single answer changes that would make the named choice win."""
from __future__ import annotations

from copy import deepcopy

from .explain import compare_text, points
from .kb import LAYERS, field_specs, load_kb
from .recommender import _core, _stack_cost
from .scoring import score_layer
from .sensitivity import _run, options_for
from .stack import TIE_MARGIN, search

MAX_CHANGES = 6
SKIP_FIELDS = ("project_name", "currency")


def why_not(raw: dict | None, pins: dict[str, str], try_changes: bool = True) -> dict:
    """pins: layer -> knowledge-base id (one layer, or all four to grade a whole stack)."""
    kb = load_kb()
    raw = deepcopy(raw or {})
    pins = {l: i for l, i in (pins or {}).items() if l in LAYERS and i in {x["id"] for x in kb[l]}}
    if not pins:
        return {"ok": False, "error": "Name a layer and a technology from the knowledge base."}
    core = _core(deepcopy(raw))
    if core["infeasible"]:
        return {"ok": False, "error": "No stack passes the hard constraints for these answers."}
    p, d, w = core["p"], core["d"], core["w"]
    best = core["combos"][0]
    scored = dict(core["scored"])
    layers = {}
    for layer, iid in pins.items():
        ex = next((e for e in core["excluded"][layer] if e["id"] == iid), None)
        cands, _ = score_layer(layer, kb[layer], p, d, w, relax=core.get("relaxed", {}).get(layer, 0), force=(iid,))
        cand = next(c for c in cands if c["id"] == iid)
        scored[layer] = [cand]
        pick = best["picks"][layer]
        layers[layer] = {"id": iid, "name": cand["name"], "pick": pick["name"], "is_pick": pick["id"] == iid,
                         "score": cand["score"], "pick_score": pick["score"],
                         "excluded": ex["reasons"] if ex else [],
                         "compare": compare_text(pick, cand) if pick["id"] != iid else ""}
    pinned = search(scored, kb["rules"], p, d)[0]
    gap = round(best["score"] - pinned["score"], 2)
    db_scored = core["scored"]["database"]
    cost_best, cost_pinned = _stack_cost(p, d, best, db_scored), _stack_cost(p, d, pinned, db_scored)
    mine, theirs = {r["id"] for r in best["rules"]}, {r["id"] for r in pinned["rules"]}
    rules_lost = [f"{r['note']} ({r['delta']:+})" for r in best["rules"] if r["id"] not in theirs and r["delta"] > 0]
    rules_gained = [f"{r['note']} ({r['delta']:+})" for r in pinned["rules"] if r["id"] not in mine and r["delta"] < 0]
    others = {l: pinned["picks"][l]["name"] for l in LAYERS if l not in pins and pinned["picks"][l]["id"] != best["picks"][l]["id"]}
    excluded = [l for l, x in layers.items() if x["excluded"]]
    names = " + ".join(layers[l]["name"] for l in LAYERS if l in layers)
    if all(x["is_pick"] for x in layers.values()):
        verdict = f"{names} is already the recommendation."
    elif excluded:
        verdict = (f"{names} is ruled out by your answers: "
                   + "; ".join(f"{layers[l]['name']}: {layers[l]['excluded'][0].rstrip('.')}" for l in excluded)
                   + f". Scored anyway (approximate), its best stack is {points(gap)} below the recommendation.")
    elif abs(gap) < TIE_MARGIN:
        where = f"{points(gap)} behind" if gap >= 0 else f"{points(gap)} ahead"
        verdict = f"{names} is within the {TIE_MARGIN:g}-point tie margin ({where}, counted as tied); either is defensible."
    elif gap < 0:
        verdict = (f"The best stack with {names} scores {points(gap)} above the recommendation; the "
                   "recommendation was kept for the reason in its tie-break note (budget, team skills or "
                   "growth over time).")
    else:
        verdict = f"The best stack with {names} scores {points(gap)} below the recommendation."
    out = {"ok": True, "pins": pins, "verdict": verdict, "gap": gap, "tie": abs(gap) < TIE_MARGIN,
           "approximate": bool(excluded), "layers": layers,
           "stack": {l: pinned["picks"][l]["name"] for l in LAYERS}, "stack_score": pinned["score"],
           "best_stack": {l: best["picks"][l]["name"] for l in LAYERS}, "best_score": best["score"],
           "other_layers_changed": others, "rules_lost": rules_lost, "rules_gained": rules_gained,
           "cost": {"pinned_low": cost_pinned, "best_low": cost_best, "difference": round(cost_pinned - cost_best, 2)},
           "changes": [], "changes_tested": 0}
    if try_changes and not all(x["is_pick"] for x in layers.values()):
        out["changes"], out["changes_tested"] = _winning_changes(raw, p, pins)
    return out


def _winning_changes(raw: dict, p: dict, pins: dict) -> tuple[list[dict], int]:
    """Single answer changes (one field at a time, every other answer kept) that make the pinned choice the pick."""
    specs = field_specs()
    base = deepcopy(p)
    found, tested = [], 0
    for key, spec in specs.items():
        if key in SKIP_FIELDS:
            continue
        for label, value in options_for(key, spec, p.get("currency", "USD")):
            if value == base.get(key):
                continue
            trial = dict(base, **{key: deepcopy(value)})
            picks = _run(trial)
            tested += 1
            if picks and all(picks.get(l) == i for l, i in pins.items()):
                found.append({"key": key, "field": spec["label"], "value": value, "label": label})
                break  # one value per question is enough to show the lever
        if len(found) >= MAX_CHANGES:
            break
    return found, tested
