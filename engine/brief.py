"""Brief parser: turns a free-text project description into questionnaire answers.

Two steps, both producing answers the questionnaire accepts, each with the words of the brief it came from:

1. Rules (engine/brief_rules.py): always run, need no network, never guess.
2. Language model (engine/llm.py): only when a key is configured, and only for the questions the rules left open.
   Every value it returns is checked against the schema, and each must carry a short quote that really occurs in
   the brief. A value that fails either check is dropped, so the model can read the text but cannot invent answers.

The result lists each filled question (value, source "rule" or "llm", evidence) and the questions still unknown.
"""
from __future__ import annotations

import math
import re

from . import llm
from .brief_rules import read_all, usd_note
from .kb import field_specs

MAX_BRIEF_CHARS = 4000
SKIPPED = {"project_name"}  # a label for exports, never read from the text


def question_keys() -> list[str]:
    return [k for k in field_specs() if k not in SKIPPED]


# ------------------------------------------------------------------ schema validation

def check_value(key: str, value):
    """Validate one answer against the questionnaire. Returns (clean value, None) or (None, reason it was rejected)."""
    spec = field_specs().get(key)
    if spec is None or key in SKIPPED:
        return None, "not a question"
    kind = spec["type"]
    if kind == "number":
        return _check_number(spec, value)
    if kind == "bool":
        return (value, None) if isinstance(value, bool) else (None, "not true or false")
    allowed = [o["value"] for o in spec.get("options", [])]
    if kind == "select":
        text = str(value).strip()
        return (text, None) if text in allowed else (None, f"'{value}' is not one of {allowed}")
    if kind == "multiselect":
        items = value if isinstance(value, list) else [value]
        items = [str(v).strip() for v in items if str(v).strip()]
        # A free list (team skills) also takes names that are not chips, as the questionnaire does: Flutter, Elixir.
        bad = [] if spec.get("free") else [v for v in items if v not in allowed]
        if bad:
            return None, f"{bad} not in {allowed}"
        return (list(dict.fromkeys(items)), None) if items else (None, "empty list")
    return None, "unsupported question type"


def _check_number(spec: dict, value):
    if isinstance(value, bool):
        return None, "not a number"
    if isinstance(value, str):
        try:
            value = float(value.replace(",", ""))
        except ValueError:
            return None, "not a number"
    if not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value):
        return None, "not a number"
    lo, hi = spec.get("min"), spec.get("max")
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        return None, f"{value} outside the allowed range {lo} to {hi}"
    return (int(value) if float(value).is_integer() else value), None


# ------------------------------------------------------------------ evidence quotes

def _norm(text: str) -> str:
    """Lower-case, straighten quotes and collapse whitespace, so a quote can be compared with the brief."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in_text(quote, text: str) -> bool:
    """True when `quote` is a non-empty piece of `text`, ignoring case and whitespace differences."""
    return isinstance(quote, str) and len(_norm(quote)) >= 2 and _norm(quote) in _norm(text)


# ------------------------------------------------------------------ language-model step

DATA_WORDS = re.compile(
    r"\b(?:data|database|schema|tables?|rows?|records?|joins?|relation\w*|entit\w+|document\w*|json|"
    r"key[- ]?value|session\w*|cache|time[- ]?series|metrics?|events?|logs?|sensor\w*|graph|connections?|"
    r"orders?|inventory|transactions?|payments?|posts?|messages?|files?|images?|catalog\w*|stor(?:e|es|ed|ing|age)|"
    r"track\w*|nested|flexible|varying|structured)\b", re.I)


def names_only_skills(quote: str) -> bool:
    """True when `quote` names technologies or skills but says nothing about data, e.g. "5 engineers who know TypeScript
    and Postgres". Such a quote describes the team, so it cannot be the evidence for a data shape."""
    from .brief_rules import read_skills
    return bool(read_skills(quote)) and not DATA_WORDS.search(quote)


