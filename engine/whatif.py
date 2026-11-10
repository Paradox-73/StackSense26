"""Plain-English what-if: turns "what if we had ten times the users?" into answer changes for the engine.

The question is read the same way as a project description (engine/brief.py): patterns first, then the language
model for what is left. Every change must be a value the questionnaire accepts and must carry a quote from the
question. The engine then re-runs on the changed answers, so every consequence still comes from the rules.
"""
from __future__ import annotations

import re

from . import llm
from .brief import _rule_field, ask_llm, check_value, question_keys, read_rules
from .profile import normalize

MAX_QUESTION_CHARS = 400
# Words such as "chat app" or "website" in a what-if describe the project, not a change to it, so the
# pattern reader leaves these two alone; the model can still set them when the question says so.
PATTERN_SKIPS = {"app_type", "platforms"}

NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "twenty": 20, "fifty": 50, "hundred": 100}
FACTOR_WORDS = {"double": 2.0, "twice": 2.0, "triple": 3.0, "half": 0.5}
# What a relative change can scale: the words after the factor, and the answer each one means.
RELATIVE_NOUNS = {"users": "dau", "visitors": "dau", "traffic": "dau",
                  "team": "team_size", "engineers": "team_size", "developers": "team_size",
                  "budget": "budget_monthly"}
RELATIVE = re.compile(
    r"\b(?:(?P<n>\d+(?:\.\d+)?|" + "|".join(NUMBER_WORDS) + r")\s*(?:x|times)(?:\s+as\s+many|\s+more)?"
    r"|(?P<f>" + "|".join(FACTOR_WORDS) + r"))"
    r"(?:\s+(?:the|our|of|as\s+many))*\s+(?P<noun>" + "|".join(RELATIVE_NOUNS) + r")\b",
    re.I)


def relative_changes(question: str, current: dict) -> dict[str, dict]:
    """Read "ten times the users", "10x traffic", "double the team", "half the budget" as new absolute answers."""
    found = {}
    for m in RELATIVE.finditer(question):
        key = RELATIVE_NOUNS[m["noun"].lower()]
        before = current.get(key)
        if not isinstance(before, (int, float)) or isinstance(before, bool):
            continue
        n = m["n"]
        factor = FACTOR_WORDS[m["f"].lower()] if m["f"] else NUMBER_WORDS.get(n.lower()) or float(n)
        value = max(1, round(before * factor)) if key != "budget_monthly" else round(before * factor, 2)
        value, why = check_value(key, value)
        if why is None:
            found[key] = _rule_field(value, [m[0]])
    return found


SYSTEM_PROMPT = (
    "A user asks a what-if question about a software project's answers. Return only the answers the question CHANGES, "
    "as new absolute values. When the question is relative (for example 'ten times the users'), compute the new value from "
    "the current answer shown next to each question. Rules: "
    "(1) Never change something the question does not mention. "
    "(2) For every change give a short \"quote\" copied word for word from the question. "
    "(3) Use only the allowed values listed for each question. "
    "Reply with one JSON object: {\"fields\": {\"<key>\": {\"value\": <new value>, \"quote\": \"<words from the question>\"}}}. "
    "Reply with {\"fields\": {}} when the question changes no answer."
)


def propose_changes(question: str, answers: dict, use_llm: bool = True) -> dict:
    """Map a what-if question to changes of `answers`.

    Returns {"changes": {key: {"value", "before", "source", "evidence"}}, "llm": {...}}. Values equal to the current
    answer are left out."""
    question = question.strip()[:MAX_QUESTION_CHARS]
    current, _, _ = normalize(answers)
    found = {k: v for k, v in read_rules(question).items() if k not in PATTERN_SKIPS}
    found.update(relative_changes(question, current))
    status = {"enabled": llm.available(), "used": False, "model": None, "error": None, "dropped": []}
    if use_llm and status["enabled"] and question:
        keys = [k for k in question_keys() if k not in found]
        try:
            extra, status["dropped"], reply = ask_llm(question, keys, current, SYSTEM_PROMPT, "What-if question")
            found.update(extra)
            status.update(used=True, model=reply.model)
        except llm.LLMError as err:
            status["error"] = str(err)
    changes = {k: dict(f, before=current.get(k)) for k, f in found.items() if f["value"] != current.get(k)}
    return {"changes": changes, "llm": status}
