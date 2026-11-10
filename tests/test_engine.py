"""Unit tests: knowledge base, input normalisation, weights, constraints, scoring and compatibility."""
import copy

import pytest

from engine import recommend
from engine.kb import LAYERS, load_kb, validate_kb
from engine.profile import derive, normalize
from engine.scoring import build_weights, hard_constraints, score_layer
from engine.stack import matching_rules


def profile_of(raw):
    p, a, w = normalize(raw)
    d = derive(p, a, w)
    return p, d, a, w


# ----------------------------------------------------------------------------- knowledge base

def test_kb_is_valid(kb):
    assert validate_kb(kb) == []


def test_kb_coverage(kb):
    assert len(kb["frontend"]) >= 9 and len(kb["backend"]) >= 12
    assert len(kb["database"]) >= 11 and len(kb["hosting"]) >= 14
    ids = [i["id"] for l in LAYERS for i in kb[l]]
    assert len(ids) == len(set(ids)), "technology ids must be unique"


# ----------------------------------------------------------------------------- normalisation

def test_empty_input_uses_defaults_and_records_assumptions():
    p, d, a, w = profile_of({})
    assert p["app_type"] == "saas" and p["team_size"] == 3
    fields = {x["field"] for x in a}
    assert {"app_type", "dau", "budget_monthly", "team_size"} <= fields


def test_garbage_values_are_clamped_and_reported():
    p, d, a, w = profile_of({"dau": "lots", "team_size": -5, "app_type": "spaceship",
                             "regions": ["mars", "india"], "budget_monthly": -100})
    codes = [x["code"] for x in w]
    assert "INVALID_NUMBER" in codes and "UNKNOWN_OPTION" in codes and "VALUE_CLAMPED" in codes
    assert p["team_size"] == 1 and p["app_type"] == "saas" and p["regions"] == ["india"]
    assert p["budget_monthly"] == 0


def test_extreme_dau_is_clamped():
    p, d, a, w = profile_of({"dau": 5e12})
    assert p["dau"] == 2_000_000_000
    assert d["compute_tier"] == 5


def test_inr_budget_converted():
    p, d, a, w = profile_of({"budget_monthly": 9600, "currency": "INR"})  # 96 INR = 1 USD (FBIL, Sep 2026)
    assert d["budget_usd"] == pytest.approx(100, rel=1e-6)


def test_peak_rps_derived_from_dau():
    p, d, a, w = profile_of({"dau": 86400, "app_type": "saas"})
    # 86,400 DAU x 150 req/day / 86,400 s x peak factor 5 = 750 req/s
    assert d["peak_rps"] == pytest.approx(750)
    assert d["rps_source"] == "derived"


def test_rps_dau_mismatch_uses_larger_value():
    p, d, a, w = profile_of({"dau": 10_000_000, "peak_rps": 5})
    assert any(x["code"] == "RPS_DAU_MISMATCH" for x in w)
    assert d["peak_rps"] > 1000


def test_implied_requirements():
    p, d, a, w = profile_of({"app_type": "fintech", "consistency": "eventual_ok", "regions": ["india"],
                             "user_actions": ["read", "sign_in", "pay"]})
    assert p["consistency"] == "strong"
    assert "data_residency_india" in p["compliance"]
    p, d, a, w = profile_of({"app_type": "mobile_first"})
    assert set(p["platforms"]) == {"ios", "android"}
    p, d, a, w = profile_of({"app_type": "realtime_collab", "realtime": "none"})
    assert p["realtime"] == "core"


# ----------------------------------------------------------------------------- weights

def test_weights_follow_inputs():
    _, d0, _, _ = profile_of({"budget_monthly": 5000, "seo": "none"})
    p1, d1, _, _ = profile_of({"budget_monthly": 0, "seo": "critical"})
    p0, _, _, _ = profile_of({"budget_monthly": 5000, "seo": "none"})
    w0, w1 = build_weights(p0, d0), build_weights(p1, d1)
    assert w1.total("cost") > w0.total("cost")
    assert w1.total("seo") > w0.total("seo")
    drivers = {i for i, _, _ in w1.parts["seo"]}
    assert "seo" in drivers


