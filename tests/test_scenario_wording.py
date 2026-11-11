"""Wording of the section 4 output: no pointer to a note the file lacks, no comparison of equal values, no raw
penalty numbers, and statements that match what the scenario said."""
import json
import re
from pathlib import Path

import pytest

from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent


def load(name: str) -> dict:
    return json.loads((ROOT / "scenarios" / "public" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def outs() -> dict:
    return {f"P{i}": run(load(f"P{i}")) for i in range(1, 7)}


def texts(out: dict):
    stack = out["stack"]
    for c in [stack[l] for l in ("frontend", "backend", "database", "hosting")] + stack["supporting"]:
        yield c["choice"]
        yield c["justification"]
        yield from (a["why_not"] for a in c["alternatives"])
        yield from c["tradeoffs"]
    yield from (w["message"] for w in out["warnings"])
    yield from out["assumptions"]


def found(outs: dict, pattern: str) -> list[str]:
    return [t for o in outs.values() for t in texts(o) if re.search(pattern, t)]


def test_no_pointer_to_a_runner_up_note(outs):
    assert not found(outs, r"runner-up note")


def test_no_stronger_on_between_equal_values(outs):
    assert not found(outs, r"\((\d+\.\d) vs \1\)")


def test_no_raw_penalty_numbers(outs):
    assert not found(outs, r"\([-+]\d+(\.\d+)?\)")


def test_assumed_consistency_is_said_to_be_assumed(outs):
    static = outs["P1"]["stack"]["database"]["justification"]
    assert "strong consistency" not in static.lower() and "read after a write" not in static, static
    assumed = outs["P2"]["stack"]["database"]["justification"]
    assert "Strong consistency is assumed" in assumed and "You need strong consistency" not in assumed, assumed


def test_a_project_of_type_other_is_not_called_a_consumer_app(outs):
    assert "consumer" not in outs["P6"]["stack"]["frontend"]["justification"]


def test_a_kept_pick_says_why_when_the_runner_up_scores_higher(outs):
    alt = next(a["why_not"] for a in outs["P4"]["stack"]["frontend"]["alternatives"] if a["choice"] == "Angular")
    assert "points higher" in alt and re.search(r"the tie went to React SPA|stays as part of the stack", alt), alt
    tie = outs["P4"]["stack"]["frontend"]["justification"]
    assert "Angular is within" in tie and re.search(r"tie went to React SPA|stays as part of the stack", tie), tie


def test_the_latency_default_is_stated_once(outs):
    for name in ("P1", "P6"):
        hits = [a for a in outs[name]["assumptions"] if "How fast must the app answer" in a or "p95_latency_ms" in a]
        assert len(hits) == 1, hits


def test_rds_proxy_is_named_only_for_functions(outs):
    assert "RDS Proxy" not in outs["P4"]["stack"]["database"]["choice"], outs["P4"]["stack"]["database"]["choice"]


def test_a_large_gap_names_the_rule_that_makes_it(outs):
    alt = next(a["why_not"] for a in outs["P1"]["stack"]["frontend"]["alternatives"] if "HTMX" in a["choice"])
    gap = float(re.search(r"lowers the stack score by (\d+\.\d) points", alt).group(1))
    rule = re.search(r"A stack compatibility rule costs it (\d+\.\d) points, more than the whole gap, while on this "
                     r"layer's own criteria it is (\d+\.\d) points ahead: HTMX needs a server", alt)
    assert gap > 5 and rule and abs(float(rule.group(1)) - float(rule.group(2)) - gap) < 0.11, alt


@pytest.mark.parametrize("platforms,languages,native", [(["android"], ["javascript", "python"], None),
                                                        (["ios"], ["swift"], "Native iOS (Swift)"),
                                                        (["android"], ["kotlin"], "Native Android (Kotlin)")])
def test_one_phone_platform_is_one_app(platforms, languages, native):
    doc = load("P6")
    doc["project"]["platforms"], doc["team"]["languages"] = platforms, languages
    out = run(doc)
    front = out["stack"]["frontend"]
    words = " ".join([front["choice"], front["justification"], out["stack"]["hosting"]["justification"]])
    assert "iOS + Android" not in words and "both the iOS and the Android" not in words, words
    assert "on iOS and Android" not in words and "two codebases" not in words, words
    if native:
        assert front["choice"] == native, front["choice"]


def test_backend_states_the_team_language_and_its_skill_score(outs):
    for name in ("P2", "P3", "P4", "P5", "P6"):
        text = outs[name]["stack"]["backend"]["justification"]
        assert re.search(r"The team lists .+ \(team skill match \d\.\d/5\)", text), (name, text)
    p5 = outs["P5"]["stack"]["backend"]["justification"]
    assert "C#" in p5 and "Entra ID" in p5 and "SQL Server" in p5, p5
    for name in ("P4", "P5", "P6"):  # realtime is false in all three
        assert "WebSockets" not in outs[name]["stack"]["backend"]["justification"], name


def test_counts_are_worded_as_singular_or_plural():
    out = run(dict(load("P1"), timeline={"mvp_weeks": 1}, project=dict(load("P1")["project"], platforms=["web", "android", "ios"])))
    assert not found({"x": out}, r"\(s\)"), found({"x": out}, r"\(s\)")
    assert any("1 week is not enough to ship all of them with 1 engineer." in t for t in texts(out))
