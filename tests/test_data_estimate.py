"""An unanswered data volume is estimated from the daily users given, is not raised by users connected at once,
and stops at a ceiling per app type; a budget warning that rests on that estimate says so."""
from engine import recommend
from engine.profile import DATA_ESTIMATE_CAP_GB, DEFAULT_DATA_ESTIMATE_CAP_GB, derive, normalize


def _data(raw: dict) -> float:
    p, a, w = normalize(raw)
    return derive(p, a, w)["data_12mo_gb"]


def test_stated_users_set_the_estimate():
    # 40k users of a SaaS app at 0.5 MB a user a month: ~20 GB a month, ~254 GB in 12 months (launch = one month).
    # The count is taken at the middle of its half of the scale tier, within 10**0.5 / 2 of it either way.
    for dau in (400, 4_000, 40_000, 120_000):
        exact = dau * 0.5 / 1024 * 13
        assert exact / 10 ** 0.5 <= _data({"app_type": "saas", "dau": dau}) <= exact * 10 ** 0.5
    assert _data({"app_type": "saas", "dau": 40_000}) < _data({"app_type": "saas", "dau": 120_000})


def test_one_estimate_per_half_tier_so_the_growth_path_agrees_with_every_run():
    from engine.profile import growth_steps, own_step
    runs = []
    for dau in (150, 250, 2_000, 20_000):
        p, a, w = normalize({"app_type": "analytics_dashboard", "dau": dau})
        d = derive(p, a, w)
        steps = growth_steps(p, d)
        assert steps[own_step(p, d)] == (d["compute_tier"], d["data_anchor"][1])
        runs.append([u for _, u in steps])
    assert all(r == runs[0] for r in runs)  # every run walks the same steps


def test_users_connected_at_once_do_not_multiply_invented_data():
    base = {"app_type": "realtime_collab", "realtime": "core", "dau": 120_000}
    alone = _data(base)
    with_conc = _data(dict(base, peak_concurrent=90_000))  # raises the compute tier to Very large
    assert with_conc == alone
    # No user count given: the users connected at once are the users the estimate counts.
    assert _data({"app_type": "realtime_collab", "realtime": "core", "peak_concurrent": 90_000}) <= alone


def test_estimate_has_a_ceiling():
    assert _data({"app_type": "saas", "dau": 5_000_000}) == DEFAULT_DATA_ESTIMATE_CAP_GB
    assert _data({"app_type": "iot_telemetry", "dau": 2_000_000}) == DATA_ESTIMATE_CAP_GB["iot_telemetry"]
    # A stated size is never capped.
    assert _data({"app_type": "saas", "dau": 5_000_000, "data_volume_gb": 30_000, "data_growth_gb_month": 1000}) == 42_000


def test_assumption_names_the_stated_users_and_the_cap():
    r = recommend({"app_type": "saas", "dau": 5_000_000, "budget_monthly": 50_000})
    why = next(a["reason"] for a in r["assumptions"] if a["field"] == "data_growth_gb_month")
    assert "the 5,000,000 you stated" in why and "capped" in why


def test_budget_warning_says_the_data_was_estimated():
    r = recommend({"app_type": "analytics_dashboard", "dau": 1_500_000, "budget_monthly": 300, "team_size": 4})
    w = next(w for w in r["warnings"] if w["code"] in ("BUDGET_INFEASIBLE", "BUDGET_STRETCH"))
    assert "estimated size" in w["detail"]
    given = recommend({"app_type": "analytics_dashboard", "dau": 1_500_000, "budget_monthly": 300, "team_size": 4,
                       "data_volume_gb": 9000, "data_growth_gb_month": 100})
    assert all("estimated size" not in w["detail"] for w in given["warnings"])
