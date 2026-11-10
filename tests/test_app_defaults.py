"""Unanswered questions take app-type defaults (IoT -> time series, analytics -> analytical, content -> SEO,
ML -> vector), are listed as defaults, and never override an answer the user gave."""
from engine import recommend
from engine.recommender import _core, _picks

APP_TYPES = ["saas", "ecommerce", "realtime_collab", "content_site", "analytics_dashboard", "ml_product", "iot_telemetry",
             "fintech", "healthcare", "social_network", "internal_tool", "mobile_first", "prototype"]
TIME_SERIES = {"timescaledb", "clickhouse", "cassandra"}


def _default(r, field):
    return next((a for a in r["assumptions"] if a["field"] == field and a.get("kind") == "default"), None)


def test_iot_quick_input_gets_time_series_store():
    """Q13: quick-mode IoT project (10k devices, $500, Python team of 6)."""
    r = recommend({"app_type": "iot_telemetry", "dau": 10000, "budget_monthly": 500, "currency": "USD",
                   "team_size": 6, "team_skills": ["python"], "compliance": []}, with_counterfactuals=False)
    assert r["profile"]["data_shapes"][0] == "time_series"
    assert "type" in _default(r, "data_shapes")["reason"]
    assert r["stack"]["database"]["pick"]["id"] in TIME_SERIES
    assert r["cost"]["status"] in ("within", "stretch")


def test_app_type_defaults_are_listed():
    cases = {"analytics_dashboard": ("data_shapes", ["analytical", "relational"]), "content_site": ("seo", "important"),
             "ml_product": ("data_shapes", ["relational", "vector"])}
    for app, (field, value) in cases.items():
        r = recommend({"app_type": app}, with_counterfactuals=False)
        assert r["profile"][field] == value
        assert _default(r, field)["value"] == value


def test_answered_question_is_not_overridden():
    r = recommend({"app_type": "iot_telemetry", "data_shapes": ["document"], "seo": "none"}, with_counterfactuals=False)
    assert r["profile"]["data_shapes"] == ["document"]
    r = recommend({"app_type": "content_site", "seo": "none"}, with_counterfactuals=False)
    assert r["profile"]["seo"] == "none"


def test_app_type_alone_changes_the_stack():
    """Changing only the app type from the defaults gives at least 6 distinct stacks over the 13 types."""
    stacks = {tuple(_picks(_core({"app_type": a})).values()) for a in APP_TYPES}
    assert len(stacks) >= 6, stacks


def test_iot_trusts_a_stated_peak_rps():
    """E15: 1M smart meters stating 2,000 req/s is sized on that rate, not on a per-device guess."""
    raw = {"app_type": "iot_telemetry", "dau": 1000000, "peak_rps": 2000, "data_volume_gb": 1000,
           "data_growth_gb_month": 600, "read_write": "write_heavy", "data_shapes": ["time_series", "relational"]}
    r = recommend(raw, with_counterfactuals=False)
    assert r["derived"]["peak_rps"] == 2000 and r["derived"]["rps_source"] == "provided"
    r10 = recommend(dict(raw, dau=10000000), with_counterfactuals=False)
    assert r10["derived"]["peak_rps"] == 2000
    assert any(w["code"] == "RPS_DAU_MISMATCH" and w["severity"] == "info" for w in r10["warnings"])


def test_app_type_data_shape_lifts_the_default_consistency_like_a_stated_one():
    """An analytics dashboard left at its defaults: the app type's analytical shape counts like a stated one, so the
    unanswered consistency question does not keep a columnar store out (t16: 5 TB of events)."""
    base = {"app_type": "analytics_dashboard", "dau": 2000, "team_size": 4, "team_skills": ["python", "sql", "react"],
            "data_volume_gb": 5000, "data_growth_gb_month": 800, "budget_monthly": 3000, "regions": ["europe"],
            "compliance": ["gdpr"]}
    defaulted = recommend(base, with_counterfactuals=False)
    stated = recommend(dict(base, data_shapes=["analytical", "relational"]), with_counterfactuals=False)
    assert defaulted["stack"]["database"]["pick"]["id"] == stated["stack"]["database"]["pick"]["id"]
    assert defaulted["stack"]["database"]["pick"]["id"] in ("bigquery", "clickhouse")
    assert "data_shapes" in defaulted["derived"]["app_defaulted"]


def test_generic_default_shape_still_binds_the_default_consistency():
    r = recommend({"app_type": "saas", "dau": 2000}, with_counterfactuals=False)
    assert "data_shapes" not in r["derived"]["app_defaulted"]
    assert {"cassandra", "clickhouse"} <= {e["id"] for e in r["stack"]["database"]["excluded"]}


def test_content_site_where_users_write_defaults_to_relational_records():
    """A news site with sign-in and comments: accounts and comments are relational rows (as in WordPress or Ghost),
    so a MySQL team keeps MySQL rather than being pushed to a document store."""
    r = recommend({"app_type": "content_site", "dau": 300000, "seo": "critical", "team_size": 5, "team_skills": ["php", "mysql"],
                   "budget_monthly": 3000, "user_actions": ["read", "sign_in", "post"], "regions": ["india"]},
                  with_counterfactuals=False)
    assert r["profile"]["data_shapes"] == ["relational"]
    assert r["stack"]["database"]["pick"]["id"] == "mysql"
    static = recommend({"app_type": "content_site", "dau": 500}, with_counterfactuals=False)
    assert static["profile"]["data_shapes"] == ["document"]
