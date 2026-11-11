"""A site whose visitors only read stays static at any size: no backend and no database, media past ~5 GB in object
storage, a static host kept above its SLA with a warning, and a compliant app host on the cloud when the cloud's
static hosts lack an attestation the project needs."""
import json
from pathlib import Path

from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent


def _site(gb: float = 1, cloud: str = "any", availability: str = "99", compliance=(), budget: float = 0) -> dict:
    doc = json.loads((ROOT / "scenarios" / "public" / "P1.json").read_text(encoding="utf-8"))
    doc["scale"]["data_volume_gb_12_months"] = gb
    doc["infrastructure"]["cloud_preference"] = cloud
    doc["requirements"]["availability"] = availability
    doc["compliance"] = list(compliance)
    doc["budget"]["monthly_infra_usd"] = budget
    return run(doc)


def _picks(out: dict) -> dict:
    return {l: out["stack"][l]["choice"] for l in ("frontend", "backend", "database", "hosting")}


def test_a_large_read_only_site_keeps_no_backend_and_no_database():
    out = _site(gb=40, budget=50)
    picks = _picks(out)
    assert picks["backend"] == "None" and picks["database"] == "None", picks
    media = [s for s in out["stack"]["supporting"] if s["layer"] == "storage"]
    assert media and "media" in media[0]["choice"], media
    assert any(a.startswith("Object storage") and "~40 GB" in a for a in out["estimated_monthly_cost_usd"]["assumptions"])


def test_a_static_host_below_the_target_is_kept_with_a_warning():
    out = _site(gb=2, cloud="aws", availability="99.95", budget=500)
    picks = _picks(out)
    assert picks["backend"] == "None" and "S3 + CloudFront" in picks["hosting"], picks
    gap = [w for w in out["warnings"] if w["code"] == "STATIC_HOST_SLA_GAP"]
    assert gap and "99.9%" in gap[0]["message"] and "requirements.availability" in gap[0]["fields"], out["warnings"]


def test_a_compliant_read_only_site_is_served_by_a_compliant_host_on_its_cloud():
    out = _site(gb=40, cloud="azure", compliance=("soc2", "iso27001"), budget=500)
    picks = _picks(out)
    assert picks["backend"] == "None" and picks["database"] == "None", picks
    assert "App Service" in picks["hosting"], picks
    assert not [w for w in out["warnings"] if w["severity"] == "critical"], out["warnings"]


def test_a_host_with_no_published_sla_gets_an_info_warning_for_a_stated_target():
    out = run(json.loads((ROOT / "scenarios" / "public" / "P3.json").read_text(encoding="utf-8")))  # Fly.io at 99.9%
    assert out["stack"]["hosting"]["choice"].startswith("Fly.io"), out["stack"]["hosting"]["choice"]
    sla = [w for w in out["warnings"] if w["code"] == "NO_PUBLISHED_SLA"]
    assert sla and sla[0]["severity"] == "info" and "requirements.availability" in sla[0]["fields"], out["warnings"]
    free = _site(budget=0)  # a $0 budget is on free plans, which FREE_TIER_NO_SLA already covers
    assert not [w for w in free["warnings"] if w["code"] == "NO_PUBLISHED_SLA"], free["warnings"]


def test_a_large_static_site_is_held_to_its_hosts_static_residency_and_its_media_stay_public():
    out = _site(gb=40, budget=50)
    doc = json.loads((ROOT / "scenarios" / "public" / "P1.json").read_text(encoding="utf-8"))
    doc["scale"]["data_volume_gb_12_months"] = 40
    doc["infrastructure"]["data_residency"] = "eu"
    doc["budget"]["monthly_infra_usd"] = 50
    eu = run(doc)
    host = eu["stack"]["hosting"]["choice"] if eu.get("stack") else ""
    for global_cdn in ("Netlify", "Vercel", "Render", "Firebase Hosting", "Azure Static Web Apps"):
        assert not host.startswith(global_cdn), host  # their static files sit on CDN edges outside the EU
    media = [s["choice"] for s in (eu.get("stack") or {}).get("supporting", []) if s["layer"] == "storage"]
    assert not [m for m in media if "signed URL" in m], media  # a static site has no backend to sign URLs
    assert out["stack"]["backend"]["choice"] == "None"


def test_no_sla_warning_names_only_a_host_that_runs_the_app():
    from engine import recommend
    r = recommend({"app_type": "mobile_first", "platforms": ["android", "ios"], "dau": 2000, "availability": "99.9",
                   "budget_monthly": 300, "team_skills": ["javascript", "firebase"]}, with_counterfactuals=False)
    if r["stack"]["backend"]["pick"].get("kind") == "baas":
        assert not [w for w in r["warnings"] if w["code"] == "NO_PUBLISHED_SLA"], r["warnings"]


def test_a_large_static_site_says_where_its_media_live():
    db = _site(gb=40, budget=50)["stack"]["database"]
    assert db["choice"] == "None" and "object storage" in db["justification"], db["justification"]
