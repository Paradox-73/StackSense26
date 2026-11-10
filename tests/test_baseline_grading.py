"""The offline LLM-baseline experiment (tools/llm_baseline.py): a stack named by ids is graded by the rule engine. No
network, and nothing here is part of the engine or the app."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from baseline_grading import describe_answers, engine_pick_ids, grade_stack  # noqa: E402
from engine import recommend  # noqa: E402

# Users sign in and pay, so a static-only host must be ruled out.
ANSWERS = {"app_type": "ecommerce", "platforms": ["web"], "dau": 20000, "budget_monthly": 5000, "currency": "INR"}


def engine_stack():
    s = recommend(ANSWERS, with_counterfactuals=False)["stack"]
    return {l: s[l]["pick"]["id"] for l in s}


def test_engine_stack_graded_by_the_engine_breaks_nothing_and_has_no_gap():
    g = grade_stack(ANSWERS, engine_pick_ids(ANSWERS))
    assert g["ok"] and g["breaks"] == {} and g["gap"] == 0 and g["cost_diff"] == 0 and g["complete"]


def test_a_static_only_host_is_a_hard_break_with_the_engines_reason():
    picks = dict(engine_stack(), hosting="aws_s3_cloudfront")
    g = grade_stack(ANSWERS, picks)
    assert list(g["breaks"]) == ["hosting"] and "read-only" in g["breaks"]["hosting"][0]


def test_inr_budget_is_converted_with_the_engines_rate():
    g = grade_stack(ANSWERS, engine_stack())
    assert g["budget_usd"] == pytest.approx(5000 / 96.0, abs=0.01)


def test_partial_picks_are_graded_but_marked_incomplete():
    g = grade_stack(ANSWERS, {"frontend": engine_stack()["frontend"], "backend": None, "database": None, "hosting": None})
    assert g["ok"] and not g["complete"]
    assert not grade_stack(ANSWERS, {"frontend": None, "backend": None, "database": None, "hosting": None})["ok"]


def test_answers_are_described_in_words():
    text = describe_answers(ANSWERS)
    assert "Monthly infrastructure budget: 5000 INR per month" in text and "Web" in text
