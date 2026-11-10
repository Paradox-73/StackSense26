"""Plain-English what-if and the /api/brief and /api/whatif endpoints. No network."""
from fastapi.testclient import TestClient

from app.main import app
from engine.whatif import propose_changes

client = TestClient(app)


def test_rules_map_numbers_without_a_key_and_skip_unchanged_values():
    r = propose_changes("What if the budget is zero and we are a team of 5, with 1,000 users a day?", {"dau": 1000, "team_size": 3})
    assert r["llm"]["enabled"] is False
    assert r["changes"]["team_size"]["value"] == 5 and r["changes"]["team_size"]["before"] == 3
    assert r["changes"]["budget_monthly"]["value"] == 0
    assert "dau" not in r["changes"]  # same as the current answer


def test_app_type_words_in_a_question_do_not_change_the_project():
    assert "app_type" not in propose_changes("What if we add a payments wallet?", {})["changes"]


def test_model_change_needs_a_valid_value_and_a_real_quote(fake_llm):
    fake = fake_llm({"fields": {
        "dau": {"value": 10000, "quote": "ten times the audience"},
        "seo": {"value": "critical", "quote": "Google ranking"},       # not in the question
        "realtime": {"value": "always", "quote": "ten times"},         # not an allowed value
    }})
    r = propose_changes("What if we had ten times the audience?", {"dau": 1000})
    assert set(r["changes"]) == {"dau"} and r["changes"]["dau"]["before"] == 1000 and r["changes"]["dau"]["source"] == "llm"
    assert {d["field"] for d in r["llm"]["dropped"]} == {"seo", "realtime"}
    assert "current answer: 1000" in fake.calls[0][1]["messages"][1]["content"]


def test_endpoints_validate_input_and_work_without_a_key():
    assert client.post("/api/brief", json={"text": "  "}).status_code == 422
    assert client.post("/api/brief", json={"text": "x" * 5000}).status_code == 422
    assert client.post("/api/whatif", json={"answers": {}}).status_code == 422
    r = client.post("/api/brief", json={"text": "A team of 4 building a blog, 500 visitors per day, $0 budget."})
    body = r.json()
    assert r.status_code == 200 and body["llm"]["enabled"] is False
    assert body["fields"]["team_size"]["value"] == 4 and body["fields"]["dau"]["value"] == 500
    w = client.post("/api/whatif", json={"answers": {"team_size": 2}, "question": "what if team of 6"}).json()
    assert w["changes"]["team_size"]["value"] == 6


def test_health_says_the_llm_is_off_without_a_key():
    assert client.get("/api/health").json()["llm_enabled"] is False


def test_health_says_the_llm_is_on_with_a_key(fake_llm):
    assert client.get("/api/health").json()["llm_enabled"] is True


def test_relative_changes_scale_the_current_answer_without_a_key():
    now = {"dau": 1000, "team_size": 4, "budget_monthly": 50}
    for question, key, value in [
        ("What if we had ten times the users?", "dau", 10000),
        ("what if 10x traffic", "dau", 10000),
        ("What if we had 3 times as many users?", "dau", 3000),
        ("double the team", "team_size", 8),
        ("What if we triple our users", "dau", 3000),
        ("half the budget", "budget_monthly", 25),
    ]:
        change = propose_changes(question, now)["changes"][key]
        assert change["value"] == value and change["source"] == "rule", question
    assert propose_changes("What if nothing changes?", now)["changes"] == {}


def test_the_what_if_box_never_asks_the_model(fake_llm):
    """Statement 5.1 allows a model to read the project description only; what-if questions use the pattern reader."""
    fake = fake_llm({"fields": {"dau": {"value": 10000, "quote": "ten times the audience"}}})
    r = client.post("/api/whatif", json={"answers": {"dau": 1000}, "question": "What if we had ten times the audience?"}).json()
    assert fake.calls == [] and all(c["source"] == "rule" for c in r["changes"].values())