def test_score_decomposes_into_input_contributions(kb):
    p, d, _, _ = profile_of({"seo": "critical", "budget_monthly": 20, "team_skills": ["react"]})
    w = build_weights(p, d)
    scored, _ = score_layer("frontend", kb["frontend"], p, d, w)
    for c in scored:
        if 0 < c["score"] < 100:
            assert sum(c["contributions"].values()) == pytest.approx(c["score"], abs=0.05)


# ----------------------------------------------------------------------------- hard constraints

def _excluded(layer, raw):
    p, d, _, _ = profile_of(raw)
    kb = load_kb()
    return {i["id"] for i in kb[layer] if hard_constraints(layer, i, p, d)}


def test_on_prem_excludes_managed_services():
    raw = {"deployment": "on_prem"}
    assert {"vercel", "netlify", "aws_lambda", "gcp_cloud_run", "cloudflare"} <= _excluded("hosting", raw)
    assert {"dynamodb", "firestore"} <= _excluded("database", raw)
    assert {"firebase", "serverless_functions"} <= _excluded("backend", raw)
    assert "supabase" not in _excluded("backend", raw)  # self-hostable
    assert "onprem_docker" not in _excluded("hosting", raw)


def test_cloud_excludes_on_prem_hosting():
    assert {"onprem_docker", "onprem_k8s"} <= _excluded("hosting", {"deployment": "cloud"})


def test_hipaa_excludes_non_baa_vendors():
    ex = _excluded("hosting", {"compliance": ["hipaa"]})
    assert {"netlify", "railway", "hetzner", "digitalocean", "cloudflare"} <= ex
    assert not {"aws_ecs", "gcp_cloud_run", "azure_apps"} & ex
    assert "firebase" in _excluded("backend", {"compliance": ["hipaa"]})


def test_india_residency_requires_india_region():
    ex = _excluded("hosting", {"compliance": ["data_residency_india"]})
    # Fly.io lists no Indian region; Cloudflare keeps data in India only with an Enterprise add-on (KB facts, Oct 2026).
    assert {"render", "railway", "hetzner", "netlify", "flyio", "cloudflare"} <= ex
    assert not {"aws_ecs", "digitalocean", "gcp_cloud_run"} & ex


def test_pci_requires_attestation():
    ex = _excluded("hosting", {"compliance": ["pci_dss"]})
    assert {"render", "railway", "flyio", "hetzner"} <= ex
    assert "aws_ecs" not in ex


def test_strong_consistency_excludes_eventual_stores():
    ex = _excluded("database", {"consistency": "strong", "data_shapes": ["relational"]})
    assert {"cassandra", "redis", "clickhouse"} <= ex


def test_data_shape_mismatch_excluded():
    ex = _excluded("database", {"consistency": "eventual_ok", "data_shapes": ["graph"]})
    assert "dynamodb" in ex and "neo4j" not in ex


def test_platform_filters_frontend():
    assert {"nextjs", "react_spa", "htmx"} <= _excluded("frontend", {"platforms": ["ios", "android"]})
    assert {"react_native", "flutter"} <= _excluded("frontend", {"platforms": ["web"]})


def test_low_lock_in_is_relaxable(kb):
    p, d, _, _ = profile_of({"lock_in_tolerance": "low"})
    w = build_weights(p, d)
    only_locked = [i for i in kb["backend"] if i["id"] == "firebase"]
    scored, excluded = score_layer("backend", only_locked, p, d, w)
    assert not scored and excluded
    scored, _ = score_layer("backend", only_locked, p, d, w, relax=1)
    assert scored


def test_scale_ceiling_excludes_sqlite_at_hyperscale():
    assert "sqlite" in _excluded("database", {"dau": 50_000_000})


# ----------------------------------------------------------------------------- compatibility rules

def _rules(ids, raw=None):
    kb = load_kb()
    p, d, _, _ = profile_of(raw or {})
    combo = dict(zip(LAYERS, (kb["index"][i] for i in ids)))
    return {r["id"] for r in matching_rules(combo, kb["rules"], p, d)}


