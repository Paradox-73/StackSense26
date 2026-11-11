"""Contradictory, missing and extreme inputs must produce a usable answer plus explicit warnings."""
import pytest

import engine.recommender as rec
from engine import recommend
from engine.kb import LAYERS, load_kb


def codes(r):
    return {w["code"] for w in r["warnings"]}


def test_contradictory_preset(presets):
    r = recommend(presets["contradictory"]["input"])
    assert r["feasible"]
    expected = {"MICROSERVICES_SMALL_TEAM", "HIPAA_FREE_TIER", "SLA_SMALL_TEAM", "RPS_DAU_MISMATCH",
                "LATENCY_PHYSICS", "COMPLIANCE_TIMELINE", "SCALE_SMALL_TEAM", "BUDGET_INFEASIBLE"}
    assert expected <= codes(r), expected - codes(r)
    for w in r["warnings"]:
        assert w["resolution"], "every warning states how it was resolved"
    kb = load_kb()
    host = kb["index"][r["stack"]["hosting"]["pick"]["id"]]
    assert host["compliance"]["hipaa"] and "india" in host["regions"], "compliance is never relaxed"
    assert r["architecture"]["style"] == "Modular monolith"
    assert r["cost"]["status"] == "over"


def test_huge_scale_zero_budget():
    r = recommend({"dau": 20_000_000, "budget_monthly": 0, "team_size": 1}, with_counterfactuals=False)
    assert r["feasible"]
    assert "BUDGET_INFEASIBLE" in codes(r)
    assert "SCALE_SMALL_TEAM" in codes(r)


def test_hipaa_free_tier():
    r = recommend({"compliance": ["hipaa"], "budget_monthly": 0}, with_counterfactuals=False)
    assert "HIPAA_FREE_TIER" in codes(r)
    kb = load_kb()
    assert kb["index"][r["stack"]["hosting"]["pick"]["id"]]["compliance"]["hipaa"]


def test_one_dev_microservices():
    r = recommend({"team_size": 1, "architecture": "microservices"}, with_counterfactuals=False)
    assert "MICROSERVICES_SMALL_TEAM" in codes(r)
    # The solo developer is steered away from microservices: a monolith or a managed BaaS backend.
    style = r["architecture"]["style"].lower()
    assert "monolith" in style or "baas" in style
    assert "overridden" in r["architecture"]["why"]


def test_on_prem_serverless_conflict():
    r = recommend({"deployment": "on_prem", "architecture": "serverless", "cloud_preference": "aws"}, with_counterfactuals=False)
    assert {"ONPREM_SERVERLESS", "ONPREM_CLOUD_PREF"} <= codes(r)
    assert load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]]["on_prem"]


def test_missing_everything():
    r = recommend(None)
    assert r["feasible"] and len(r["assumptions"]) >= 10


def test_mobile_only_with_seo():
    r = recommend({"platforms": ["android"], "seo": "important"}, with_counterfactuals=False)
    assert "SEO_NO_WEB" in codes(r)
    assert r["stack"]["frontend"]["pick"]["id"] in ("react_native", "flutter", "native_mobile")


def test_dual_residency_warning():
    r = recommend({"compliance": ["data_residency_eu", "data_residency_india"]}, with_counterfactuals=False)
    assert "DUAL_RESIDENCY" in codes(r)
    regions = set(load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]]["regions"])
    assert {"india", "europe"} <= regions


def test_no_feasible_option(monkeypatch):
    """If every hosting option is removed by hard constraints, the engine says so instead of guessing."""
    kb = load_kb()
    trimmed = dict(kb, hosting=[h for h in kb["hosting"] if not h.get("on_prem")])
    monkeypatch.setattr(rec, "load_kb", lambda: trimmed)
    r = rec.recommend({"deployment": "on_prem"}, with_counterfactuals=False)
    assert r["feasible"] is False
    assert "NO_FEASIBLE_OPTION" in codes(r)


@pytest.mark.parametrize("dau", [0, 1, 999_999_999])
@pytest.mark.parametrize("budget", [0, 1, 10_000_000])
def test_extreme_grid_never_crashes(dau, budget):
    r = recommend({"dau": dau, "budget_monthly": budget}, with_counterfactuals=False)
    assert r["feasible"]
    for l in LAYERS:
        assert 0 <= r["stack"][l]["pick"]["score"] <= 100


def test_numbers_beyond_float_range_do_not_crash():
    from fastapi.testclient import TestClient

    from app.main import app
    from engine.kb import field_specs

    numeric = [k for k, s in field_specs().items() if s["type"] == "number"]
    assert len(numeric) == 9
    body = "{" + ", ".join(f'"{k}": 1{"0" * 400}' for k in numeric) + "}"
    resp = TestClient(app).post("/api/recommend?lite=1", content=body, headers={"content-type": "application/json"})
    assert resp.status_code == 200
    codes = {w["code"] for w in resp.json()["warnings"]}
    assert "INVALID_NUMBER" in codes


