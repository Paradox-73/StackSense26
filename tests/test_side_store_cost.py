"""A side store of records beside an analytics primary is priced by the records it holds (the traffic's tier),
not by the analytics volume in the primary."""
from engine import recommend

WAREHOUSE = {"app_type": "analytics_dashboard", "dau": 3000, "data_volume_gb": 15000, "data_growth_gb_month": 400,
             "data_shapes": ["analytical", "relational"], "cloud_preference": "gcp", "budget_monthly": 6000,
             "team_size": 4}


def test_record_store_beside_a_warehouse_is_priced_by_traffic():
    r = recommend(WAREHOUSE, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "bigquery"
    side = next(x for x in r["cost"]["lines"] if x["component"].startswith("Secondary store"))
    db = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database"))
    assert side["low"] < 100 and side["low"] * 10 < db["low"]
    why = next(s["why"] for s in r["supporting_services"] if s["role"].startswith("Secondary store"))
    assert "holds the records" in why
