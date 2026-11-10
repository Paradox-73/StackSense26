"""A stated cloud preference is a strong preference: honoured in most projects, overridden only with a warning."""
from engine import recommend
from engine.kb import load_kb
from engine.scoring import CLOUD_PREF_BONUS, cloud_pref_bonus

APPS = ["saas", "ecommerce", "fintech", "healthcare", "social_network", "ml_product", "internal_tool", "mobile_first"]


def _provider(r):
    return load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]].get("provider")


def test_aws_preference_alone_lands_on_aws():
    r = recommend({"cloud_preference": "aws"}, with_counterfactuals=False)
    assert _provider(r) == "aws"


def test_preferred_cloud_honoured_or_warned():
    """Across app types, scales and team sizes: the preferred cloud hosts the stack in at least 80% of runs,
    and every run that lands elsewhere carries CLOUD_PREFERENCE_OVERRIDDEN."""
    for pref in ("aws", "gcp", "azure"):
        on = total = 0
        for app in APPS:
            for dau, budget, team in ((1000, 200, 3), (50000, 3000, 8), (1000000, 40000, 20)):
                r = recommend({"app_type": app, "cloud_preference": pref, "dau": dau, "budget_monthly": budget,
                               "team_size": team}, with_counterfactuals=False)
                total += 1
                if _provider(r) == pref:
                    on += 1
                    assert not any(w["code"] == "CLOUD_PREFERENCE_OVERRIDDEN" for w in r["warnings"])
                else:
                    assert any(w["code"] == "CLOUD_PREFERENCE_OVERRIDDEN" for w in r["warnings"]), (pref, app, dau)
        assert on >= 0.8 * total, (pref, on, total)


def test_preference_is_soft_at_zero_budget():
    """At $0 the bonus shrinks, so a hyperscaler's paid minimum does not push a free project over budget."""
    assert cloud_pref_bonus(0) < cloud_pref_bonus(25) < cloud_pref_bonus(50) == CLOUD_PREF_BONUS
    r = recommend({"cloud_preference": "aws", "budget_monthly": 0}, with_counterfactuals=False)
    assert r["feasible"]


def test_on_prem_ignores_cloud_preference_without_override_warning():
    r = recommend({"cloud_preference": "aws", "deployment": "on_prem"}, with_counterfactuals=False)
    codes = {w["code"] for w in r["warnings"]}
    assert "ONPREM_CLOUD_PREF" in codes and "CLOUD_PREFERENCE_OVERRIDDEN" not in codes
