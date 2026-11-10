"""Second opinion: a language model proposes its own stack, the rule engine grades it.

The model gets the project description and the list of technologies the knowledge base knows, and answers with one id
per layer. It never decides anything: the engine runs `why_not` on the model's four picks and reports which hard
requirements they break, the score gap and the cost difference against the engine's own stack. The same prompt and
grading are used by tools/llm_baseline.py to measure the model alone on the benchmark briefs.
"""
from __future__ import annotations

from copy import deepcopy

from . import llm
from .kb import LAYERS, field_specs, load_kb
from .profile import derive, normalize
from .recommender import recommend
from .whynot import why_not

SYSTEM_PROMPT = (
    "You are a senior engineer choosing a technology stack. Read the project description and pick exactly one option "
    "per layer (frontend, backend, database, hosting) from the allowed lists. Use the id exactly as listed. "
    'Reply with one JSON object: {"frontend": "<id>", "backend": "<id>", "database": "<id>", "hosting": "<id>"}.'
)
LAYER_NAME = {"frontend": "Frontend", "backend": "Backend", "database": "Database", "hosting": "Hosting"}


def allowed_options() -> dict[str, dict[str, str]]:
    """{layer: {id: name}} for every technology in the knowledge base."""
    kb = load_kb()
    return {layer: {item["id"]: item["name"] for item in kb[layer]} for layer in LAYERS}


def build_messages(brief_text: str, options: dict[str, dict[str, str]]) -> list[dict]:
    lists = "\n".join(f"{layer}: " + "; ".join(f"{i} = {n}" for i, n in options[layer].items()) for layer in LAYERS)
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Allowed options (id = name):\n{lists}\n\nProject description:\n{brief_text}"}]


def read_picks(data: dict, options: dict[str, dict[str, str]]) -> dict[str, str | None]:
    """The model's pick per layer; None where the answer is not one of the allowed ids."""
    return {layer: (data.get(layer) if data.get(layer) in options[layer] else None) for layer in LAYERS}


# ------------------------------------------------------------------ grading

def engine_pick_ids(raw: dict) -> dict[str, str]:
    """The ids of the engine's own stack for these answers."""
    stack = recommend(deepcopy(raw), with_counterfactuals=False)["stack"]
    return {layer: stack[layer]["pick"]["id"] for layer in LAYERS}


def grade_stack(raw: dict, picks: dict[str, str | None]) -> dict:
    """Grade a stack with the engine, offline. `picks` maps layer to a knowledge-base id (None = no valid pick).

    Returns {"ok": False, "error"} when nothing can be graded, else:
      breaks      {layer: [reasons]} for each pick a hard requirement rules out (empty = none)
      gap         engine stack score minus this stack's score (approximate when a pick is ruled out)
      cost_low    minimum monthly cost of this stack in USD, engine_cost_low the engine's own, cost_diff the difference
      budget_usd  the budget converted to USD with the engine's fixed rate (INR budgets included)
      over_budget True when cost_low is above budget_usd; over_by how much
      complete    True when all four layers had a valid pick (cost and gap are only meaningful then)
    """
    pins = {l: i for l, i in picks.items() if i}
    if not pins:
        return {"ok": False, "error": "no valid pick to grade"}
    g = why_not(raw, pins, try_changes=False)
    if not g.get("ok"):
        return {"ok": False, "error": g.get("error", "could not grade")}
    p, assumptions, warnings = normalize(deepcopy(raw))
    budget = derive(p, assumptions, warnings)["budget_usd"]
    low, best_low = g["cost"]["pinned_low"], g["cost"]["best_low"]
    return {"ok": True, "complete": len(pins) == len(LAYERS),
            "breaks": {l: x["excluded"] for l, x in g["layers"].items() if x["excluded"]},
            "gap": g["gap"], "cost_low": low, "engine_cost_low": best_low, "cost_diff": round(low - best_low, 2),
            "budget_usd": budget, "over_budget": low > budget, "over_by": round(max(0.0, low - budget), 2),
            "layers": g["layers"], "verdict": g["verdict"]}


# ------------------------------------------------------------------ the answers as text for the model

