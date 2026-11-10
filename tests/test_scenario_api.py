"""The scenario-file page and its API (FR1, FR2, FR8): the standard schema as form fields, the public example files,
and POST /api/scenario returning the section 4 output, including for bodies that are not valid scenarios."""
import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from engine.standard import FIELD_PATHS, run  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
client = TestClient(app)


def test_the_form_covers_every_standard_field():
    fields = client.get("/api/scenario/fields").json()
    assert [f["path"] for f in fields] == list(FIELD_PATHS)
    assert all(f["help"] for f in fields)
    platforms = next(f for f in fields if f["path"] == "project.platforms")
    assert platforms["required"] and platforms["allowed"] == ["web", "android", "ios", "desktop", "api_only"]


def test_public_examples_are_served_as_they_are_on_disk():
    listed = client.get("/api/scenario/examples").json()
    assert [x["name"] for x in listed if x["group"] == "public"] == ["P1", "P2", "P3", "P4", "P5", "P6"]
    assert [x["name"][:2] for x in listed if x["group"] == "edge"] == [f"E{i}" for i in range(1, 10)]
    on_disk = json.loads((ROOT / "scenarios" / "public" / "P3.json").read_text(encoding="utf-8"))
    assert client.get("/api/scenario/examples/P3").json() == on_disk
    for bad in ("P7", "..%2F..%2Fdata%2Fpresets", "%2E%2E"):
        assert client.get(f"/api/scenario/examples/{bad}").status_code == 404


def test_post_returns_the_engine_output():
    doc = json.loads((ROOT / "scenarios" / "public" / "P2.json").read_text(encoding="utf-8"))
    r = client.post("/api/scenario", json=doc)
    assert r.status_code == 200 and r.json() == run(doc)


@pytest.mark.parametrize("body", ['{"scenario_id": ', "[]", '"text"', "", "null", "[" * 3000, "[" + ", ".join(["{}"] * 101) + "]"])
def test_bodies_that_are_not_scenarios_are_invalid_input_not_errors(body):
    r = client.post("/api/scenario", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "invalid_input" and out["stack"] is None and out["validation_errors"]


def test_an_array_of_scenarios_returns_an_array_of_outputs():
    """The organisers share the public scenarios as one JSON array; each element is run on its own."""
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "scenarios" / "public").glob("P*.json"))]
    r = client.post("/api/scenario", json=docs + [1])
    assert r.status_code == 200 and r.json() == [run(d) for d in docs] + [run(1)]
    assert [o["scenario_id"] for o in r.json()] == ["P1", "P2", "P3", "P4", "P5", "P6", None]


def test_page_is_served_and_health_reports_the_switch(monkeypatch):
    page = client.get("/scenario")
    assert page.status_code == 200 and 'id="sc-form"' in page.text and "/static/scenario.js" in page.text
    assert client.get("/api/health").json()["llm_switched_off"] is False
    monkeypatch.setenv("STACKSENSE_LLM", "off")
    assert client.get("/api/health").json()["llm_switched_off"] is True


def test_edge_examples_show_each_section_6_category():
    """scenarios/edge holds one file per edge-case category of statement section 6; each gives the behaviour the
    statement expects, so the report's screenshots of them show the real engine."""
    def out(stem):
        return client.post("/api/scenario", json=client.get(f"/api/scenario/examples/{stem}").json()).json()
    def codes(o):
        return {w["code"]: w["severity"] for w in o["warnings"]}
    assert codes(out("E1_missing_fields")).get("MISSING_REQUIRED_FIELD") == "warning"
    invalid = out("E2_invalid_values")
    assert invalid["status"] == "invalid_input" and len(invalid["validation_errors"]) >= 6
    assert {"BEGINNER_HIGH_AVAILABILITY", "MANY_PLATFORMS_SHORT_TIMELINE", "BUDGET_INFEASIBLE"} <= set(codes(out("E3_contradictions")))
    static = out("E4_static_at_scale")["stack"]
    assert static["backend"]["choice"] == "None" and static["database"]["choice"] == "None"
    assert "Frankfurt" in out("E5_regulatory")["stack"]["hosting"]["choice"]
    legacy = out("E6_existing_systems")
    assert "EOL_EXISTING_SYSTEM" in codes(legacy) and any(s["choice"].startswith("Okta (existing)") for s in legacy["stack"]["supporting"])
    assert codes(out("E7_air_gapped"))["AIR_GAPPED_EXTERNAL"] == "critical"
    assert out("E8_skill_mismatch")["stack"]["backend"]["choice"] == "PHP + Laravel"
    assert list(codes(out("E9_deprecated"))) == ["EOL_EXISTING_SYSTEM"] and len(out("E9_deprecated")["warnings"]) == 4


def test_the_pages_rupee_lines_use_the_engines_rate():
    import re
    from engine.profile import INR_PER_USD
    for page in ("scenario.js", "app.js"):
        js = (ROOT / "app" / "static" / page).read_text(encoding="utf-8")
        assert float(re.search(r"const FX = ([\d.]+);", js).group(1)) == INR_PER_USD, page
