"""Team skills decide the backend: a team's own language wins unless something concrete outweighs it."""
import json
from pathlib import Path

import pytest

from engine import recommend
from engine.kb import load_kb
from engine.recommender import _core, _picks
from engine.scoring import raw_scores

AUDIT = Path(__file__).parent / "scenarios_extra"
APP_TYPES = ["saas", "ecommerce", "realtime_collab", "content_site", "analytics_dashboard", "ml_product", "iot_telemetry",
             "fintech", "healthcare", "social_network", "internal_tool", "mobile_first", "prototype"]
NEUTRAL = {"supabase", "firebase", "serverless_functions"}  # managed backends that need no server language


def _scenario(prefix):
    for f in AUDIT.glob("*.json"):
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s["name"].startswith(prefix):
                return s["input"]
    raise KeyError(prefix)


def _raw(r, layer, item_id):
    """Per-criterion 1-5 scores of one technology for the profile behind result r."""
    d = dict(r["derived"], skills=set(r["derived"]["skills"]))
    return raw_scores(layer, load_kb()["index"][item_id], r["profile"], d, {})


def test_java_fintech_team_gets_spring_boot():
    """Q18: a 12-person Java/Spring fintech team used to get C# on Azure through a .NET bundle bonus."""
    r = recommend(_scenario("Q18"), with_counterfactuals=False)
    assert r["stack"]["backend"]["pick"]["id"] == "spring_boot"
    assert "dotnet_azure" not in {c["id"] for c in r["compatibility"]}


@pytest.mark.parametrize("skills,family", [(["java", "spring"], {"spring_boot"}), (["php"], {"laravel"}),
                                           (["csharp"], {"dotnet"}), (["python"], {"fastapi", "django"})])
def test_language_chip_keeps_the_team_language(skills, family):
    """Quick-mode language chip across app types: the backend is in the team's language or a managed BaaS,
    at least 80% of the time, and a Java team never gets C#."""
    picks = [_picks(_core({"app_type": app, "dau": dau, "budget_monthly": 500, "team_size": 3, "team_skills": skills}))["backend"]
             for app in APP_TYPES for dau in (1000, 100000)]
    ok = sum(b in family or b in NEUTRAL for b in picks)
    assert ok >= 0.8 * len(picks), picks
    if "java" in skills:
        assert "dotnet" not in picks


def test_vue_team_skill_fit_nuxt_at_least_nextjs():
    """G2: a Vue team listing JavaScript/TypeScript must not be told Next.js is a better skill match than Nuxt."""
    r = recommend(_scenario("G2"), with_counterfactuals=False)
    assert _raw(r, "frontend", "nuxt")["skill_fit"] >= _raw(r, "frontend", "nextjs")["skill_fit"]
    assert r["stack"]["frontend"]["pick"]["id"] == "nuxt"


def test_known_tool_has_no_learning_curve():
    """A backend the team already ships scores 5/5 on learning curve and carries the 'already ships' bonus."""
    r = recommend({"team_skills": ["java", "spring"]}, with_counterfactuals=False)
    assert _raw(r, "backend", "spring_boot")["ease"] == 5.0
    assert r["stack"]["backend"]["pick"]["id"] == "spring_boot"
    assert any("already ships" in a["reason"] for a in r["stack"]["backend"]["pick"]["adjustments"])


def test_baas_related_skills_capped():
    """Listing SQL and React is not knowing Supabase: related-only skill fit for a BaaS is capped at 3."""
    r = recommend({"team_skills": ["sql", "react"]}, with_counterfactuals=False)
    assert _raw(r, "backend", "supabase")["skill_fit"] <= 3.0


def test_htmx_rare_for_big_teams_but_kept_for_internal_tools():
    """HTMX is penalised for teams of 10+ and rich UIs; a small Django internal tool still gets it."""
    picks = [_picks(_core({"app_type": app, "team_size": team, "team_skills": sk}))["frontend"]
             for app in ("saas", "ecommerce", "fintech") for team in (10, 20, 40)
             for sk in ([], ["python", "django"])]
    assert picks.count("htmx") <= 4, picks
    assert _picks(_core({"app_type": "internal_tool", "team_size": 3, "team_skills": ["python", "django"]}))["frontend"] == "htmx"


