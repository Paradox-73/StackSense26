"""Vendor free and entry plans: a database is priced from $0 (or a small fixed plan) only while the data
expected within 12 months and the scale tier fit that plan's published limits."""
import json
from copy import deepcopy
from pathlib import Path

from engine import recommend
from engine.kb import load_kb, validate_kb
from engine.profile import derive, normalize
from engine.scoring import entry_plan, tier_cost

KB = load_kb()
PG, MYSQL, MONGO = KB["index"]["postgres"], KB["index"]["mysql"], KB["index"]["mongodb"]
KEY = json.loads((Path(__file__).resolve().parent / "benchmark" / "answer_key.json").read_text(encoding="utf-8"))


def _derived(**answers):
    p, a, w = normalize(answers)
    return p, derive(p, a, w)


def test_free_plan_only_within_its_storage_and_scale():
    p, d = _derived(dau=2000, data_volume_gb=0.1, data_growth_gb_month=0.02)  # ~0.3 GB in 12 months
    assert entry_plan(PG, 1, d)["usd"] == 0
    assert tier_cost(PG, 1, p, d)[0] == 0
    p, d = _derived(dau=2000, data_volume_gb=0.5, data_growth_gb_month=0.5)  # 6.5 GB: past every free plan
    assert entry_plan(PG, 1, d)["name"].startswith("Aiven")
    assert tier_cost(PG, 1, p, d)[0] == 5
    # Medium scale is past every free plan; the paid entry plans that hold it set the band (cheapest to dearest).
    p, d = _derived(dau=20000, data_volume_gb=0.1, data_growth_gb_month=0.0)
    assert entry_plan(PG, 2, d)["name"] == "Supabase Pro + Small compute"
    assert tier_cost(PG, 2, p, d) == (30, 75)
    # Large scale is past every entry plan: the published price band applies.
    p, d = _derived(dau=200000, data_volume_gb=0.1, data_growth_gb_month=0.0)
    assert entry_plan(PG, 3, d) is None
    assert tier_cost(PG, 3, p, d) == tuple(PG["cost_usd"][3])


def test_a_zero_floor_is_not_free_past_every_entry_plan():
    # Hobby scale but ~9.5 GB within a year: no free or entry plan holds it, so the next tier's floor applies.
    p, d = _derived(dau=200, data_volume_gb=8, data_growth_gb_month=0.1)
    assert d["db_tier"] == 0
    assert tier_cost(PG, 0, p, d)[0] == PG["cost_usd"][1][0] > 0
    assert tier_cost(MYSQL, 0, p, d)[0] == MYSQL["cost_usd"][1][0] > 0
    # Without the project's data size (supporting stores), the band is used as published.
    assert tier_cost(PG, 0, p) == tuple(PG["cost_usd"][0])


def test_mongodb_entry_plans():
    p, d = _derived(dau=2000, data_volume_gb=0.2, data_growth_gb_month=0.01)
    assert tier_cost(MONGO, 1, p, d)[0] == 0
    p, d = _derived(dau=2000, data_volume_gb=2, data_growth_gb_month=0.1)
    assert tier_cost(MONGO, 1, p, d)[0] == 8


def test_flyio_and_managed_timescale_have_no_free_plan():
    assert KB["index"]["flyio"]["cost_usd"][0][0] > 0
    assert KB["index"]["timescaledb"]["cost_usd"][0][0] >= 30


def test_campus_chat_bill_uses_the_entry_plan():
    brief = next(b for b in KEY["briefs"] if b["id"] == "A05")
    r = recommend(deepcopy(brief["input"]), with_counterfactuals=False)
    db_line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database"))
    assert r["stack"]["database"]["pick"]["id"] == "postgres"
    # Priced from the plan of the offering the stack names on its host (an Aiven plan is not sold as Railway
    # Postgres). A host offering with no checked plan in the KB (e.g. Render Postgres) is priced from the tier band
    # and says so, rather than borrowing another vendor's cheaper plan.
    plans = KB["index"]["postgres"].get("host_plans", []) + KB["index"]["postgres"]["entry_plans"]
    plan = next((ep for ep in plans if ep["name"] in db_line["basis"]), None)
    if plan:
        assert plan["vendor"] in r["stack"]["database"]["managed_offering"]
        assert db_line["low"] < 15
    else:
        assert "priced as" in db_line["basis"] and db_line["low"] <= 15
    assert r["cost"]["total_low"] <= 30  # the realtime Redis is priced at the app's tier


def test_small_data_project_is_priced_from_the_free_plan():
    r = recommend({"app_type": "saas", "dau": 2000, "budget_monthly": 0, "team_size": 2,
                   "team_skills": ["javascript", "node", "react"], "data_volume_gb": 0.1, "data_growth_gb_month": 0.02},
                  with_counterfactuals=False)
    db_line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database"))
    assert db_line["low"] == 0 and "Free" in db_line["basis"]


def test_entry_plans_are_validated():
    kb = deepcopy(KB)
    kb["database"] = [dict(it) for it in kb["database"]]
    pg = next(it for it in kb["database"] if it["id"] == "postgres")
    pg["entry_plans"] = [dict(pg["entry_plans"][0], source="https://example.com/not-in-sources")]
    assert any("entry plan" in x for x in validate_kb(kb))
    assert validate_kb() == []


def test_medium_scale_is_priced_from_paid_entry_plans_with_disk_billed_per_gb():
    """20k daily users and ~17 GB within a year: Supabase Pro with Small compute holds it ($30 plus 9 GB of disk past
    the 8 GB included at $0.125/GB), so the database is no longer priced from the tier's $50 floor."""
    p, d = _derived(app_type="saas", dau=20000, data_volume_gb=5, data_growth_gb_month=1)
    ep = entry_plan(PG, d["db_tier"], d)
    assert d["db_tier"] == 2 and ep["name"] == "Supabase Pro + Small compute"
    lo, hi = tier_cost(PG, 2, p, d)
    assert lo == 31.12 and hi < PG["cost_usd"][2][1]
    assert tier_cost(MONGO, 2, p, d) == (60, 388)  # band floor is cheaper than Atlas M20; M30 is the dearest plan that holds 20 GB
    # The data is stated: left unanswered, it is estimated from the scale tier (~117 GB at 20k users), past these plans.
    r = recommend({"app_type": "saas", "dau": 20000, "budget_monthly": 5000, "currency": "INR", "team_skills": ["react", "node"],
                   "team_size": 3, "data_volume_gb": 5, "data_growth_gb_month": 1}, with_counterfactuals=False)
    if r["stack"]["database"]["pick"]["id"] == "postgres":
        line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database"))
        assert "Supabase Pro" in line["basis"] and line["low"] < 50
        assert r["cost"]["status"] != "over"
