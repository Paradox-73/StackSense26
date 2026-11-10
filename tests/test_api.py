"""HTTP API smoke tests (FastAPI TestClient)."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_questions_and_presets():
    q = client.get("/api/questions").json()
    assert len(q["steps"]) == 5
    assert sum(len(s["fields"]) for s in q["steps"]) >= 24
    assert len(client.get("/api/presets").json()) >= 8


def test_recommend_preset(presets):
    r = client.post("/api/recommend", json=presets["india_ecommerce_scale"]["input"])
    assert r.status_code == 200
    body = r.json()
    assert body["feasible"] and set(body["stack"]) == {"frontend", "backend", "database", "hosting"}


def test_recommend_empty_body():
    r = client.post("/api/recommend", json={})
    assert r.status_code == 200 and r.json()["feasible"]


def test_markdown_export(presets):
    r = client.post("/api/export/markdown", json=presets["startup_mvp"]["input"])
    assert r.status_code == 200
    assert "## Recommended stack" in r.text and "## What would change the recommendation" in r.text


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200 and "StackSense" in r.text


def test_sensitivity_endpoint():
    r = client.post("/api/sensitivity", json={"answers": {"app_type": "saas"}, "unknown": ["dau", "budget_monthly"]})
    assert r.status_code == 200
    body = r.json()
    assert [f["key"] for f in body["fields"]] == ["dau", "budget_monthly"]
    assert set(body["robust_layers"]) | set(body["depends"]) == {"frontend", "backend", "database", "hosting"}


def test_sensitivity_endpoint_tolerates_bad_payload():
    r = client.post("/api/sensitivity", json={"answers": "nope", "unknown": "dau"})
    assert r.status_code == 200 and r.json()["fields"] == []


def test_glossary_endpoint():
    g = client.get("/api/glossary").json()
    assert "hipaa" in g["terms"] and g["terms"]["hipaa"]["source"].startswith("https://www.hhs.gov")


def test_oversized_request_body_is_rejected_with_413():
    from app.main import MAX_BODY_BYTES
    big = {"answers": {}, "padding": "x" * (MAX_BODY_BYTES + 1)}
    assert client.post("/api/recommend", json=big).status_code == 413
    assert client.post("/api/recommend", json={}).status_code == 200
