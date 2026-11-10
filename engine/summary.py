"""Grounded plain-English summary of a recommendation.

The rule engine has already decided the stack. Here a language model only re-words the engine's own output:

1. `build_facts()` collects what the engine decided (picks, scores, reasons, rejected options, cost, conflicts, sources).
2. The model writes one short paragraph per layer plus an overall paragraph, from those facts only.
3. `validate()` rejects any text that names a technology, or contains a number, that is not in the facts.
4. A failed check triggers one retry that shows the model its mistakes; a second failure, or no API key,
   falls back to the engine's template explanation. The text is never shown unchecked.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from . import llm
from .kb import LAYERS, load_kb

MAX_ATTEMPTS = 2

# ------------------------------------------------------------------ facts

def _name(item: dict) -> str:
    return item["name"]


def build_facts(result: dict) -> dict:
    """The engine's decisions as a small JSON-able dict. The model may use only what is in here."""
    p, d, cost = result["profile"], result["derived"], result["cost"]
    facts: dict = {
        "project": {"daily_users": p["dau"], "team_size": p["team_size"], "timeline_weeks": p["timeline_weeks"],
                    "monthly_budget": p["budget_monthly"], "budget_currency": p["currency"], "scale_tier": d["tier_label"]},
        "scores_are_out_of": 100,
        "stack_score": result["stack_score"],
        "layer_count": len(LAYERS),
        "cost_per_month_usd": {"low": round(cost["total_low"]), "high": round(cost["total_high"]), "budget_status": cost["status"]},
        "layers": {layer: _layer_facts(result["stack"][layer]) for layer in LAYERS},
        "conflicts": [{"title": w["title"], "detail": w["detail"]} for w in result["warnings"]
                      if w["severity"] in ("critical", "warning")][:4],
        "stack_rules_that_applied": [c["note"] for c in result.get("compatibility", [])][:3],
        "sources": sorted({urlparse(u).netloc for u in result.get("sources", [])})[:8],
    }
    if p["currency"] == "INR":
        facts["cost_per_month_inr"] = {"low": round(cost["total_low_inr"]), "high": round(cost["total_high_inr"])}
    return facts


def _layer_facts(layer: dict) -> dict:
    ex, pick = layer["explanation"], layer["pick"]
    run = ex.get("vs_runner_up") or {}
    return {
        "pick": _name(pick), "score": pick["score"], "confidence": ex["confidence"],
        "main_reasons": ex["why"][:3], "trade_offs": ex["tradeoffs"][:2], "risks": ex["risks"][:2],
        "runner_up": {"name": run.get("runner_up"), "margin_in_stack_points": run.get("margin")} if run else None,
        "rejected_alternatives": [_name(a) for a in layer["alternatives"][:2]],
        "ruled_out": [{"name": x["name"], "reason": x["reasons"][0]} for x in layer.get("excluded", [])[:2] if x.get("reasons")],
    }


# ------------------------------------------------------------------ technology names

AMBIGUOUS_NAMES = {"Go", "Render", "Express", "Phoenix", "Rails", "Spring", "Native", "Workers"}  # also ordinary words: match capitalised only
SKIP_ALIASES = {"static", "none", "android", "native ios", "server-rendered html", "no database", "no server code", "html"}
EXTRA_ALIASES = {"postgres": ["Postgres"], "mongodb": ["Mongo"], "aws_lambda": ["Lambda"], "gcp_cloud_run": ["Cloud Run"],
                 "flyio": ["Fly"], "react_spa": ["React"], "nextjs": ["NextJS"], "sveltekit": ["Svelte"]}


def _aliases(item: dict) -> set[str]:
    """Names a person may use for a technology: the full name, the name without brackets, and each part of
    'A + B' / 'A / B' names ('Node.js + Express' -> Node.js, Express)."""
    name = item["name"]
    out = {name, re.sub(r"\s*\(.*?\)", "", name).strip()}
    for part in re.split(r"\s+[+/]\s+|/", re.sub(r"\s*\(.*?\)", "", name)):
        out.add(part.strip())
    for inner in re.findall(r"\(([^)]*)\)", name):  # brackets that hold a product name: 'React SPA (Vite)'
        out.update(x.strip() for x in re.split(r"[,/]| or ", inner) if re.fullmatch(r"[A-Z][A-Za-z.]+", x.strip()))
    out.update(EXTRA_ALIASES.get(item["id"], []))
    return {a for a in out if len(a) >= 2 and a.lower() not in SKIP_ALIASES and a not in {"BaaS", "FaaS"}}


def alias_index() -> dict[str, set[str]]:
    """lower-case alias -> ids of the technologies that go by it."""
    index: dict[str, set[str]] = {}
    for layer in LAYERS:
        for item in load_kb()[layer]:
            for alias in _aliases(item):
                index.setdefault(alias, set()).add(item["id"])
    return index


