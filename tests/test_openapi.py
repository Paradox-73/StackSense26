"""The interactive API docs (/docs) describe every endpoint and every answer, from data/questions.json."""
from fastapi.testclient import TestClient

from app.main import app
from engine.kb import load_questions

client = TestClient(app)


def _spec():
    return client.get("/openapi.json").json()


def test_every_answer_is_a_documented_property_of_the_recommend_body():
    body = _spec()["paths"]["/api/recommend"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    keys = [f["key"] for s in load_questions()["steps"] for f in s["fields"]]
    assert set(body["properties"]) == set(keys)
    assert len(body["properties"]) == len(keys)
    dau = body["properties"]["dau"]
    assert dau["type"] == "number" and dau["minimum"] == 0 and dau["default"] == 1000
    assert "enum" in body["properties"]["app_type"] and "saas" in body["properties"]["app_type"]["enum"]


def test_every_endpoint_has_a_summary_and_a_description():
    for path, ops in _spec()["paths"].items():
        for method, op in ops.items():
            assert op.get("summary"), (method, path)
            assert op.get("description"), (method, path)


def test_the_recommend_body_has_examples_that_run():
    content = _spec()["paths"]["/api/recommend"]["post"]["requestBody"]["content"]["application/json"]
    assert {"minimal", "startup_mvp", "hipaa_telehealth"} <= set(content["examples"])
    for ex in content["examples"].values():
        assert client.post("/api/recommend", params={"lite": True}, json=ex["value"]).status_code == 200


def test_documented_endpoints_still_answer():
    assert client.post("/api/next", json={"answers": {"dau": 100}}).status_code == 200
    assert client.post("/api/sensitivity", json={"answers": {}, "unknown": ["dau"]}).status_code == 200
    assert client.post("/api/switch", json={"before": {"dau": 100}, "after": {"dau": 1_000_000}}).status_code == 200
