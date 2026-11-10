"""Explanation text must match the final stack. Every preset and every adversarial input in
tests/redteam/cases.json is run once, and each shown sentence that names a service, a plan or a way of
running the code is checked against the picks, the hosting (the API's host under split hosting) and the
stated compliance."""
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from engine import recommend
from engine.advice import database_offering, usable_plans
from engine.kb import load_kb, load_presets

CASES = json.loads((Path(__file__).parent / "redteam" / "cases.json").read_text(encoding="utf-8"))["cases"]


def redteam_input(case_id: str) -> dict:
    return deepcopy(next(c["input"] for c in CASES if c["id"] == case_id))


@pytest.fixture(scope="module")
def runs():
    inputs = [("preset_" + p["id"], p["input"]) for p in load_presets()] + [(c["id"], c["input"]) for c in CASES]
    out = {}
    for name, inp in inputs:
        r = recommend(deepcopy(inp), with_counterfactuals=False)
        if r["feasible"]:
            out[name] = r
    return out


def _items(r):
    kb = load_kb()["index"]
    return {l: kb[r["stack"][l]["pick"]["id"]] for l in r["stack"]}


def _api_host(r):
    api = r["stack"]["hosting"].get("api_host")
    return load_kb()["index"][api["id"]] if api else None


def test_database_cost_line_cites_only_a_plan_the_stack_can_buy(runs):
    """A plan quoted in the database cost line is sold as the stack's managed offering on the API's host, and
    under HIPAA its vendor signs a BAA for it (no Supabase Pro on an RDS, Cloud SQL or HIPAA stack)."""
    bad = []
    for name, r in runs.items():
        it = _items(r)
        db = it["database"]
        line = next((x for x in r["cost"]["lines"] if x["component"].startswith("Database:")), None)
        if not line:
            continue
        cited = re.search(r"from \$[\d.]+ on ([^:]+):", line["basis"])
        if not cited:
            continue
        offer = database_offering(db, _api_host(r) or it["hosting"], r["profile"])
        plan = next((ep for ep in db.get("entry_plans", []) + db.get("host_plans", []) if ep["name"] == cited.group(1)), None)
        if plan is None or plan not in usable_plans(db, offer, r["profile"]):
            bad.append((name, cited.group(1), offer))
        if "hipaa" in r["profile"]["compliance"] and not (plan or {}).get("baa"):
            bad.append((name, cited.group(1), "HIPAA without a BAA"))
    assert not bad, bad


@pytest.mark.parametrize("case_id", ["t05_hipaa_telehealth_aws", "t20_multitenant_saas_soc2", "t31_hipaa_gcp_onprem_hybrid",
                                     "t15_rails_marketplace", "t35_user_code_edu"])
def test_redteam_hyperscaler_database_is_not_priced_as_supabase(case_id):
    r = recommend(redteam_input(case_id), with_counterfactuals=False)
    line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database:"))
    assert "Supabase" not in line["basis"] and "Neon" not in line["basis"], line["basis"]
    assert r["stack"]["database"]["managed_offering"].split(" ")[0] in line["basis"] or "priced as" in line["basis"]


def test_hipaa_mongodb_is_priced_from_a_baa_plan():
    from engine.advice import usable_plans
    db = load_kb()["index"]["mongodb"]
    offer = db["managed_offerings"]["any"]
    names = [ep["name"] for ep in usable_plans(db, offer, {"compliance": ["hipaa"]})]
    assert names and all(n in ("MongoDB Atlas M10", "MongoDB Atlas M20", "MongoDB Atlas M30") for n in names)
    assert "MongoDB Atlas Flex" in [ep["name"] for ep in usable_plans(db, offer, {"compliance": []})]


SCHEMALESS = ("mongodb", "firestore", "dynamodb", "cassandra", "redis", "opensearch", "neo4j")


def test_schema_change_text_follows_the_database(runs):
    """'Versioned migrations' of a table schema only for databases that have one; Redis, MongoDB and Firestore
    stacks say how their own data changes shape."""
    bad = []
    for name, r in runs.items():
        db = r["stack"]["database"]["pick"]["id"]
        deploy = next(s["text"] for s in r["architecture"]["how_parts_fit"] if s["step"] == "Deploy")
        if db in SCHEMALESS and ("schema changes run as versioned migrations" in deploy.lower()
                                 or "Schema changes and access rules" in deploy):
            bad.append((name, db, deploy))
    assert not bad, bad


