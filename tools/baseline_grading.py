"""Prompt and grading for tools/llm_baseline.py, an offline experiment that is not part of the engine or the app.

A language model gets a benchmark brief and the knowledge base's technology ids and answers with one id per layer; the
rule engine then grades that stack (`why_not` on the four picks: the hard requirements they break, the score gap and
the cost difference against the engine's own stack). The engine never sees the model's answer, so the experiment
measures a model alone against the rules on the same briefs.
"""
from __future__ import annotations

import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.kb import LAYERS, field_specs, load_kb  # noqa: E402
from engine.profile import derive, normalize  # noqa: E402
from engine.recommender import recommend  # noqa: E402
from engine.whynot import why_not  # noqa: E402

SYSTEM_PROMPT = (
    "You are a senior engineer choosing a technology stack. Read the project description and pick exactly one option "
    "per layer (frontend, backend, database, hosting) from the allowed lists. Use the id exactly as listed. "
    'Reply with one JSON object: {"frontend": "<id>", "backend": "<id>", "database": "<id>", "hosting": "<id>"}.'
)


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
