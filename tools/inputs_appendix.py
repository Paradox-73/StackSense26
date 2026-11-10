"""Appendix B of the report: the question catalogue and what each answer changes, written from the code and data.

    python tools/inputs_appendix.py        # prints the Markdown (tools/build_assets.py writes report/inputs_appendix.md)

Sources of every number: data/questions.json (the questions), app/static/app.js (which are in quick mode),
report/question_influence.json (how often changing an answer changed a pick; made by tools/question_influence.py)
and engine/profile.py (the derived quantities and their thresholds).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import profile as P  # noqa: E402
from engine.kb import load_questions  # noqa: E402

# Questions that have no quick-mode control of their own but are set by a must-have chip.
MUST_KEYS = {"realtime", "offline", "seo", "platforms"}
# A note printed under the table of the step that holds the question, where a number needs explaining.
# Each note is built from the study's numbers, so it cannot disagree with the table.
NOTES = {"special_workloads": lambda x: (f"Special workloads changes a pick in {round(100 * x['pick_change_rate'])}% of re-runs; its main effect is on "
                                        "the supporting services and the cost estimate (video, maps, SMS and file delivery are priced separately).")}


def quick_keys() -> set[str]:
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    block = re.search(r"const QUICK = \[(.*?)\n\];", js, re.S).group(1)
    keys = set(re.findall(r'key2?: "([a-z_]+)"', block)) - {"must"}
    return keys | MUST_KEYS


def _first_sentence(t: str, limit: int = 190) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    return s if len(s) <= limit else s[: limit - 1].rsplit(" ", 1)[0] + "..."


def _answer(f: dict) -> str:
    t = f["type"]
    if t == "number":
        lo, hi = f.get("min"), f.get("max")
        unit = f.get("unit") or ""
        d = f.get("default")
        rng = f", {lo:,} to {hi:,}" if lo is not None and hi is not None else ""
        return f"Number{f' ({unit})' if unit else ''}{rng}; " + (f"default {d:,}" if d is not None else "optional, derived when left empty")
    if t == "select":
        return f"One of {len(f['options'])}; default {_label(f, f['default'])}"
    if t == "multiselect":
        return f"Any of {len(f['options'])}" + (f"; default {', '.join(_label(f, x) for x in f['default'])}" if f.get("default") else "; default none")
    if t == "bool":
        return f"Yes or no; default {'yes' if f.get('default') else 'no'}"
    return "Free text; names the project only"


def _label(f: dict, v) -> str:
    for o in f.get("options", []):
        if o["value"] == v:
            return re.split(r"\s+[—–-]\s+|\s*\(", o["label"])[0].strip()
    return str(v)


def influence() -> dict[str, dict]:
    d = json.loads((ROOT / "report" / "question_influence.json").read_text(encoding="utf-8"))
    return {x["key"]: x for x in d["all"]}


def derived_rows() -> list[tuple[str, str, str]]:
    rpd = P.REQ_PER_USER_DAY
    lo, hi = min(rpd.values()), max(rpd.values())
    pf = ", ".join(f"{k.replace('_', ' ')} x{v}" for k, v in P.PEAK_FACTOR.items())
    th = lambda xs: " / ".join(f"{x:,.0f}" for x in xs)
    return [
        ("Budget in dollars", f"budget; if the currency is INR, budget / {P.INR_PER_USD:.0f} (a fixed planning rate)", "cost fit, budget guard, over-budget warnings"),
        ("Requests per user per day", f"set by the app type, from {lo} to {hi:,}; 100 if unknown", "peak requests per second"),
        ("Peak factor", f"{pf}; x{P.DEFAULT_PEAK_FACTOR} for other app types; steady traffic caps it at 3, spiky traffic raises it to at least 15", "peak requests per second"),
        ("Share reaching the servers", "cacheable share: little or unsure x1.0, some x0.6, most x0.2", "peak requests per second (a CDN, a network of caching servers close to users, absorbs the rest)"),
        ("Peak requests per second", "daily users x requests per user per day / 86,400 x peak factor x share reaching the servers; a stated peak is used as given (times the share reaching the servers); if it differs from the estimate by more than 30 times, the larger figure is used, except for IoT where the stated rate wins", "compute tier, load balancer and cache advice"),
        ("Compute tier (0 to 5)", f"the higher of the tier of daily users (limits {th(P.DAU_THRESHOLDS)}) and the tier of peak requests per second (limits {th(P.RPS_THRESHOLDS)})", "price band of every option, scale ceilings, weights"),
        ("Data tier (0 to 5)", f"data in 12 months = volume + 12 x monthly growth; tier limits in GB {th(P.DATA_GB_THRESHOLDS)}", "database choice"),
        ("Database tier", "the higher of the data tier and the compute tier, one lower for read-heavy apps (caches absorb reads)", "database scale ceiling and write-scaling rules"),
        ("Implied answers", "fintech forces strong consistency, and adds Indian data residency when users are in India; realtime collaboration forces realtime to core; mobile-first adds iOS and Android; a DPDP answer is noted as consent and breach duties", "hard constraints and weights, each shown as an assumption or a warning"),
    ]


def appendix_markdown() -> str:
    qs = load_questions()
    inf, quick = influence(), quick_keys()
    out = ["## Appendix B. Question catalogue and traceability", "",
           f"Every question the app asks, generated from `data/questions.json`. The last five columns come from the question-influence study (`tools/question_influence.py`): "
           "the engine was re-run with each other value of one question while every other answer stayed fixed, and a run counts when at least one of the four picks changed. "
           "F, B, D and H are the shares of re-runs in which the frontend, backend, database or hosting pick changed. "
           "The reason each question is asked is in the app (the Why we ask button) and in `data/questions.json`; Appendix E gives it by group.", ""]
    n = 0
    out += ['<div class="appb">', ""]
    for step in qs["steps"]:
        out += [f"### B.{qs['steps'].index(step) + 1} {step['title']}", "",
                "| # | Question | Answer | Quick | Pick changed | F | B | D | H |", "|---|---|---|---|---|---|---|---|---|"]
        for f in step["fields"]:
            n += 1
            x = inf.get(f["key"])
            pc = lambda v: f"{round(100 * v)}%"
            if x:
                cells = [pc(x["pick_change_rate"])] + [pc(x["layer_rates"][l]) for l in ("frontend", "backend", "database", "hosting")]
            else:
                cells = ["names only"] + ["-"] * 4
            label = re.sub(r"\s*\(.*?\)\s*$", "", f["label"])
            out.append(f"| {n} | {label}<br>`{f['key']}` | {_answer(f)} | {'yes' if f['key'] in quick else '-'} | " + " | ".join(cells) + " |")
        out.append("")
        out += [f"*Note:* {NOTES[f['key']](inf[f['key']])}" + chr(10) for f in step["fields"] if f["key"] in NOTES and f["key"] in inf]
    out += ["</div>", "", "### B.6 Quantities derived from the answers", "",
            "| Quantity | How it is computed | Decides |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in derived_rows()]
    out += ["", "Every row above is read from `engine/profile.py`, so the table cannot drift from the engine; `tests/test_questions.py` checks that every question except the project name changes at least one pick, cost or warning in the study."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(appendix_markdown())