def test_java_erp_team_keeps_spring_boot():
    """S24: a 2-person Java/Spring/MySQL team building a college ERP keeps its own framework and database."""
    picks = _picks(_core(_scenario("S24")))
    assert picks["backend"] == "spring_boot" and picks["database"] == "mysql"


def test_rails_team_listing_javascript_keeps_rails():
    """E26: a Rails team that also lists JavaScript (for its frontend) is not moved to an Express backend."""
    assert _picks(_core(_scenario("E26")))["backend"] == "rails"


def test_php_team_news_portal_keeps_php():
    """S09: a PHP + MySQL team building a read-heavy SEO news site gets its own backend, not a BaaS
    nobody on the team has used."""
    r = recommend(_scenario("S09"), with_counterfactuals=False)
    assert r["stack"]["backend"]["pick"]["id"] == "laravel"
    fire = next(x for x in r["stack"]["backend"]["ranking"] if x["id"] == "firebase")
    assert fire["score"] < next(x for x in r["stack"]["backend"]["ranking"] if x["id"] == "laravel")["score"]


def test_unknown_baas_penalised_for_a_server_team():
    r = recommend({"team_skills": ["python", "django"], "team_size": 4}, with_counterfactuals=False)
    supa = _raw(r, "backend", "supabase")
    assert supa["skill_fit"] <= 2.0


def test_php_solo_content_site_frontend_fits():
    """Q08: a solo PHP developer's static content site gets a static generator or server-rendered HTML. The team
    lists no frontend skill, so the frontend's hiring pool decides a tie: Next.js (static export) counts too."""
    r = recommend(_scenario("Q08"), with_counterfactuals=False)
    assert r["stack"]["frontend"]["pick"]["id"] in ("astro", "htmx", "nextjs")
    assert r["stack"]["backend"]["pick"]["id"] == "no_custom_backend"


@pytest.mark.parametrize("team", [10, 15, 30])
def test_no_skills_large_saas_team_is_cloud_neutral(team):
    """With no skills listed the hiring pool stands in for skill match, and a vendor's first-party
    tooling bonus (C# on Azure) does not apply."""
    r = recommend({"app_type": "saas", "team_size": team, "team_skills": []}, with_counterfactuals=False)
    assert "dotnet_azure" not in {c["id"] for c in r["compatibility"]}
    assert r["stack"]["hosting"]["pick"]["id"] != "azure_apps"
    hiring = {x["id"]: load_kb()["index"][x["id"]]["scores"]["hiring"] for x in r["stack"]["backend"]["ranking"][:5]}
    assert hiring[r["stack"]["backend"]["pick"]["id"]] == max(hiring.values())
    assert any(d["input"] == "team_skills" for w in r["weights"] if w["criterion"] == "hiring" for d in w["drivers"])


def test_backend_view_layer_counts_as_a_known_frontend_skill():
    # Rails Hotwire, Laravel Livewire, Phoenix LiveView, Blazor (KB view_layer.interactive): a team that writes such a
    # framework and lists no frontend framework builds server-rendered pages in it rather than hiring for React.
    from engine.scoring import skill_fit
    from engine.kb import load_kb
    htmx = load_kb()["index"]["htmx"]
    assert skill_fit(htmx, {"ruby", "postgres"}) == 4.5
    assert skill_fit(htmx, {"php", "sql", "javascript"}) == 4.5
    assert skill_fit(htmx, {"ruby", "go"}) < 4.5          # may write the backend in Go, which has no view layer
    assert skill_fit(htmx, {"python", "django"}) < 4.5    # plain templates: the interactive parts are JavaScript
    assert skill_fit(htmx, {"java", "spring", "angular"}) < 4.5  # already builds its pages in Angular
    r = recommend({"app_type": "internal_tool", "dau": 50, "team_size": 2, "team_skills": ["ruby", "postgres"],
                   "budget_monthly": 50, "regions": ["north_america"], "seo": "none"}, with_counterfactuals=False)
    assert (r["stack"]["frontend"]["pick"]["id"], r["stack"]["backend"]["pick"]["id"]) == ("htmx", "rails")
    assert "Hotwire" in r["architecture"]["how_parts_fit"][0]["text"]