def mentioned_technologies(text: str) -> dict[str, set[str]]:
    """{alias found in text: ids it can stand for}. Longer names are matched first and then blanked out."""
    found: dict[str, set[str]] = {}
    for alias, ids in sorted(alias_index().items(), key=lambda kv: -len(kv[0])):
        flags = 0 if alias in AMBIGUOUS_NAMES else re.I
        rx = re.compile(r"(?<![\w.])" + re.escape(alias) + r"(?![\w])", flags)
        if rx.search(text):
            found[alias] = ids
            text = rx.sub(" ", text)
    return found


# ------------------------------------------------------------------ numbers

NUMBER = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?:\s?(k|m|lakhs?|crores?|thousand|million))?(?![\w])", re.I)
SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7}


def numbers_in(text: str) -> set[float]:
    """Every number in `text` as a float. '1,000', '1k', '$25' and '25.0' read as 1000, 1000, 25 and 25."""
    out = set()
    for m in NUMBER.finditer(text):
        try:
            value = float(m.group(1).replace(",", "").rstrip("."))
        except ValueError:
            continue
        out.add(round(value * SCALE.get((m.group(2) or "").lower(), 1), 6))
    return out


# ------------------------------------------------------------------ validation

def validate(parts: dict[str, str], facts: dict) -> list[str]:
    """Problems found in the generated texts ({"overall": ..., "frontend": ...}); an empty list means they pass."""
    facts_text = json.dumps(facts, ensure_ascii=False)
    fact_ids = {i for ids in mentioned_technologies(facts_text).values() for i in ids}
    fact_numbers = numbers_in(facts_text)
    errors = []
    for part, text in parts.items():
        for alias, ids in mentioned_technologies(text).items():
            if not ids & fact_ids:
                errors.append(f'{part}: names "{alias}", which is not among the technologies in the facts')
        for number in sorted(numbers_in(text) - fact_numbers):
            errors.append(f"{part}: contains the number {number:g}, which is not in the facts")
    return errors


# ------------------------------------------------------------------ generation

SYSTEM_PROMPT = (
    "You explain a tech-stack recommendation in plain English for a non-expert. A rule engine already chose the stack; "
    "you only re-word its facts. Use ONLY the facts JSON you are given: do not name any technology that is not in it, "
    "and do not write any number that is not in it (copy numbers exactly as written there). Do not add advice or claims of your own. "
    "Write short sentences in everyday words. Do not copy the reason strings or score notation such as '5.0/5 vs 3.6 average': "
    "say what they mean (for example 'the easiest of these to hire for' or 'the best fit for this kind of data'). "
    "Where a runner-up is given, say in a few words why it lost. Reply with one JSON object: "
    '{"layers": {"frontend": "...", "backend": "...", "database": "...", "hosting": "..."}, "overall": "..."}. '
    "Each layer text is 1 or 2 sentences: what was picked and the main reason. "
    "The overall text is 3 or 4 sentences: the stack, the monthly cost against the budget, and the main risk or conflict if there is one."
)


def _parts(data: dict) -> dict[str, str] | None:
    """The model's JSON as {"frontend": text, ..., "overall": text}, or None when the shape is wrong."""
    layers = data.get("layers")
    if not isinstance(layers, dict) or not isinstance(data.get("overall"), str):
        return None
    parts = {layer: layers.get(layer) for layer in LAYERS}
    parts["overall"] = data["overall"]
    return parts if all(isinstance(t, str) and t.strip() for t in parts.values()) else None


def template_summary(result: dict) -> dict:
    """The engine's own template explanation, used when the model is off, fails, or fails the check."""
    layers = {l: result["stack"][l]["explanation"].get("paragraph", "") for l in LAYERS} if result.get("feasible") else {}
    return {"layers": layers, "overall": result.get("summary", "")}


def summarize(result: dict) -> dict:
    """Plain-English summary of `result` (the output of engine.recommend).

    Returns {"source": "llm" | "template", "checked": bool, "model", "layers", "overall", "attempts", "errors", "llm_enabled"}.
    "checked" is True only for model text that passed validate()."""
    base = {"model": None, "attempts": 0, "errors": [], "llm_enabled": llm.available()}
    if not result.get("feasible") or not llm.available():
        return {"source": "template", "checked": False, **template_summary(result), **base}
    facts = build_facts(result)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Facts:\n" + json.dumps(facts, ensure_ascii=False, indent=1)}]
    errors: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data, reply = llm.chat_json(messages)
        except llm.LLMError as err:
            errors = [str(err)]
            break
        base.update(attempts=attempt, model=reply.model)
        parts = _parts(data)
        errors = ["the reply did not have the requested shape"] if parts is None else validate(parts, facts)
        if not errors:
            return {"source": "llm", "checked": True, "layers": {l: parts[l] for l in LAYERS}, "overall": parts["overall"], **base}
        messages += [{"role": "assistant", "content": reply.text},
                     {"role": "user", "content": "That answer broke the rules:\n- " + "\n- ".join(errors[:8]) +
                      "\nWrite it again with the same JSON shape, using only technologies and numbers from the facts."}]
    return {"source": "template", "checked": False, **template_summary(result), **dict(base, errors=errors)}
