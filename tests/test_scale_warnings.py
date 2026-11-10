"""Architect warnings that need the picks: a single-primary relational database past ~10 TB needs a sharding plan,
and a sub-100 ms target for users on several continents cannot be met from one region."""
from engine import recommend


def codes(r):
    return {w["code"] for w in r["warnings"]}


def test_big_relational_primary_gets_a_sharding_warning():
    r = recommend({"app_type": "ecommerce", "dau": 300_000, "data_volume_gb": 9_000, "data_growth_gb_month": 300,
                   "data_shapes": ["relational"], "budget_monthly": 25_000, "team_size": 12},
                  with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] in ("postgres", "mysql", "sqlserver")
    w = next(w for w in r["warnings"] if w["code"] == "SHARDING_PLAN")
    assert "Citus" in w["resolution"] and "Vitess" in w["resolution"] and "https://" in w["detail"]
    small = recommend({"app_type": "ecommerce", "dau": 300_000, "data_volume_gb": 900, "data_growth_gb_month": 30,
                       "data_shapes": ["relational"], "budget_monthly": 25_000, "team_size": 12},
                      with_counterfactuals=False)
    assert "SHARDING_PLAN" not in codes(small)


def test_tight_latency_across_continents_is_warned_with_a_cited_round_trip():
    base = {"app_type": "fintech", "dau": 40_000, "latency_target_ms": 70, "budget_monthly": 3000, "team_size": 6}
    r = recommend(dict(base, regions=["europe", "southeast_asia"]), with_counterfactuals=False)
    w = next(w for w in r["warnings"] if w["code"] == "CROSS_REGION_LATENCY")
    assert "ms" in w["detail"] and "https://" in w["detail"] and "multi-region" in w["resolution"]
    assert "CROSS_REGION_LATENCY" not in codes(recommend(dict(base, regions=["europe"]), with_counterfactuals=False))
    assert "CROSS_REGION_LATENCY" not in codes(recommend(dict(base, regions=["europe", "southeast_asia"],
                                                              latency_target_ms=250), with_counterfactuals=False))