def describe_answers(raw: dict) -> str:
    """The user's answers as a plain list the model can read: question label, then the answer in words."""
    specs = field_specs()
    p, _, _ = normalize(deepcopy(raw or {}))
    lines = []
    for key in (raw or {}):
        spec = specs.get(key)
        if spec is None or key in ("project_name", "currency"):
            continue
        value = p.get(key, raw[key])
        labels = {o["value"]: o["label"] for o in spec.get("options", [])}
        if isinstance(value, bool):
            text = "yes" if value else "no"
        elif isinstance(value, list):
            text = ", ".join(str(labels.get(v, v)) for v in value) or "none"
        else:
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            text = str(labels.get(value, value))
            if key == "budget_monthly":
                text += f" {p.get('currency', 'USD')} per month"
        lines.append(f"{spec['label']}: {text}")
    return "\n".join(lines) or "No answers given."


# ------------------------------------------------------------------ the feature

def _usd(v: float) -> str:
    return f"${abs(v):,.0f}"


def second_opinion(raw: dict, use_cache: bool = True) -> dict:
    """Ask the model for its own stack and grade it against the engine's. Never raises: failures come back as
    {"ok": False, "enabled": ..., "note": ...}."""
    raw = raw or {}
    if not llm.available():
        return {"ok": False, "enabled": False, "note": "The language model is off (no API key), so there is no second opinion."}
    options = allowed_options()
    try:
        data, reply = llm.chat_json(build_messages(describe_answers(raw), options), use_cache=use_cache)
    except llm.LLMError as err:
        return {"ok": False, "enabled": True, "note": f"The model did not answer ({err}). Try again later."}
    picks = read_picks(data, options)
    result = recommend(deepcopy(raw), with_counterfactuals=False)
    engine = {l: result["stack"][l]["pick"] for l in LAYERS}
    grade = grade_stack(raw, picks)
    if not grade["ok"]:
        return {"ok": False, "enabled": True, "model": reply.model, "note": "The model named no technology from the knowledge base."}
    layers, lines = {}, []
    for layer in LAYERS:
        mine, theirs = picks[layer], engine[layer]
        agree = mine == theirs["id"]
        info = grade["layers"].get(layer)
        reasons = info["excluded"] if info else []
        name = options[layer].get(mine) if mine else None
        if mine is None:
            line = f"{LAYER_NAME[layer]}: the model gave no valid option; the engine picks {theirs['name']}."
        elif agree:
            line = f"{LAYER_NAME[layer]}: both pick {theirs['name']}."
        elif reasons:
            line = (f"{LAYER_NAME[layer]}: the model suggests {name}; the engine rules it out: "
                    f"{'; '.join(r.rstrip('.') for r in reasons)}. The engine picks {theirs['name']}.")
        else:
            line = (f"{LAYER_NAME[layer]}: the model suggests {name}; the engine picks {theirs['name']}"
                    f"{(': ' + info['compare'].rstrip('.')) if info and info.get('compare') else ''}.")
        engine_reason = "" if agree else (result["stack"][layer]["explanation"]["why"] or [""])[0]
        layers[layer] = {"model_id": mine, "model": name, "engine_id": theirs["id"], "engine": theirs["name"],
                         "agree": agree, "ruled_out": reasons, "engine_reason": engine_reason, "verdict": line}
        lines.append(line)
    breaks = [f"{LAYER_NAME[l]} ({layers[l]['model']}): {'; '.join(r.rstrip('.') for r in rs)}" for l, rs in grade["breaks"].items()]
    cost = {"model_low": grade["cost_low"], "engine_low": grade["engine_cost_low"], "difference": grade["cost_diff"],
            "budget_usd": grade["budget_usd"], "model_over_budget": grade["over_budget"]}
    if all(v["agree"] for v in layers.values()):
        summary = "The model and the engine chose the same stack."
    else:
        summary = (f"The engine's stack scores {abs(grade['gap']):.1f} stack points "
                   f"{'above' if grade['gap'] >= 0 else 'below'} the model's" if not breaks else
                   "The model's stack breaks a hard requirement, so the engine cannot recommend it "
                   "(its score is only approximate)")
        if grade["cost_diff"]:
            summary += (f"; it costs at least {_usd(grade['cost_diff'])} a month "
                        f"{'more' if grade['cost_diff'] > 0 else 'less'} than the engine's stack")
        summary += "."
    if grade["over_budget"]:
        lines.append(f"The model's stack costs at least {_usd(grade['cost_low'])} a month, above your budget of {_usd(grade['budget_usd'])}.")
    return {"ok": True, "enabled": True, "model": reply.model, "complete": grade["complete"],
            "model_stack": {l: picks[l] for l in LAYERS}, "engine_stack": {l: engine[l]["id"] for l in LAYERS},
            "layers": layers, "breaks": breaks, "gap": grade["gap"], "cost": cost, "summary": summary, "verdicts": lines}