@pytest.mark.parametrize("case_id", ["t21_game_backend", "t37_mongo_existing", "t25_huge_enterprise_budget", "v_eu_res_content"])
def test_redteam_schemaless_deploy_text(case_id):
    r = recommend(redteam_input(case_id), with_counterfactuals=False)
    deploy = next(s["text"] for s in r["architecture"]["how_parts_fit"] if s["step"] == "Deploy")
    db = r["stack"]["database"]["pick"]
    if db["id"] in SCHEMALESS:
        word = {"mongodb": "MongoDB", "firestore": "Firestore", "redis": "Redis", "dynamodb": "DynamoDB",
                "cassandra": "Cassandra", "neo4j": "Neo4j", "opensearch": "index"}[db["id"]]
        assert word in deploy and "versioned migrations before" not in deploy, deploy


def test_backend_and_hosting_text_follow_how_the_code_runs(runs):
    """'Long-running service' only where the API runs as processes; on a functions or frontend platform without an
    API host of its own, the paragraphs say serverless functions, as the hosting's 'Runs here' line does."""
    bad = []
    for name, r in runs.items():
        runs_here = r["stack"]["hosting"].get("runs_here") or ""
        functions = "as serverless functions" in runs_here or "the serverless functions" in runs_here
        for layer in ("backend", "hosting"):
            para = r["stack"][layer]["explanation"]["paragraph"]
            if functions and "long-running" in para:
                bad.append((name, layer, para))
        if "as long-running processes" in runs_here and "serverless functions" in r["stack"]["backend"]["explanation"]["paragraph"] \
                and r["stack"]["backend"]["pick"]["id"] != "serverless_functions":
            bad.append((name, "backend", "says functions on a long-running host"))
    assert not bad, bad


@pytest.mark.parametrize("case_id", ["v_eu_res_content", "v_default_30k"])
def test_redteam_functions_hosting_is_not_called_long_running(case_id):
    r = recommend(redteam_input(case_id), with_counterfactuals=False)
    if "as serverless functions" in r["stack"]["hosting"]["runs_here"]:
        para = r["stack"]["backend"]["explanation"]["paragraph"]
        assert "long-running" not in para and "serverless functions" in para, para


def test_database_offering_follows_the_api_host(runs):
    """Under split hosting the database sits next to the API: no Cloudflare Hyperdrive offering when the API runs on
    Cloud Run, and the offering is the one the API host's provider sells."""
    bad = []
    for name, r in runs.items():
        api = _api_host(r)
        offer = r["stack"]["database"]["managed_offering"] or ""
        host = api or _items(r)["hosting"]
        if "Hyperdrive" in offer and host["id"] != "cloudflare":
            bad.append((name, offer, host["id"]))
        if api and r["stack"]["backend"]["pick"]["id"] != r["stack"]["database"]["pick"]["id"] and \
                not offer.startswith("Included with"):
            assert offer == database_offering(_items(r)["database"], api, r["profile"]), name
    assert not bad, bad


def test_redteam_split_hosting_database_offering():
    r = recommend(redteam_input("t03_10M_zero_budget"), with_counterfactuals=False)
    api = r["stack"]["hosting"].get("api_host")
    if api:
        assert "Hyperdrive" not in r["stack"]["database"]["managed_offering"]


def test_supporting_services_are_listed_once(runs):
    bad = []
    for name, r in runs.items():
        names = [s["name"] for s in r["supporting_services"] + r["deferred_services"]]
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            bad.append((name, dup))
    assert not bad, bad


@pytest.mark.parametrize("case_id", ["t05_hipaa_telehealth_aws", "t07_india_fintech_inr", "t25_huge_enterprise_budget",
                                     "t38_live_streaming"])
