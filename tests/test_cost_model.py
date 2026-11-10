"""Cost estimate believability: bills grow with data, users and availability, and usage-billed
services (a BaaS, Firestore, model inference, per-seat hosting) carry their usage terms."""
from copy import deepcopy

import pytest

from engine import recommend
from engine.advice import estimate_cost, supporting_services
from engine.kb import LAYERS, load_kb
from engine.profile import derive, normalize

DATA_GB = [0.1, 1, 5, 20, 80, 300, 1_000, 5_000, 20_000, 80_000]
AVAILABILITY = ["99.0", "99.9", "99.95", "99.99"]


def _cost(raw: dict, stack: dict) -> dict:
    p, a, w = normalize(raw)
    d = derive(p, a, w)
    return estimate_cost(p, d, stack, supporting_services(p, d, stack, []))


def _stack(r: dict) -> dict:
    kb = load_kb()
    return {l: kb["index"][r["stack"][l]["pick"]["id"]] for l in LAYERS}


@pytest.mark.parametrize("pid", ["startup_mvp", "hipaa_telehealth", "student_project", "india_social_mobile",
                                 "realtime_multiplayer", "ml_product"])
def test_cost_monotone_in_data_and_availability(presets, pid):
    raw = deepcopy(presets[pid]["input"])
    stack = _stack(recommend(raw, with_counterfactuals=False))
    prev = (0, 0)
    for gb in DATA_GB:
        c = _cost(dict(raw, data_volume_gb=gb, data_growth_gb_month=0), stack)
        assert (c["total_low"], c["total_high"]) >= prev and c["total_low"] >= prev[0] and c["total_high"] >= prev[1], (gb, c["lines"])
        prev = (c["total_low"], c["total_high"])
    prev = (0, 0)
    for av in AVAILABILITY:
        c = _cost(dict(raw, availability=av), stack)
        assert c["total_low"] >= prev[0] and c["total_high"] >= prev[1], (av, c["lines"])
        prev = (c["total_low"], c["total_high"])


def test_availability_changes_cost_for_self_run_capacity(presets):
    raw = presets["hipaa_telehealth"]["input"]
    stack = _stack(recommend(raw, with_counterfactuals=False))
    assert _cost(dict(raw, availability="99.99"), stack)["total_low"] > _cost(dict(raw, availability="99.0"), stack)["total_low"]


def test_baas_plan_follows_stored_data(presets):
    raw = presets["startup_mvp"]["input"]  # ~14 GB in 12 months: past Supabase Free's 500 MB
    r = recommend(raw, with_counterfactuals=False)
    if r["stack"]["backend"]["pick"]["id"] == "supabase":
        line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Backend"))
        assert line["low"] >= 25
    big = recommend(dict(raw, data_volume_gb=50_000), with_counterfactuals=False)
    assert big["cost"]["total_low"] >= 3000
    assert big["cost"]["status"] != "within"


def test_every_cost_line_states_its_basis(presets):
    for pid, pr in presets.items():
        r = recommend(pr["input"], with_counterfactuals=False)
        if r.get("feasible"):
            assert all(x.get("basis") for x in r["cost"]["lines"]), pid


def test_model_product_has_an_inference_line(presets):
    r = recommend(presets["ml_product"]["input"], with_counterfactuals=False)
    assert any(x["component"].startswith("Model serving") and x["high"] > 0 for x in r["cost"]["lines"])


def test_firestore_bill_grows_with_traffic():
    kb = load_kb()
    stack = {"frontend": kb["index"]["react_native"], "backend": kb["index"]["firebase"],
             "database": kb["index"]["firestore"], "hosting": kb["index"]["vercel"]}
    lows = [_cost({"app_type": "social_network", "platforms": ["android"], "dau": dau}, stack)["total_low"]
            for dau in (10_000, 300_000, 3_000_000)]
    assert lows == sorted(lows) and lows[-1] > lows[0]


def test_vercel_bills_deploying_seats():
    kb = load_kb()
    stack = {"frontend": kb["index"]["nextjs"], "backend": kb["index"]["supabase"],
             "database": kb["index"]["postgres"], "hosting": kb["index"]["vercel"]}
    one = _cost({"team_size": 1, "dau": 3000}, stack)
    five = _cost({"team_size": 5, "dau": 3000}, stack)
    host = lambda c: next(x for x in c["lines"] if x["component"].startswith("Hosting"))["low"]
    assert host(five) - host(one) == 4 * kb["index"]["vercel"]["seat_usd"]


def test_self_managed_sql_server_carries_its_licence():
    # On your own servers SQL Server needs a licence the managed services include: Standard per core, or the free
    # Express edition for a database of at most 10 GB with no failover.
    base = {"app_type": "healthcare", "dau": 5000, "deployment": "on_prem", "team_size": 4,
            "team_skills": ["csharp", "sql"], "existing_systems": ["sqlserver"], "budget_monthly": 5000}
    r = recommend(dict(base, availability="99.9"), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "sqlserver"
    lic = [l for l in r["cost"]["lines"] if l["component"].startswith("Licence")]
    assert lic and lic[0]["low"] == 4 * 73 and "Express" in lic[0]["basis"]
    r = recommend(dict(base, availability="99.0", data_volume_gb=1, data_growth_gb_month=0.1), with_counterfactuals=False)
    assert not any(l["component"].startswith("Licence") for l in r["cost"]["lines"])
    assert "Express edition licence: free" in next(l["basis"] for l in r["cost"]["lines"] if l["component"].startswith("Database"))
    r = recommend(dict(base, deployment="cloud", cloud_preference="azure"), with_counterfactuals=False)
    assert not any(l["component"].startswith("Licence") for l in r["cost"]["lines"])