def field_guide(keys: list[str], current: dict | None = None) -> str:
    """One line per question: its key, the values it accepts and what it means. Goes into the prompt."""
    specs, lines = field_specs(), []
    for key in keys:
        spec = specs[key]
        if spec["type"] == "number":
            accepts = f"a number from {spec.get('min')} to {spec.get('max')}"
        elif spec["type"] == "bool":
            accepts = "true or false"
        else:
            opts = ", ".join(f'"{o["value"]}"' for o in spec["options"])
            accepts = f"one of {opts}" if spec["type"] == "select" else f"a list of any of {opts}"
        now = f" (current answer: {current[key]!r})" if current and key in current else ""
        lines.append(f'- "{key}": {accepts}. {spec["label"]}: {spec["help"]}{now}')
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You read a software project description and fill in questionnaire answers. Rules: "
    "(1) Include a question only when the text states or clearly implies the answer; never guess and never use defaults. "
    "(2) For every value give a short \"quote\" copied word for word from the text that supports it. "
    "(3) Use only the allowed values listed for each question. "
    "(4) Fill a question only from words that describe THAT question's subject. A sentence about the team's skills "
    "(who knows which language or database) says nothing about the data, the traffic, the platforms or the budget, so "
    "never take a data shape, a scale or a requirement from it; use it only for team skills. "
    "Reply with one JSON object: {\"fields\": {\"<key>\": {\"value\": <value>, \"quote\": \"<words from the text>\"}}}. "
    "Reply with {\"fields\": {}} when nothing qualifies."
)


def ask_llm(text: str, keys: list[str], current: dict | None = None, system: str = SYSTEM_PROMPT,
            label: str = "Project description") -> tuple[dict[str, dict], list[dict], llm.Reply]:
    """Ask the model for the questions in `keys`. Returns (accepted fields, dropped values with reasons, reply)."""
    prompt = (f"Questions you may answer:\n{field_guide(keys, current)}\n\n"
              f'{label}:\n"""\n{text}\n"""')
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    data, reply = llm.chat_json(messages)
    dropped: list[dict] = []
    return validate_llm_fields(data, text, keys, dropped), dropped, reply


def validate_llm_fields(data: dict, text: str, keys: list[str], dropped: list[dict] | None = None) -> dict[str, dict]:
    """Keep only the model's values that are valid answers AND carry a quote found in `text`.
    Rejected ones are appended to `dropped` as {"field", "reason"}."""
    dropped = dropped if dropped is not None else []
    raw = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    accepted: dict[str, dict] = {}
    for key, entry in raw.items():
        if key not in keys:
            continue
        if not isinstance(entry, dict):
            dropped.append({"field": key, "reason": "malformed entry"})
            continue
        value, why = check_value(key, entry.get("value"))
        if not why and key == "data_shapes" and quote_in_text(entry.get("quote"), text) and names_only_skills(entry["quote"]):
            why = "the quote names technologies or skills, not the data"
        if why:
            dropped.append({"field": key, "reason": why})
        elif not quote_in_text(entry.get("quote"), text):
            dropped.append({"field": key, "reason": "the quote does not occur in the description"})
        else:
            accepted[key] = {"value": value, "source": "llm", "evidence": entry["quote"].strip(), "quotes": [entry["quote"].strip()]}
    return accepted


# ------------------------------------------------------------------ the whole parser

def _rule_field(value, quotes: list[str], note: str | None = None) -> dict:
    """A field found by the pattern reader: its value and the words of the text it was read from."""
    out = {"value": value, "source": "rule", "evidence": " / ".join(dict.fromkeys(quotes)), "quotes": quotes}
    if note:
        out["note"] = note
    return out


def read_rules(text: str, only: set[str] | None = None) -> dict[str, dict]:
    """The deterministic step: fields read with patterns, each checked against the schema."""
    fields = {}
    for key, hit in read_all(text, only).items():
        value, why = check_value(key, hit.value)
        if why is None:
            fields[key] = _rule_field(value, hit.quotes, hit.note)
    if "budget_monthly" in fields and fields.get("currency", {}).get("value") == "INR":
        fields["budget_monthly"]["note"] = usd_note(fields["budget_monthly"]["value"], "INR")
    return fields


def parse_brief(text: str, use_llm: bool = True) -> dict:
    """Parse a project description. Returns {"fields", "unknown", "llm"}:
    fields   {question key: {"value", "source": "rule" | "llm", "evidence", "quotes"}}
    unknown  question keys the description did not answer
    llm      {"enabled", "used", "model", "error", "dropped"}: what the language-model step did"""
    text = text.strip()[:MAX_BRIEF_CHARS]
    fields = read_rules(text)
    status = {"enabled": llm.available(), "used": False, "model": None, "error": None, "dropped": []}
    open_keys = [k for k in question_keys() if k not in fields]
    if use_llm and status["enabled"] and open_keys and text:
        try:
            extra, status["dropped"], reply = ask_llm(text, open_keys)
            fields.update(extra)
            status.update(used=True, model=reply.model)
        except llm.LLMError as err:
            status["error"] = str(err)
    return {"fields": fields, "unknown": [k for k in question_keys() if k not in fields], "llm": status}
