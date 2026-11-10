"""Second opinion: the model's own stack graded by the rule engine, and the /api/second-opinion endpoint. No network."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from engine import recommend  # noqa: E402
from engine.second_opinion import describe_answers, engine_pick_ids, grade_stack, second_opinion  # noqa: E402

client = TestClient(app)
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


def test_without_a_key_there_is_no_second_opinion():
    r = second_opinion(ANSWERS)
    assert r["ok"] is False and r["enabled"] is False and "no API key" in r["note"]


def test_same_stack_agrees_on_every_layer(fake_llm):
    fake_llm(engine_stack())
    r = second_opinion(ANSWERS)
    assert r["ok"] and all(v["agree"] for v in r["layers"].values()) and r["breaks"] == [] and r["gap"] == 0
    assert "same stack" in r["summary"]


def test_a_stack_with_a_ruled_out_host_gets_a_plain_verdict(fake_llm):
    fake_llm(dict(engine_stack(), hosting="aws_s3_cloudfront"))
    r = second_opinion(ANSWERS)
    host = r["layers"]["hosting"]
    assert not host["agree"] and host["ruled_out"] and host["engine_reason"]
    assert "the engine rules it out: Only for read-only sites" in host["verdict"]
    assert len(r["breaks"]) == 1 and "hard requirement" in r["summary"] and r["cost"]["engine_low"] == r["cost"]["model_low"] - r["cost"]["difference"]


def test_invalid_ids_are_dropped_and_nothing_valid_is_a_note(fake_llm):
    fake_llm({"frontend": "x", "backend": "y", "database": "z", "hosting": "w"})
    r = second_opinion(ANSWERS)
    assert r["ok"] is False and "no technology" in r["note"]


def test_model_failure_is_reported_not_raised(fake_llm):
    fake_llm((429, {}))
    r = second_opinion(ANSWERS)
    assert r["ok"] is False and r["enabled"] is True and "did not answer" in r["note"]


def test_endpoint_without_a_key():
    off = client.post("/api/second-opinion", json=ANSWERS)
    assert off.status_code == 200 and off.json()["enabled"] is False and off.json()["ok"] is False


def test_endpoint(fake_llm):
    fake_llm(dict(engine_stack(), hosting="aws_s3_cloudfront"))
    r = client.post("/api/second-opinion", json=ANSWERS).json()
    assert r["ok"] and set(r["layers"]) == {"frontend", "backend", "database", "hosting"}
    assert r["model_stack"]["hosting"] == "aws_s3_cloudfront" and r["engine_stack"] == engine_stack()
    assert any("rules it out" in v for v in r["verdicts"])
