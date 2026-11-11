"""Supporting services obey the same hard constraints as the four picks: residency keeps SMS and uploads in the
country, HIPAA and residency keep uploads out of public CDNs, and a third-party database offering without an
attestation the project needs gives way to running the database on the chosen cloud."""
import json
from pathlib import Path

from engine import recommend
from engine.advice import database_offering
from engine.kb import load_kb
from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent


def _public(name: str) -> dict:
    return run(json.loads((ROOT / "scenarios" / "public" / f"{name}.json").read_text(encoding="utf-8")))


def _choices(out: dict) -> list[str]:
    return [s["choice"] for s in out["stack"]["supporting"]]


def test_sms_under_india_residency_is_sent_by_an_india_stored_gateway():
    out = _public("P2")  # phone sign-in, data_residency india
    sms = [s for s in out["stack"]["supporting"] if "SMS" in s["choice"] or "MSG91" in s["choice"]]
    assert sms and sms[0]["choice"].startswith("MSG91") and "Twilio" not in sms[0]["choice"], _choices(out)
    assert "outside India" in sms[0]["justification"] and sms[0]["source"] == "https://msg91.com/pdf/sar.pdf"


def test_uploads_under_rbi_localisation_stay_in_a_private_bucket():
    out = _public("P4")  # KYC uploads, rbi_localisation
    store = [s for s in out["stack"]["supporting"] if s["layer"] == "storage"]
    assert store and "private bucket" in store[0]["choice"] and "CloudFront" not in store[0]["choice"], _choices(out)
    assert not [c for c in _choices(out) if "uploaded files" in c and "CloudFront" in c], _choices(out)
    assert any("signed URLs" in c and "no public CDN" in c for c in _choices(out)), _choices(out)


def test_a_third_party_offering_without_iso_27001_gives_way_to_self_managed():
    kb = load_kb()
    timescale, ecs = kb["index"]["timescaledb"], kb["index"]["aws_ecs"]
    plain = {"compliance": [], "deployment": "cloud", "cloud_preference": "aws"}
    assert "Timescale Cloud" in database_offering(timescale, ecs, plain)
    strict = database_offering(timescale, ecs, dict(plain, compliance=["iso27001"]))
    assert "Timescale Cloud publishes no ISO/IEC 27001" in strict and strict.startswith("Self-managed"), strict


def test_offline_sync_under_hipaa_names_the_plan_and_the_baa():
    r = recommend({"app_type": "healthcare", "platforms": ["android", "ios"], "offline": True, "compliance": ["hipaa"],
                   "regions": ["north_america"], "dau": 2000})
    sync = [s for s in r["supporting_services"] if s["role"] == "Offline sync"]
    assert sync and "ElectricSQL" not in sync[0]["name"], sync
    assert "PowerSync" in sync[0]["name"] and "BAA" in sync[0]["name"] and "HIPAA" in sync[0]["name"], sync


def test_hipaa_in_india_without_a_devops_team_keeps_sign_in_in_india():
    from engine.advice import _auth
    env = {"onprem": False, "self_managed": False, "hybrid": False, "air_gapped": False, "hipaa": True, "india": True,
           "eu": False, "us": False, "cloud": None, "no_hyperscaler": True}
    p = {"enterprise_sso": False, "tenancy": "single", "has_devops": False}
    name = _auth(env, p, {"budget_usd": 500}, {"id": "express"})[0]
    assert "Auth0" not in name and "India" in name, name  # Auth0 keeps no data in India


def test_teams_on_their_own_servers_run_their_search_engine():
    doc = json.loads((ROOT / "scenarios" / "public" / "P3.json").read_text(encoding="utf-8"))
    doc["infrastructure"].update(cloud_preference="none", deployment_model="self_hosted_cloud_vm")
    doc["requirements"]["full_text_search"] = True
    search = [s["choice"] for s in run(doc)["stack"]["supporting"] if s["layer"] == "search"]
    assert search and not [s for s in search if "Cloud" in s], search


def test_phone_codes_beside_a_backend_as_a_service_are_not_cognitos():
    from engine.advice import supporting_services
    from engine.profile import derive, normalize
    kb = load_kb()["index"]
    p, a, w = normalize({"app_type": "mobile_first", "platforms": ["android"], "special_workloads": ["phone_otp"],
                         "dau": 2000})
    d = derive(p, a, w)
    stack = {"frontend": kb["react_native"], "backend": kb["supabase"], "database": kb["postgres"],
             "hosting": kb["aws_s3_cloudfront"]}
    sms = [s["name"] for s in supporting_services(p, d, stack, []) if s["role"] == "Phone login (SMS OTP)"]
    assert sms and "Cognito" not in sms[0], sms
