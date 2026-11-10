"""Cost model checks on the adversarial review inputs (tests/redteam/cases.json): unanswered defaults do not push a
small project over budget, database prices follow the stored data, huge data is at least its storage bill, add-ons
are priced at the app's scale, and usage lines follow the services they name."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from engine import recommend
from engine.profile import derive, normalize

CASES = {c["id"]: c["input"] for c in
         json.loads((Path(__file__).parent / "redteam" / "cases.json").read_text(encoding="utf-8"))["cases"]}


def run(case_id: str, **change) -> dict:
    return recommend(dict(deepcopy(CASES[case_id]), **change), with_counterfactuals=False)


def derived(**raw):
    p, a, w = normalize(raw)
    return p, derive(p, a, w), a


@pytest.mark.parametrize("case_id", ["t02_hackathon_proto", "t28_laravel_shop_inr", "t39_eu_residency_cheap",
                                     "t41_dau0", "t42_internal_tool_tiny"])
def test_redteam_small_projects_are_not_over_budget_from_defaults(case_id):
    """These projects stated no data size and no availability target; the defaults alone used to put them over
    budget (17 GB of data for any project, and x1.5 for the default 99.9%)."""
    r = run(case_id)
    assert r["cost"]["total_low"] <= r["derived"]["budget_usd"], (r["cost"]["total_low"], r["derived"]["budget_usd"])
    assert not any(w["code"] in ("BUDGET_STRETCH", "BUDGET_INFEASIBLE") for w in r["warnings"])


def test_default_data_follows_users_and_app_type():
    sizes = [derived(app_type="saas", dau=dau)[1]["data_12mo_gb"] for dau in (100, 3_000, 30_000, 3_000_000)]
    assert sizes == sorted(sizes) and sizes[0] < 5 and sizes[-1] > 1_000
    assert derived(app_type="social_network", dau=30_000)[1]["data_12mo_gb"] > derived(app_type="saas", dau=30_000)[1]["data_12mo_gb"]
    # the same at every user count of one half of a scale tier, so runs at different user counts agree on the growth path
    assert derived(app_type="saas", dau=1_000)[1]["data_12mo_gb"] == derived(app_type="saas", dau=1_500)[1]["data_12mo_gb"]
    # a stated size is kept, and a content site keeps its own app-type default
    assert derived(app_type="saas", dau=30_000, data_volume_gb=5, data_growth_gb_month=1)[1]["data_12mo_gb"] == 17
    assert derived(app_type="content_site", dau=30_000)[1]["data_12mo_gb"] == 2.2
    _, _, assumptions = derived(app_type="saas", dau=30_000)
    note = next(a for a in assumptions if a["field"] == "data_growth_gb_month")
    assert "estimated" in note["reason"] and "MB of database rows per daily user" in note["reason"]


def test_availability_is_priced_only_when_stated():
    base = {"app_type": "saas", "dau": 5_000, "team_skills": ["python", "django"], "budget_monthly": 500}
    unstated = recommend(base, with_counterfactuals=False)
    stated = recommend(dict(base, availability="99.9"), with_counterfactuals=False)
    host = lambda r: next(x for x in r["cost"]["lines"] if x["component"].startswith("Hosting"))  # noqa: E731
    if unstated["stack"]["hosting"]["pick"]["id"] == stated["stack"]["hosting"]["pick"]["id"] and \
            "x1.5" in host(stated)["basis"]:
        assert host(stated)["low"] == pytest.approx(1.5 * host(unstated)["low"], abs=1)
        assert "no availability target was given" in host(unstated)["basis"]


def test_redteam_stated_small_data_prices_the_small_plan():
    """t42 with its real data (1 GB) is priced from the host's cheapest database, not a 17 GB plan."""
    r = run("t42_internal_tool_tiny", data_volume_gb=1, data_growth_gb_month=0.1)
    assert r["cost"]["total_low"] <= 20


@pytest.mark.parametrize("case_id", ["t34_wordpress_shop_like", "t13_iot_fleet"])
def test_redteam_database_top_follows_small_data(case_id):
    """Traffic set the database tier but the data is far smaller than the tier's: the top of the price band is the
    instance the traffic needs, not the tier's largest data (t34: 2 GB priced up to $4,500 before)."""
    r = run(case_id)
    d = r["derived"]
    line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database:"))
    if d["data_tier"] < d["db_tier"]:
        assert line["high"] <= 2.5 * line["low"] and "upper end for" in line["basis"], line


def test_database_band_is_unchanged_when_data_sets_the_tier():
    r = recommend({"app_type": "saas", "dau": 2_000, "data_volume_gb": 5_000, "data_growth_gb_month": 100,
                   "budget_monthly": 50_000}, with_counterfactuals=False)
    line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database:"))
    assert "upper end for" not in line["basis"]


def test_redteam_hyperscale_database_costs_at_least_its_storage():
    """t25: 4.4 PB of MongoDB was priced at $60k-240k a month, below the disk alone."""
    from engine.advice import STORAGE_USD_PER_GB
    r = run("t25_huge_enterprise_budget")
    line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database:"))
    floor = r["derived"]["data_12mo_gb"] * STORAGE_USD_PER_GB["default"]
    assert line["low"] >= floor - 1 and "at least the storage" in line["basis"]


@pytest.mark.parametrize("case_id", ["t19_video_platform", "t25_huge_enterprise_budget"])
def test_redteam_add_ons_are_priced_at_the_apps_scale(case_id):
    """A cache, job queue, secondary store or warehouse is priced at the app's tier, not one or two tiers below."""
    r = run(case_id)
    tier_words = (r["derived"]["tier_label"], r["derived"]["db_tier_label"])
    for x in r["cost"]["lines"]:
        if x["component"].split(":")[0] in ("Cache", "Background jobs", "Analytics", "Realtime") or \
                x["component"].startswith("Secondary store"):
            assert x["basis"].startswith(tier_words), x


def test_redteam_secondary_postgres_for_a_fintech_is_not_free():
    """t26: the relational store next to the graph database was priced $0 (a free plan under the Hobby band)."""
    r = run("t26_graph_fraud")
    for x in r["cost"]["lines"]:
        if x["component"].startswith("Secondary store"):
            assert x["low"] > 0, x


def test_redteam_video_cost_follows_the_named_services():
    """t19 names S3 + MediaConvert + CloudFront but was priced at Cloudflare Stream's per-minute rate; the line now
    prices CDN data transfer and transcoding, and only a managed video service is priced per minute delivered."""
    from engine.advice import cdn_transfer_usd
    r = run("t19_video_platform")
    svc = next(s for s in r["supporting_services"] if s["role"] == "Video on demand")
    line = next(x for x in r["cost"]["lines"] if x["component"] == "Video on demand")
    if "MediaConvert" in svc["name"] or "Transcoder API" in svc["name"]:
        assert "CDN data transfer" in line["basis"] and "transcoding" in line["basis"]
        assert "per minute delivered" not in line["basis"]
    managed = recommend({"app_type": "social_network", "dau": 20_000, "special_workloads": ["video_on_demand"],
                         "budget_monthly": 5_000}, with_counterfactuals=False)
    svc = next(s for s in managed["supporting_services"] if s["role"] == "Video on demand")
    line = next(x for x in managed["cost"]["lines"] if x["component"] == "Video on demand")
    assert ("per minute delivered" in line["basis"]) == svc["name"].startswith("Cloudflare Stream")
    # volume tiers: the first 10 TB at $0.085/GB, the bill per GB falls with volume
    assert cdn_transfer_usd(1_000) == pytest.approx(85) and cdn_transfer_usd(1e7) / 1e7 < 0.03