def test_kotlin_for_the_native_apps_is_not_spring_boot_code():
    """A team that lists Kotlin and Swift for its native apps does not 'already ship' Spring Boot; a Java + Spring
    team that also writes iOS keeps its Spring experience."""
    from engine.kb import load_kb
    from engine.profile import derive, normalize
    from engine.scoring import adjustments

    def ships(skills):
        p, a, w = normalize({"app_type": "mobile_first", "platforms": ["android", "ios", "web"], "team_skills": skills})
        d = derive(p, a, w)
        return any("already ships" in x["reason"] for x in adjustments("backend", load_kb()["index"]["spring_boot"], p, d))
    assert not ships(["go", "kotlin", "swift", "kubernetes"])
    assert ships(["java", "spring", "kotlin", "swift"])
    # A team that lists only the two native app languages builds the apps: it has no server code yet, so Kotlin does
    # not count as Spring Boot experience (red-team t22: three iOS/Android developers).
    assert not ships(["kotlin", "swift"])


def test_typescript_backend_team_without_a_frontend_framework_weighs_the_frontend_hiring_pool():
    """TypeScript carries over to every JavaScript framework alike, so it does not say which one the team knows: the
    frontend with the larger hiring pool leads, not Vue or Svelte by a sub-point margin (red-team t29)."""
    r = recommend({"app_type": "ecommerce", "dau": 20000, "traffic_pattern": "spiky", "architecture": "serverless",
                   "team_size": 3, "team_skills": ["typescript", "node", "aws"], "budget_monthly": 600,
                   "regions": ["india"], "user_actions": ["read", "sign_in", "pay"]}, with_counterfactuals=False)
    assert r["stack"]["frontend"]["pick"]["id"] in ("nextjs", "react_spa")


def test_team_with_an_interactive_view_layer_keeps_server_rendered_pages():
    r = recommend({"app_type": "ecommerce", "dau": 15000, "team_size": 4, "team_skills": ["ruby", "postgres", "javascript"],
                   "budget_monthly": 1500, "regions": ["north_america"], "seo": "important"}, with_counterfactuals=False)
    assert r["stack"]["frontend"]["pick"]["id"] == "htmx"


def test_team_that_lists_neither_native_language_is_not_given_two_new_languages():
    """A C# team building iOS + Android apps: native means Swift and Kotlin, both new; a cross-platform toolkit is one."""
    r = recommend({"app_type": "realtime_collab", "dau": 100000, "platforms": ["android", "ios"], "team_size": 6,
                   "team_skills": ["csharp"], "budget_monthly": 5000, "regions": ["global"], "latency_target_ms": 50,
                   "data_shapes": ["key_value", "relational"], "consistency": "eventual_ok"}, with_counterfactuals=False)
    rank = {c["id"]: c["score"] for c in r["stack"]["frontend"]["ranking"]}
    assert rank["native_mobile"] < rank["flutter"]
    native = next(a for a in r["stack"]["frontend"]["pick"]["adjustments"] if "new languages" in a["reason"])         if r["stack"]["frontend"]["pick"]["id"] == "native_mobile" else None
    assert native is None or native["delta"] < 0
    kotlin = recommend({"app_type": "mobile_first", "platforms": ["android", "ios"], "team_skills": ["kotlin", "swift"]},
                       with_counterfactuals=False)
    assert kotlin["stack"]["frontend"]["pick"]["id"] == "native_mobile"


def test_mobile_only_team_gets_a_backend_as_a_service():
    """Three iOS/Android developers and $500: no server code to keep, so a BaaS is not penalised as setting it aside."""
    r = recommend({"app_type": "social_network", "dau": 20000, "platforms": ["android", "ios"], "team_size": 3,
                   "team_skills": ["swift", "kotlin"], "budget_monthly": 500, "regions": ["north_america"],
                   "special_workloads": ["media_uploads"]}, with_counterfactuals=False)
    assert r["stack"]["backend"]["pick"]["id"] in ("supabase", "firebase")
