"""A project that states no data at launch and no growth stores nothing users write: when what users do is
left unanswered, it is read-only (a static site needs no server code and no database)."""
from engine import recommend

SITE = {"app_type": "prototype", "platforms": ["web"], "dau": 300, "data_volume_gb": 0, "data_growth_gb_month": 0,
        "data_shapes": ["document"], "team_size": 1, "team_skills": ["javascript", "html"], "timeline_weeks": 1, "budget_monthly": 0,
        "currency": "USD", "deployment": "cloud"}


def _actions(r):
    return next(a for a in r["assumptions"] if a["field"] == "user_actions")


def test_zero_data_defaults_to_read_only():
    r = recommend(SITE)
    assert _actions(r)["value"] == ["read"]
    assert r["stack"]["backend"]["pick"]["id"] == "no_custom_backend"
    assert r["stack"]["database"]["pick"]["id"] == "none_static"


def test_stated_actions_or_some_data_keep_the_generic_default():
    r = recommend(dict(SITE, user_actions=["read", "sign_in", "post"]))
    assert r["stack"]["backend"]["pick"]["id"] != "no_custom_backend"
    r = recommend(dict(SITE, data_growth_gb_month=0.1))
    assert _actions(r)["value"] == ["read", "sign_in", "post"]
    r = recommend({k: v for k, v in SITE.items() if k != "data_volume_gb"})  # volume left at its default
    assert _actions(r)["value"] == ["read", "sign_in", "post"]