def test_redteam_uploads_bucket_is_not_a_second_frontend_line(case_id):
    r = recommend(redteam_input(case_id), with_counterfactuals=False)
    names = [s["name"] for s in r["supporting_services"]]
    assert len(names) == len(set(names)), names
    store = next((s["name"] for s in r["supporting_services"] if s["role"] == "Object storage"), "")
    if store.startswith("Amazon S3 (a second bucket"):
        assert "CloudFront" in store


def test_no_zero_point_gaps_in_text(runs):
    """A gap that prints as 0.0 points reads as a contradiction ('within 0.0 stack points'); it is worded as a tie."""
    pat = re.compile(r"\b0\.0 (stack )?points\b")
    bad = [(name, pat.search(json.dumps(r)).group(0)) for name, r in runs.items() if pat.search(json.dumps(r))]
    assert not bad, bad


def test_points_wording():
    from engine.explain import points
    assert points(1.26) == "1.3 stack points" and points(-0.4) == "0.4 stack points"
    assert points(0.01) == "less than 0.05 stack points" and points(0) == "less than 0.05 stack points"


def test_free_tier_warning_matches_the_estimate(runs):
    """'Free tiers only' is said only when the estimate is $0; otherwise the warning says the budget is 0 but the
    cheapest stack costs money."""
    bad = []
    for name, r in runs.items():
        for w in r["warnings"]:
            if w["code"] == "FREE_TIER_NO_SLA" and r["cost"]["total_low"] > 0 and "free tiers only" in w["title"]:
                bad.append((name, r["cost"]["total_low"]))
    assert not bad, bad


@pytest.mark.parametrize("case_id", ["t03_10M_zero_budget"])
def test_redteam_zero_budget_warning_states_the_real_cost(case_id):
    r = recommend(redteam_input(case_id), with_counterfactuals=False)
    w = next(w for w in r["warnings"] if w["code"] == "FREE_TIER_NO_SLA")
    assert "zero budget" in w["title"] and f"${r['cost']['total_low']:,.0f}/month" in w["detail"]


def _num(tok):
    tok = tok.strip().replace(",", "")
    mult = 1.0
    for suf, m in (("TB", 1e3), ("GB", 1.0), ("k", 1e3), ("M", 1e6)):
        if tok.endswith(suf):
            tok, mult = tok[: -len(suf)].strip(), m
    return float(tok) * mult


def _in_range(text, value):
    """'Medium (10k-100k daily users)', 'Large (500-5,000 req/s at peak)', 'Small (<10 GB of data)' hold value."""
    inner = re.search(r"\(([^)]*)\)", text).group(1)
    rng = re.match(r"([<>]?)([\d.,]+ ?(?:k|M|GB|TB)?)(?:-([\d.,]+ ?(?:k|M|GB|TB)?))?", inner)
    op, a, b = rng.groups()
    if b and b.strip().endswith("TB") and not a.strip().endswith(("GB", "TB")):
        a += "TB"
    lo, hi = (0, _num(a)) if op == "<" else (_num(a), float("inf")) if op == ">" else (_num(a), _num(b))
    return lo <= value < hi


def test_scale_labels_describe_what_set_the_tier(runs):
    """The tier label quotes the measure that set the tier, with a range that holds the project's own figure:
    30k daily users of a realtime app is 'Large (500-5,000 req/s at peak)', not 'Large (100k-1M)'."""
    bad = []
    for name, r in runs.items():
        d, p = r["derived"], r["profile"]
        label = d["tier_label"]
        value = p["dau"] if "daily users" in label else d["peak_rps"] if "req/s" in label else None
        if value is None or not _in_range(label, value):
            bad.append((name, label, p["dau"], d["peak_rps"]))
        db = d["db_tier_label"]
        if "of data" in db and not _in_range(db, d["data_12mo_gb"]):
            bad.append((name, db, d["data_12mo_gb"]))
    assert not bad, bad


@pytest.mark.parametrize("case_id,word", [("t14_realtime_collab_elixir", "req/s"), ("t13_iot_fleet", "req/s"),
                                          ("t32_low_latency_trading", "req/s"), ("t24_all_not_sure", "daily users")])
def test_redteam_scale_label(case_id, word):
    r = recommend(redteam_input(case_id), with_counterfactuals=False)
    assert word in r["derived"]["tier_label"] and "100k-1M)" not in r["summary"]
