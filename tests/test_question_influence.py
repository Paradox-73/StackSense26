"""The question-influence study: repeatable, and the app's 'Not sure' order is the measured order."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import question_influence as qi  # noqa: E402


def test_study_is_repeatable_on_one_project():
    base = qi._preset_bases()[5]
    assert qi.study_base(base) == qi.study_base(base)


def test_special_workloads_count_their_full_cost():
    """The study prices the whole bill (supporting services included), so a workload that adds a video or SMS
    service moves the measured cost even when the four picks stay the same."""
    base = dict(qi._preset_bases()[0], special_workloads=[])
    ref = qi.recommend(base)
    vod = qi.recommend(dict(base, special_workloads=["video_on_demand"]))
    assert vod["cost"] > ref["cost"] * (1 + qi.COST_MOVE)


def test_every_question_is_measured_and_none_is_empty():
    res = json.loads((ROOT / "report" / "question_influence.json").read_text(encoding="utf-8"))
    keys = [r["key"] for r in res["all"]]
    assert sorted(keys) == sorted(qi.QUESTIONS)
    assert all(r["runs"] > 0 for r in res["all"])
    # Over the full sample every question changes a pick at least sometimes.
    assert all(r["pick_change_rate"] > 0 for r in res["all"])


def test_not_sure_order_in_the_app_is_the_measured_order():
    res = json.loads((ROOT / "report" / "question_influence.json").read_text(encoding="utf-8"))
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    m = re.search(r"const UNKNOWN_ORDER = \[(.*?)\];", js, re.S)
    order = re.findall(r'"([a-z_0-9]+)"', m.group(1))
    assert order == [r["key"] for r in res["all"]]


def test_report_quotes_the_measured_team_skills_rate():
    res = json.loads((ROOT / "report" / "question_influence.json").read_text(encoding="utf-8"))
    rate = round(100 * next(r for r in res["all"] if r["key"] == "team_skills")["pick_change_rate"])
    text = (ROOT / "report" / "report.md").read_text(encoding="utf-8")
    assert f"Team skills changed a pick in {rate}%" in text
    assert "move the result most" not in text


def test_currency_is_not_a_question_about_the_project():
    """Currency is the unit of the budget: it is left out of the study and of ask-next."""
    from engine.sensitivity import next_questions
    assert "currency" not in qi.QUESTIONS
    out = next_questions({"app_type": "saas", "budget_monthly": 100})
    keys = [r["key"] for r in out["ranked"]] + [r["key"] for r in out["settled_questions"]]
    assert "currency" not in keys and "dau" in keys
