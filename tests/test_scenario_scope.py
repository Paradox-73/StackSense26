"""What a scenario's own answers leave out stays out: an availability target nobody stated adds no standby, a zero budget
or a solo beginner gets no paid analytics store it did not ask for, a budget no stack fits is named as relaxed, a
residency rule keeps personal files private but lets a CDN carry public ones, and warnings or lines that do not apply
to the deployment are not shown."""
import copy
import json
from pathlib import Path

from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent


def _doc(folder: str, name: str, **sections) -> dict:
    doc = copy.deepcopy(json.loads((ROOT / "scenarios" / folder / f"{name}.json").read_text(encoding="utf-8")))
    for sec, fields in sections.items():
        doc[sec].update(fields)
    return doc


def _sup(out: dict, layer: str) -> list[dict]:
    return [s for s in out["stack"]["supporting"] if s["layer"] == layer]


def test_an_unstated_availability_target_on_a_solo_on_prem_project_plans_one_database_server():
    doc = _doc("edge", "E7_air_gapped", team={"size": 1})
    doc["requirements"].pop("availability")
    out = run(doc)
    db = out["stack"]["database"]["choice"]
    assert "one server" in db and "Patroni" not in db, db
    assert any(a.startswith("requirements.availability not given and the project is small") for a in out["assumptions"])
    assert not [a for a in out["estimated_monthly_cost_usd"]["assumptions"] if "a standby server" in a]
    doc["requirements"]["availability"] = "99.9"  # a stated target keeps the replica with automated failover
    assert "Patroni" in run(doc)["stack"]["database"]["choice"]


def test_own_servers_get_no_free_tier_sla_warning():
    out = run(_doc("edge", "E7_air_gapped", budget={"monthly_infra_usd": 0}))
    assert "FREE_TIER_NO_SLA" not in [w["code"] for w in out["warnings"]]


def test_a_zero_budget_defers_an_analytics_store_it_did_not_ask_for():
    doc = _doc("public", "P3", project={"type": "social"}, budget={"monthly_infra_usd": 0},
               scale={"users_at_launch": 50000, "users_12_months": 2000000, "peak_concurrent_users": 100000})
    out = run(doc)
    assert not [s for s in out["stack"]["supporting"] if "ClickHouse" in s["choice"] or "BigQuery" in s["choice"]]
    held = [a for a in out["assumptions"] if a.startswith("Deferred: Analytics")]
    assert held and "a zero budget" in held[0] and "reports run on" in held[0], out["assumptions"]
    doc["project"]["type"] = "data_analytics"  # analytics is what the project is for: the store stays
    assert not [a for a in run(doc)["assumptions"] if "a zero budget should not" in a]


def test_a_budget_no_stack_fits_is_named_as_the_relaxed_constraint():
    out = run(_doc("edge", "E3_contradictions"))
    codes = [w["code"] for w in out["warnings"]]
    assert out["status"] == "ok_with_warnings" and "BUDGET_INFEASIBLE" in codes
    cost = out["estimated_monthly_cost_usd"]
    relaxed = [a for a in out["assumptions"] if a.startswith("Relaxed: budget")]
    assert relaxed and f"${cost['min']:,}-{cost['max']:,} a month against your $0" in relaxed[0], out["assumptions"]
    assert "a relaxed recommendation over your $0 budget" in out["summary"], out["summary"]


def test_residency_keeps_a_cdn_for_public_files_and_personal_files_private():
    out = run(_doc("public", "P5", project={"type": "ecommerce"}, requirements={"seo_critical": True}))
    cdn = [s["choice"] for s in _sup(out, "cdn")]
    assert cdn and "Front Door" in cdn[0] and "public, non-personal files only" in cdn[0], cdn
    store = [s["choice"] for s in _sup(out, "storage")]
    assert store and "private container" in store[0] and "SAS" in store[0], store
    assert not [s for s in out["stack"]["supporting"] if "no public Microsoft page" in s["choice"]]


def test_an_air_gapped_site_names_no_host_analytics_and_no_seo_hint_for_seo_it_turned_off():
    out = run(_doc("public", "P1", infrastructure={"deployment_model": "air_gapped", "cloud_preference": "none"}))
    codes = [w["code"] for w in out["warnings"]]
    assert "SEO_RESTRICTED_DEPLOYMENT" in codes and "SEO_HINT" not in codes, codes
    assert not [s for s in out["stack"]["supporting"] if "host's web analytics" in s["choice"]]


def test_sign_in_choice_is_a_product_name_and_the_price_is_a_reason():
    out = run(_doc("public", "P4"))
    auth = _sup(out, "auth")[0]
    assert "would cost" not in auth["choice"] and "Amazon Cognito would cost about" in auth["justification"], auth
    assert not [s for s in out["stack"]["supporting"] if "expected at 12 months" in s["justification"]]
    social = _sup(run(_doc("public", "P3", requirements={"auth": "social"})), "auth")[0]
    assert "product or framework library" in social["justification"], social
