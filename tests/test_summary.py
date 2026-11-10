"""Grounded summary: facts, the technology and number validator, retry, fallback. No network."""
import pytest

from engine import recommend
from engine.summary import build_facts, numbers_in, summarize, validate

ANSWERS = {"app_type": "ecommerce", "dau": 20000, "budget_monthly": 5000, "currency": "INR"}


@pytest.fixture(scope="module")
def result():
    return recommend(ANSWERS, with_counterfactuals=False)


def good_text(result):
    """Model output that only uses names and numbers from the engine's result."""
    s = result["stack"]
    names = {l: s[l]["pick"]["name"] for l in s}
    layers = {l: f"{names[l]} is the {l} pick, scored {s[l]['pick']['score']} out of 100." for l in s}
    cost = result["cost"]
    return {"layers": layers, "overall": f"The stack is {' + '.join(names.values())}. "
                                         f"It costs about ${cost['total_low']:g} to ${cost['total_high']:g} a month."}


def test_facts_hold_the_engine_decisions(result):
    f = build_facts(result)
    assert f["layers"]["frontend"]["pick"] == result["stack"]["frontend"]["pick"]["name"]
    assert f["cost_per_month_usd"]["low"] == result["cost"]["total_low"] and f["project"]["daily_users"] == 20000
    assert set(f["layers"]["database"]) >= {"main_reasons", "rejected_alternatives", "ruled_out", "runner_up", "risks"}


def test_number_formats_read_as_the_same_number():
    assert numbers_in("1,000 and 1k and 1000.0 and $25 and ₹5,000 and 2.5M") == {1000.0, 25.0, 5000.0, 2500000.0}


def test_validator_accepts_text_made_of_facts(result):
    facts = build_facts(result)
    text = good_text(result)
    assert validate({**text["layers"], "overall": text["overall"]}, facts) == []
    assert validate({"overall": f"20,000 daily users, or 20k, at ${result['cost']['total_low']:g}."}, facts) == []


def test_validator_rejects_an_invented_technology(result):
    errors = validate({"backend": "Use Ruby on Rails and Heroku."}, build_facts(result))
    assert any("Ruby on Rails" in e for e in errors)


def test_validator_rejects_an_invented_number(result):
    errors = validate({"overall": "It will serve 4,321 users and cost $9,999 a month."}, build_facts(result))
    assert any("4321" in e for e in errors) and any("9999" in e for e in errors)


def test_no_key_returns_the_template(result):
    out = summarize(result)
    assert out["source"] == "template" and out["checked"] is False and out["llm_enabled"] is False
    assert out["layers"]["frontend"] == result["stack"]["frontend"]["explanation"]["paragraph"]
    assert out["overall"] == result["summary"]


def test_valid_model_text_is_marked_checked(fake_llm, result):
    fake_llm(good_text(result))
    out = summarize(result)
    assert out["source"] == "llm" and out["checked"] and out["attempts"] == 1 and out["model"] == "model/a:free"
    assert out["layers"]["hosting"].startswith(result["stack"]["hosting"]["pick"]["name"])


def test_one_retry_with_the_errors_then_accept(fake_llm, result):
    bad = good_text(result)
    bad["overall"] = "Use Ruby on Rails for 77777 users."
    fake = fake_llm(bad, good_text(result))
    out = summarize(result)
    assert out["source"] == "llm" and out["checked"] and out["attempts"] == 2
    retry_prompt = fake.calls[1][1]["messages"][-1]["content"]
    assert "Ruby on Rails" in retry_prompt and "77777" in retry_prompt


def test_two_failures_fall_back_to_the_template(fake_llm, result):
    bad = good_text(result)
    bad["layers"]["database"] = "Cassandra with 424242 nodes."
    fake_llm(bad)
    out = summarize(result)
    assert out["source"] == "template" and not out["checked"] and out["attempts"] == 2
    assert out["errors"] and out["layers"]["database"] == result["stack"]["database"]["explanation"]["paragraph"]


def test_wrong_shape_and_model_outage_fall_back(fake_llm, result):
    fake_llm({"overall": "only this"})
    assert summarize(result)["source"] == "template"
    fake_llm((503, {}))
    out = summarize(result)
    assert out["source"] == "template" and out["errors"]


def test_summary_endpoint_without_a_key():
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).post("/api/summary", json=ANSWERS)
    assert r.status_code == 200 and r.json()["source"] == "template" and r.json()["llm_enabled"] is False


def test_summary_endpoint_with_a_key(fake_llm):
    from fastapi.testclient import TestClient
    from app.main import app
    fake_llm(good_text(recommend(ANSWERS, with_counterfactuals=False)))
    assert TestClient(app).post("/api/summary", json=ANSWERS).json()["checked"] is True
