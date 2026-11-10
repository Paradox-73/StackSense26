"""Explanation invariants over 300 seeded random profiles plus the presets.

Each rule is checked on every profile; a failing rule names the first offending profile and layer.
Rules marked xfail describe known defects; strict=True makes them fail loudly once fixed, so the
marker must then be removed.
"""
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from engine import recommend  # noqa: E402
from engine.explain import TIE_MARGIN  # noqa: E402
from engine.recommender import BUDGET_GUARD_POINTS  # noqa: E402
from engine.stack import RETURN_MARGIN  # noqa: E402
from engine.export import to_markdown  # noqa: E402
from engine.kb import LAYERS, load_presets  # noqa: E402
from profiles import profiles  # noqa: E402

SEED, N = 2026, 300
BAD_TEXT = re.compile(r"by -\d|[−-]-\d|because your edited|\b[Aa]n '[BCDGJKPQTVWYZ]|\bNone\b|\bnan\b|\{[a-z_]+\}")


@pytest.fixture(scope="module")
def runs():
    inputs = [(p["id"], p["input"]) for p in load_presets()]
    inputs += [(f"seed{SEED}#{i}", x) for i, x in enumerate(profiles(SEED, N))]
    return [(name, inp, recommend(deepcopy(inp), with_counterfactuals=False)) for name, inp in inputs]


def _layers(runs):
    for name, inp, r in runs:
        if r["feasible"]:
            for l in LAYERS:
                yield name, l, r, r["stack"][l]


def test_every_pick_has_reasons(runs):
    for name, l, r, s in _layers(runs):
        e = s["explanation"]
        assert e["why"] and all(isinstance(x, str) and x.strip() for x in e["why"]), (name, l)


def test_confidence_matches_margin(runs):
    for name, l, r, s in _layers(runs):
        e, vs = s["explanation"], s["explanation"]["vs_runner_up"]
        if vs:
            m = vs["margin"]
            assert e["confidence"] == ("high" if m >= 4 else "medium" if m >= 1.5 else "low"), (name, l, m)


def test_runner_up_text_matches_sign_of_margin(runs):
    for name, l, r, s in _layers(runs):
        vs = s["explanation"]["vs_runner_up"]
        if not vs:
            continue
        if vs["margin"] < 0:
            assert "beats" not in vs["text"], (name, l, vs["text"])
        if abs(vs["margin"]) < TIE_MARGIN:
            assert vs["tie"] and "tie margin" in vs["text"], (name, l, vs["text"])


def test_no_malformed_text(runs):
    for name, inp, r in runs:
        txt = json.dumps({k: r[k] for k in ("summary", "warnings", "stack", "architecture") if k in r}, ensure_ascii=False)
        if r["feasible"]:
            txt += to_markdown(r)
        m = BAD_TEXT.search(txt)
        assert not m, (name, txt[max(0, m.start() - 120): m.end() + 40])


def test_tie_break_text_present_when_top_scorer_not_chosen(runs):
    for name, inp, r in runs:
        tb = r.get("tie_break")
        if tb:
            # A stack that fits the budget may replace one over it from up to BUDGET_GUARD_POINTS lower.
            # A stack that does not go back to a pick the smaller-scale path left may be up to RETURN_MARGIN lower
            # (FORWARD_MARGIN when the path could not hold the earlier pick); the margin used is reported.
            limit = (BUDGET_GUARD_POINTS + TIE_MARGIN if tb.get("budget_guard") else
                     tb["return_margin"] if tb.get("avoided_return") else
                     RETURN_MARGIN if tb["kept_on_growth_path"] else
                     TIE_MARGIN)
            assert tb["margin"] < limit and tb["text"] in r["summary"], name


def test_same_input_same_output(runs):
    for name, inp, r in runs[:40]:
        again = recommend(deepcopy(inp), with_counterfactuals=False)
        assert json.dumps(again, sort_keys=True, default=str) == json.dumps(r, sort_keys=True, default=str), name


def test_contributions_add_up_to_score(runs):
    for name, l, r, s in _layers(runs):
        total = sum(c["points"] for c in s["explanation"]["input_contributions"])
        assert abs(total - s["pick"]["score"]) <= 0.5, (name, l, round(total, 2), s["pick"]["score"])


def test_runner_up_reasons_sum_to_margin(runs):
    for name, l, r, s in _layers(runs):
        vs = s["explanation"]["vs_runner_up"]
        if vs:
            listed = sum(x["points"] for x in vs["favour_pick"]) - sum(x["points"] for x in vs["favour_runner_up"])
            assert abs(listed - vs["margin"]) <= 0.05, (name, l, vs["margin"], round(listed, 2))


def test_alternatives_never_beat_the_top_stack(runs):
    for name, l, r, s in _layers(runs):
        top = max(r["stack_score"], (r.get("tie_break") or {}).get("top_score") or 0)
        for a in s["alternatives"]:
            # stack_score is rounded to 1 decimal; alternatives keep 2
            assert a["stack_score"] <= top + 0.05, (name, l, a["name"], a["stack_score"], top)