# ---- every warning code the engine can raise has a test that triggers it -------------------------------------
@pytest.mark.parametrize("code, answers", [
    ("BUDGET_OVERSIZED", {"dau": 100, "budget_monthly": 50_000}),
    ("TEAM_OVERSIZED", {"dau": 100, "team_size": 300}),
    ("OFFLINE_WEB", {"offline": True, "platforms": ["web"]}),
    ("RESIDENCY_REGION", {"compliance": ["data_residency_india"], "regions": ["europe"]}),
    ("IMPLIED_REALTIME", {"app_type": "realtime_collab", "realtime": "none"}),
    ("IMPLIED_CONSISTENCY", {"app_type": "fintech", "consistency": "eventual_ok"}),
    ("HIPAA_HINT", {"app_type": "healthcare", "regions": ["north_america"], "compliance": []}),
    ("SEO_HINT", {"app_type": "content_site", "seo": "none"}),
    ("VECTOR_HINT", {"app_type": "ml_product", "data_shapes": ["document"]}),
    ("PRIORITIES_TRIMMED", {"priorities": ["cost", "speed", "scale", "proven"]}),
    ("RELAXED_CONSTRAINT", {"data_shapes": ["graph"], "read_write": "write_heavy", "data_growth_gb_month": 1543, "dau": 264}),
])
def test_each_remaining_warning_code_is_raised(code, answers):
    r = recommend(answers, with_counterfactuals=False)
    hit = [w for w in r["warnings"] if w["code"] == code]
    assert hit, (code, sorted(codes(r)))
    assert hit[0]["resolution"], "every warning states how it was resolved"


def test_every_warning_code_in_the_engine_is_tested():
    """A new _warn("CODE", ...) in engine/ must come with a test that names the code."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    emitted = set()
    for f in (root / "engine").glob("*.py"):
        emitted |= set(re.findall(r'_warn\(\s*"([A-Z][A-Z0-9_]+)"', f.read_text(encoding="utf-8")))
    tested = "".join(f.read_text(encoding="utf-8") for f in (root / "tests").glob("test_*.py"))
    untested = sorted(c for c in emitted if c not in tested)
    assert not untested, untested


def scenario(**sections) -> dict:
    """Public scenario P3 run through the standard adapter, with some sections edited."""
    import json
    from pathlib import Path

    from engine.standard import run
    doc = json.loads((Path(__file__).resolve().parent.parent / "scenarios" / "public" / "P3.json").read_text(encoding="utf-8"))
    for sec, values in sections.items():
        doc[sec].update(values)
    return run(doc)


def severities(out: dict) -> dict:
    return {w["code"]: w["severity"] for w in out["warnings"]}


def test_concurrency_above_the_user_count_is_a_critical_contradiction():
    out = scenario(scale={"users_at_launch": 1000, "users_12_months": 10000, "peak_concurrent_users": 50000})
    assert severities(out).get("CONCURRENT_ABOVE_USERS") == "critical" and out["status"] == "ok_with_warnings"
    assert any(a.startswith("Relaxed: scale.peak_concurrent_users 50,000 capped at the user count, 10,000")
               for a in out["assumptions"]), out["assumptions"]
    assert "CONCURRENT_ABOVE_USERS" not in severities(scenario())


def test_api_only_with_offline_and_seo_is_relaxed_and_gets_no_client_parts():
    out = scenario(project={"type": "api_platform", "platforms": ["api_only"]},
                   requirements={"offline_support": True, "seo_critical": True})
    found = severities(out)
    assert found.get("API_ONLY_CLIENT_REQUIREMENT") == "critical", found
    assert "OFFLINE_WEB" not in found and "SEO_NO_WEB" not in found, found
    parts = [s["choice"] for s in out["stack"]["supporting"]]
    assert not [c for c in parts if "SQLite" in c or "sync" in c.lower()], parts


def test_seo_on_a_network_without_the_internet_is_a_contradiction():
    gapped = scenario(infrastructure={"deployment_model": "air_gapped", "cloud_preference": "none"},
                      requirements={"seo_critical": True})
    assert severities(gapped).get("SEO_RESTRICTED_DEPLOYMENT") == "critical"
    assert any("requirements.seo_critical true treated as false" in a for a in gapped["assumptions"])
    on_prem = scenario(infrastructure={"deployment_model": "on_premise", "cloud_preference": "none"},
                       requirements={"seo_critical": True})
    assert severities(on_prem).get("SEO_RESTRICTED_DEPLOYMENT") == "warning"
