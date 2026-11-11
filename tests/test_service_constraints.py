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
    if "PowerSync" in sync[0]["name"]:
        assert "BAA" in sync[0]["name"] and "HIPAA" in sync[0]["name"], sync
