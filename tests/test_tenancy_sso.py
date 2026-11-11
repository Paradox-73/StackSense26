"""Customer organisations sharing the app (tenancy) and enterprise single sign-on: both default to no effect; a shared
database favours stores that enforce each customer's rows themselves; SSO raises the bill of a BaaS that sells it."""
from engine import recommend
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import adjustments, tier_cost

BASE = {"app_type": "saas", "dau": 5000, "budget_monthly": 200}


def _pd(raw):
    p, a, w = normalize(raw)
    return p, derive(p, a, w)


def _picks(r):
    return {l: r["stack"][l]["pick"]["id"] for l in r["stack"]}


def test_defaults_change_nothing():
    a = recommend(BASE, with_counterfactuals=False)
    b = recommend(dict(BASE, tenancy="single", enterprise_sso=False), with_counterfactuals=False)
    assert _picks(a) == _picks(b) and a["cost"] == b["cost"]


def test_shared_database_favours_row_level_security():
    kb = load_kb()["index"]
    p, d = _pd(dict(BASE, tenancy="shared"))
    pts = lambda i: sum(x["delta"] for x in adjustments("database", kb[i], p, d) if x["input"] == "tenancy")
    assert pts("postgres") > 0 and pts("sqlserver") > 0 and pts("dynamodb") > 0
    assert pts("mysql") < 0 and pts("mongodb") < 0 and pts("sqlite") < 0
    assert pts("redis") == 0  # no stated fact either way
    p0, d0 = _pd(BASE)
    assert not [x for x in adjustments("database", kb["mysql"], p0, d0) if x["input"] == "tenancy"]


def test_shared_tenancy_reorders_the_database_ranking():
    raw = dict(BASE, team_skills=["javascript", "node", "mysql"])
    a = recommend(raw, with_counterfactuals=False)["stack"]["database"]["ranking"][0]["id"]
    b = recommend(dict(raw, tenancy="shared"), with_counterfactuals=False)["stack"]["database"]["ranking"][0]["id"]
    assert (a, b) == ("mysql", "postgres")


def test_isolated_tenancy_weighs_operations():
    from engine.scoring import build_weights
    p, d = _pd(dict(BASE, tenancy="isolated"))
    assert any(x["input"] == "tenancy" for x in build_weights(p, d).as_list() if x.get("input"))  \
        or build_weights(p, d).total("ops") > build_weights(*_pd(BASE)).total("ops")


def test_every_tenant_isolation_fact_is_cited():
    for db in load_kb()["database"]:
        iso = db.get("tenant_isolation")
        if iso:
            assert isinstance(iso["in_database"], bool) and iso["source"].startswith("https://"), db["id"]


def test_sso_raises_the_supabase_floor_to_pro_and_prices_users():
    kb = load_kb()["index"]
    p, d = _pd(dict(BASE, dau=500))
    p2, d2 = _pd(dict(BASE, dau=500, enterprise_sso=True))
    assert tier_cost(kb["supabase"], 0, p, d)[0] < 25 <= tier_cost(kb["supabase"], 0, p2, d2)[0]
    raw = {"app_type": "saas", "dau": 2000, "budget_monthly": 50, "team_skills": ["typescript", "nextjs", "supabase"]}
    a = recommend(raw, with_counterfactuals=False)
    b = recommend(dict(raw, enterprise_sso=True), with_counterfactuals=False)
    assert b["cost"]["total_low"] > a["cost"]["total_low"]
    assert any(s["role"] == "Enterprise SSO" for s in b["supporting_services"])


def test_sso_on_a_server_backend_is_part_of_the_one_sign_in_product():
    """One customer's directory is a federation of the sign-in product; Keycloak brokering is for many tenants' own
    identity providers, and only with a team that runs servers and a budget for one."""
    one = recommend(dict(BASE, team_skills=["python", "django"], enterprise_sso=True), with_counterfactuals=False)
    auth = [s for s in one["supporting_services"] if s["role"] in ("Authentication", "Enterprise SSO")]
    assert len(auth) == 1 and "SAML or OIDC" in auth[0]["name"] and "Keycloak" not in auth[0]["name"], auth
    many = recommend(dict(BASE, team_skills=["python", "django"], enterprise_sso=True, tenancy="shared",
                          has_devops=True), with_counterfactuals=False)
    auth = [s for s in many["supporting_services"] if s["role"] in ("Authentication", "Enterprise SSO")]
    assert len(auth) == 1 and "Keycloak identity brokering" in auth[0]["name"], auth


def test_sso_counts_against_backends_that_need_a_broker():
    kb = load_kb()["index"]
    p, d = _pd(dict(BASE, enterprise_sso=True, tenancy="shared", has_devops=True))  # a Keycloak broker to run
    pts = lambda i: sum(x["delta"] for x in adjustments("backend", kb[i], p, d) if x["input"] == "enterprise_sso")
    assert pts("express") < 0 and pts("django") < 0 and pts("supabase") == 0 and pts("firebase") == 0
    p1, d1 = _pd(dict(BASE, enterprise_sso=True))  # one customer: a hosted identity service federates it for any backend
    assert sum(x["delta"] for x in adjustments("backend", kb["express"], p1, d1) if x["input"] == "enterprise_sso") == 0


def test_the_budget_check_counts_sso_users_at_the_scale_tier():
    """The budget guard prices stacks with estimate_cost(usage=False); the per-user SSO bill must be in it, the same
    at every user count of one tier."""
    from engine.advice import estimate_cost, supporting_services
    kb = load_kb()["index"]
    stack = {"frontend": kb["react_spa"], "backend": kb["supabase"], "database": kb["postgres"], "hosting": kb["vercel"]}

    def floor(dau):
        p, d = _pd({"app_type": "saas", "dau": dau, "enterprise_sso": True, "budget_monthly": 1500})
        lines = estimate_cost(p, d, stack, supporting_services(p, d, stack, []), usage=False)["lines"]
        return sum(l["low"] for l in lines if l["component"] == "Enterprise SSO")

    assert floor(100_000) > 1500
    assert floor(100_000) == floor(150_000)


def test_an_identity_provider_already_run_adds_no_broker_penalty():
    """P5 signs users in through its existing Entra ID, so no backend is marked down for needing an SSO broker."""
    import json
    from pathlib import Path
    from engine.standard import run
    doc = json.loads((Path(__file__).resolve().parent.parent / "scenarios" / "public" / "P5.json").read_text(encoding="utf-8"))
    out = run(doc)
    assert "broker" not in json.dumps(out["stack"]["backend"]), out["stack"]["backend"]["tradeoffs"]
    assert out["stack"]["backend"]["choice"].startswith("C# + ASP.NET Core")
    doc["infrastructure"]["existing_systems"] = []
    doc["requirements"]["multi_tenant"] = True
    doc["team"]["has_devops"] = True
    assert "identity broker" in json.dumps(run(doc)["stack"]["backend"])  # many tenants' directories: a broker to run
