"""The question catalogue (report Appendix B) covers every question, and every question feeds a decision."""
import json
import re
from pathlib import Path

from engine.kb import load_questions

ROOT = Path(__file__).resolve().parent.parent
KEYS = [f["key"] for s in load_questions()["steps"] for f in s["fields"]]


def _study():
    d = json.loads((ROOT / "report" / "question_influence.json").read_text(encoding="utf-8"))
    return {x["key"]: x for x in d["all"]}


def test_every_question_except_the_project_name_changes_something():
    study = _study()
    for key in KEYS:
        if key in ("project_name", "currency"):  # currency is the unit of the budget, not studied
            continue
        assert key in study, f"{key} is missing from the question-influence study"
        assert study[key]["any_effect_rate"] > 0, f"changing {key} never changed a pick, a cost or a warning"


def test_appendix_has_one_row_per_question():
    text = (ROOT / "report" / "inputs_appendix.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| .*?<br>`([a-z_]+)`", text, re.M)
    assert [k for _, k in rows] == KEYS
    assert [int(n) for n, _ in rows] == list(range(1, len(KEYS) + 1))


def test_appendix_lists_the_derived_quantities():
    text = (ROOT / "report" / "inputs_appendix.md").read_text(encoding="utf-8")
    for name in ("Peak requests per second", "Compute tier", "Database tier", "Budget in dollars"):
        assert name in text


def test_quick_mode_marks_match_the_app():
    text = (ROOT / "report" / "inputs_appendix.md").read_text(encoding="utf-8")
    quick = re.findall(r"<br>`([a-z_]+)` \| [^|]* \| yes \|", text)
    for key in ("app_type", "dau", "budget_monthly", "team_size", "team_skills", "compliance", "deployment", "realtime", "offline", "seo", "platforms"):
        assert key in quick, key
    assert "special_workloads" not in quick
