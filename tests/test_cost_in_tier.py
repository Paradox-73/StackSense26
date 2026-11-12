"""The displayed cost reads each price band where the project sits inside its scale tier (engine/scoring.py
placed_cost): the low end stays the band's floor (the bill the budget guard checks), and the top end is the price
half a tier above the project's place, so at the tier's bottom it sits near the floor, it rises smoothly with users
and it does not jump at a tier edge. Every floor the band carries (entry plans, HIPAA/SSO/SOC 2 minimums) still holds.
The budget guard's bill (usage=False) keeps whole bands, the same at every user count of a tier. The budget status and
the BUDGET_* warnings follow the displayed estimate."""
import glob
import json

import pytest

from engine import recommend
from engine.advice import estimate_cost
from engine.kb import load_kb, load_presets
from engine.profile import CONCURRENT_THRESHOLDS, DAU_THRESHOLDS, TIER_NAMES, derive, normalize
from engine.scoring import placed_cost, scale_place, tier_cost
from engine.standard import run_text

KB = load_kb()["index"]
PLAIN = normalize({"app_type": "saas", "dau": 1000})[0]  # no compliance, SSO or static site: the bands as listed


def _pd(**raw):
    p, a, w = normalize(dict({"app_type": "saas", "data_volume_gb": 20, "data_growth_gb_month": 0,
                              "availability": "99.0"}, **raw))
    return p, derive(p, a, w)


def test_place_is_tier_plus_log_share():
    assert scale_place(1_000, DAU_THRESHOLDS) == pytest.approx(1.0)
    assert scale_place(5_000, CONCURRENT_THRESHOLDS) == pytest.approx(3.0)
    assert scale_place(500, CONCURRENT_THRESHOLDS) == pytest.approx(2.0)
    assert scale_place(1_581, CONCURRENT_THRESHOLDS) == pytest.approx(2.5, abs=1e-3)
    assert scale_place(1, DAU_THRESHOLDS) == 0.0 and scale_place(1e12, DAU_THRESHOLDS) < len(TIER_NAMES)


@pytest.mark.parametrize("iid", ["redis", "digitalocean", "postgres", "flyio", "aws_ecs"])
def test_low_end_is_the_band_floor_and_the_top_starts_near_it(iid):
    item = KB[iid]
    for tier in range(len(TIER_NAMES)):
        lo, hi = tier_cost(item, tier, PLAIN)
        for share in (0.0, 0.4, 0.9):
            assert placed_cost(item, tier, tier + share, PLAIN)[0] == pytest.approx(lo), (tier, share)
        if tier < len(TIER_NAMES) - 1 and hi > lo and lo > 0:
            top = placed_cost(item, tier, float(tier), PLAIN)[1]
            assert top < hi and top == pytest.approx(lo * (hi / lo) ** 0.5), tier  # half a tier up, not the tier's top


@pytest.mark.parametrize("iid", ["redis", "digitalocean", "postgres", "flyio", "aws_ecs", "supabase"])
def test_top_rises_with_place_and_does_not_jump_where_bands_meet(iid):
    item = KB[iid]
    prev = (0.0, 0.0)
    for i in range(600):
        at = i / 100
        cur = placed_cost(item, int(at), at, PLAIN)
        assert cur[0] >= prev[0] - 1e-9 and cur[1] >= prev[1] - 1e-9 and cur[1] >= cur[0], at
        prev = cur
    met = 0
    for k in range(1, len(TIER_NAMES)):
        if tier_cost(item, k - 1, PLAIN)[1] != tier_cost(item, k, PLAIN)[0]:
            continue  # a real step between plans (a free tier, then a paid one) stays a step
        met += 1
        assert placed_cost(item, k - 1, k - 1e-9, PLAIN)[1] == pytest.approx(placed_cost(item, k, float(k), PLAIN)[1], rel=1e-6)
    assert met >= 3


@pytest.mark.parametrize("raw", [{"compliance": ["hipaa"]}, {"compliance": ["soc2"]}, {"enterprise_sso": True},
                                 {"data_volume_gb": 0.3}, {"data_volume_gb": 6}])
def test_placed_price_keeps_every_floor_of_the_band(raw):
    """Entry-plan floors (with the derived profile, at small data sizes) and the HIPAA, SOC 2 and SSO minimums."""
    p, d = _pd(**raw)
    for item in KB.values():
        if "cost_usd" not in item:
            continue
        for tier in range(len(TIER_NAMES)):
            lo = tier_cost(item, tier, p, d)[0]
            for share in (0.0, 0.5, 0.99):
                plo, phi = placed_cost(item, tier, tier + share, p, d)
                assert plo >= lo - 1e-9 and phi >= plo, (item["id"], tier, share)


STACK = {"frontend": KB["react_spa"], "backend": KB["go"], "database": KB["postgres"], "hosting": KB["digitalocean"]}


def _bills(key, values, line=None, **fixed):
    """(low, high, scale tier) of the bill, or of one line of it, at each value of one answer."""
    out = {}
    for v in values:
        p, d = _pd(**{key: v}, **fixed)
        c = estimate_cost(p, d, STACK, [])
        x = next(x for x in c["lines"] if x["component"].startswith(line)) if line else             {"low": c["total_low"], "high": c["total_high"]}
        out[v] = (x["low"], x["high"], d["compute_tier"])
    return out