def test_nextjs_vercel_synergy():
    assert "nextjs_vercel" in _rules(["nextjs", "express", "postgres", "vercel"])


def test_lambda_postgres_pooling_caveat():
    assert "lambda_rdbms_pooling" in _rules(["react_spa", "serverless_functions", "postgres", "aws_lambda"])


def test_supabase_with_other_db_conflict():
    assert "supabase_other_db" in _rules(["nextjs", "supabase", "mongodb", "vercel"])
    assert "supabase_other_db" not in _rules(["nextjs", "supabase", "postgres", "vercel"])


def test_realtime_on_functions_penalised_unless_baas():
    raw = {"realtime": "core"}
    assert "realtime_on_functions" in _rules(["nextjs", "express", "postgres", "netlify"], raw)
    assert "realtime_on_functions" not in _rules(["nextjs", "supabase", "postgres", "netlify"], raw)
    assert "realtime_on_functions" not in _rules(["nextjs", "express", "postgres", "netlify"], {"realtime": "none"})
    # Vercel Functions serve WebSockets in public beta (2026): a caveat, not a conflict.
    assert "realtime_on_functions" not in _rules(["nextjs", "express", "postgres", "vercel"], raw)
    assert "realtime_vercel_beta" in _rules(["nextjs", "express", "postgres", "vercel"], raw)


def test_dynamodb_off_aws_conflict():
    assert "dynamodb_off_aws" in _rules(["nextjs", "express", "dynamodb", "gcp_cloud_run"])
    assert "dynamodb_off_aws" not in _rules(["nextjs", "express", "dynamodb", "aws_ecs"])


# ----------------------------------------------------------------------------- whole-engine properties

def test_deterministic(presets):
    a = recommend(presets["startup_mvp"]["input"])
    b = recommend(copy.deepcopy(presets["startup_mvp"]["input"]))
    assert a == b


def test_seo_critical_prefers_server_rendering():
    r = recommend({"seo": "critical", "app_type": "content_site"}, with_counterfactuals=False)
    assert r["stack"]["frontend"]["pick"]["id"] in ("nextjs", "astro", "nuxt", "sveltekit", "htmx")


def test_frontend_rendering_follows_the_seo_answer():
    """A signed-in React dashboard with no SEO need gets the client-rendered SPA outside the tie margin, and the
    comparison names the SEO answer; SEO important moves it to server rendering; a team that already builds
    with Next.js keeps it."""
    raw = {"app_type": "saas", "team_skills": ["react", "typescript", "node"], "seo": "none", "team_size": 4}
    fe = recommend(raw, with_counterfactuals=False)["stack"]["frontend"]
    vs = fe["explanation"]["vs_runner_up"]
    assert fe["pick"]["id"] == "react_spa" and vs["runner_up_id"] == "nextjs"
    assert not vs["tie"] and "seo need" in vs["text"].lower()
    assert recommend(dict(raw, seo="important"), with_counterfactuals=False)["stack"]["frontend"]["pick"]["id"] == "nextjs"
    known = dict(raw, team_skills=raw["team_skills"] + ["nextjs"])
    assert recommend(known, with_counterfactuals=False)["stack"]["frontend"]["pick"]["id"] == "nextjs"


def test_skills_shift_the_pick():
    r_py = recommend({"team_skills": ["python", "django"], "app_type": "internal_tool"}, with_counterfactuals=False)
    r_rb = recommend({"team_skills": ["ruby", "rails"], "app_type": "internal_tool"}, with_counterfactuals=False)
    assert r_py["stack"]["backend"]["pick"]["id"] == "django"
    assert r_rb["stack"]["backend"]["pick"]["id"] == "rails"


def test_counterfactuals_report_changes(presets):
    r = recommend(presets["startup_mvp"]["input"])
    changes = {c["change"]: c for c in r["counterfactuals"]}
    onprem = changes["Must run on-premises"]
    assert any(e["layer"] == "hosting" for e in onprem["effects"])
    for c in r["counterfactuals"]:
        for e in c["effects"]:
            assert e["from"] != e["to"]