def _smooth(bills, below, edge):
    values = list(bills.values())
    assert all(b[0] >= a[0] and b[1] >= a[1] for a, b in zip(values, values[1:])), bills
    assert bills[below][2] + 1 == bills[edge][2], bills  # the two counts sit on either side of a tier edge
    assert bills[edge][1] == pytest.approx(bills[below][1], rel=0.02), bills  # the top does not jump there


def test_hosting_rises_smoothly_with_users_online_across_a_tier_edge():
    """20,000 daily users; users online at once cross from Medium into Large at 5,000. The app servers hold those
    connections, so the hosting top is smooth; the low end steps up at the edge, to the floor of the larger tier. (The
    database follows its own queries and data, which do not change here, so it starts at the larger tier's floor.)"""
    bills = _bills("peak_concurrent", (1_000, 2_000, 3_500, 4_999, 5_000, 8_000, 15_000, 19_000), "Hosting",
                   dau=20_000)
    _smooth(bills, 4_999, 5_000)
    assert bills[19_000][1] > 1.5 * bills[5_000][1], bills  # the top of the tier costs more than its bottom
    assert bills[3_500][0] == bills[1_000][0], bills  # the floor holds through the tier


def test_bill_rises_smoothly_with_daily_users_across_a_tier_edge():
    """Daily users push the peak request rate past 500 req/s (Large) at ~57,600 users, moving the app and database
    tiers together."""
    bills = _bills("dau", (20_000, 40_000, 57_000, 57_700, 70_000, 90_000))
    _smooth(bills, 57_000, 57_700)


def test_budget_guard_bill_is_the_same_at_every_user_count_of_a_tier():
    guard = set()
    for conc in (5_000, 9_000, 19_000):
        p, d = _pd(dau=20_000, peak_concurrent=conc)
        assert d["compute_tier"] == 3
        guard.add(estimate_cost(p, d, STACK, [], usage=False)["total_low"])
    assert len(guard) == 1


def test_bottom_of_large_tier_quotes_the_floor_and_says_where():
    p, d = _pd(dau=20_000, peak_concurrent=5_000)
    host = next(x for x in estimate_cost(p, d, STACK, [])["lines"] if x["component"].startswith("Hosting"))
    assert host["low"] == tier_cost(KB["digitalocean"], 3, p)[0]
    assert "5,000 users online at once" in host["basis"] and "bottom of the tier" in host["basis"]


def _budget_codes(warnings):
    return {w["code"]: w["severity"] for w in warnings if w["code"].startswith("BUDGET_") and w["code"] != "BUDGET_OVERSIZED"}


@pytest.mark.parametrize("preset", [x["id"] for x in load_presets()])
def test_budget_status_and_warnings_follow_the_displayed_estimate(preset):
    r = recommend(next(x for x in load_presets() if x["id"] == preset)["input"], with_counterfactuals=False)
    if not r["feasible"]:
        return
    c, codes = r["cost"], _budget_codes(r["warnings"])
    if c["total_low"] > c["budget_usd"]:
        assert c["status"] == "over" and set(codes) & {"BUDGET_INFEASIBLE", "BUDGET_STRETCH"}
        assert "critical" in codes.values()
    elif c["total_high"] > c["budget_usd"]:
        assert c["status"] == "stretch" and codes == {"BUDGET_RANGE_OVER": "warning"}
    else:
        assert c["status"] == "within" and not codes


@pytest.mark.parametrize("path", sorted(glob.glob("scenarios/public/*.json") + glob.glob("scenarios/edge/*.json")))
def test_no_scenario_goes_over_budget_silently(path):
    out = run_text(open(path, encoding="utf-8").read(), capped=False)
    if out["status"] in ("invalid_input", "infeasible"):
        return
    cost = out["estimated_monthly_cost_usd"]
    check = next(x for x in cost["assumptions"] if x.startswith("Budget check: $"))  # the budget used (or its default)
    if cost["max"] > float(check.split("$")[1].split("/")[0].replace(",", "")):
        assert _budget_codes(out["warnings"]) and out["status"] == "ok_with_warnings", out["warnings"]


def _p2(**change):
    doc = json.load(open("scenarios/public/P2.json", encoding="utf-8"))
    for path, value in change.items():
        section, key = path.split("__")
        doc[section][key] = value
    return run_text(json.dumps(doc), capped=False)


UNQUALIFIED_FIT = ("minimum bill that fits your budget", "fits the budget (about")


@pytest.mark.parametrize("change", [{}, {"budget__monthly_infra_usd": 165.0}, {"priorities__performance": 4},
                                    {"budget__monthly_infra_usd": 300}])
def test_budget_rule_says_fits_only_when_the_estimate_fits(change):
    """P2 with its budget raised 10% picked Cloud Run "on a minimum bill that fits your budget" while the estimate
    shown was over $165: the budget rules compare the bands' floors, so the words must follow the estimate shown."""
    out = _p2(**change)
    budget = json.load(open("scenarios/public/P2.json", encoding="utf-8"))["budget"]["monthly_infra_usd"]
    budget = change.get("budget__monthly_infra_usd", budget)
    text = json.dumps(out["stack"]) + json.dumps(out["warnings"])
    if out["estimated_monthly_cost_usd"]["min"] > budget:
        assert not any(x in text for x in UNQUALIFIED_FIT), [x for x in UNQUALIFIED_FIT if x in text]
    if out["estimated_monthly_cost_usd"]["max"] > budget:
        assert _budget_codes(out["warnings"]) and out["status"] == "ok_with_warnings"
