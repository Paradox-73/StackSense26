"""Users connected at the same moment: an optional answer that sizes the scale tier and, with live updates,
penalises hosts that run code only as request-scoped functions."""
from engine import recommend
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.stack import matching_rules


def _pd(raw):
    p, a, w = normalize(raw)
    return p, derive(p, a, w)


def test_blank_changes_nothing():
    base = {"app_type": "saas", "dau": 5000, "realtime": "some"}
    a = recommend(base, with_counterfactuals=False)
    b = recommend(dict(base, peak_concurrent=None), with_counterfactuals=False)
    assert {l: a["stack"][l]["pick"]["id"] for l in a["stack"]} == {l: b["stack"][l]["pick"]["id"] for l in b["stack"]}
    assert a["cost"] == b["cost"]
    assert not any(x["field"] == "peak_concurrent" for x in a["assumptions"])


def test_ten_thousand_online_is_the_large_tier_and_raises_daily_users():
    p, d = _pd({"app_type": "realtime_collab", "dau": 2000, "peak_concurrent": 10000})
    assert d["compute_tier"] == 3
    assert p["dau"] == 10000
    r = recommend({"app_type": "realtime_collab", "dau": 2000, "peak_concurrent": 10000}, with_counterfactuals=False)
    assert "CONCURRENT_ABOVE_DAU" in {w["code"] for w in r["warnings"]}


def test_concurrency_below_daily_users_keeps_them():
    p, d = _pd({"app_type": "saas", "dau": 200000, "peak_concurrent": 600})
    assert p["dau"] == 200000 and d["compute_tier"] == 3


def test_many_connections_penalise_function_hosts_unless_a_baas_holds_them():
    kb = load_kb()["index"]
    stack = {"frontend": kb["nextjs"], "backend": kb["express"], "database": kb["postgres"], "hosting": kb["vercel"]}
    rules = load_kb()["rules"]
    hit = lambda raw, s=stack: "many_connections_on_functions" in {r["id"] for r in matching_rules(s, rules, *_pd(raw))}
    assert hit({"realtime": "some", "peak_concurrent": 10000})
    assert not hit({"realtime": "some", "peak_concurrent": 500})
    assert not hit({"realtime": "none", "peak_concurrent": 10000})
    assert not hit({"realtime": "some", "peak_concurrent": 10000}, dict(stack, backend=kb["supabase"]))


def test_concurrency_can_move_the_hosting_pick():
    base = {"app_type": "saas", "realtime": "some", "team_skills": ["javascript", "react", "nextjs"],
            "budget_monthly": 300, "dau": 5000}
    a = recommend(base, with_counterfactuals=False)["stack"]
    b = recommend(dict(base, peak_concurrent=10000), with_counterfactuals=False)["stack"]
    assert a["hosting"]["pick"]["id"] != b["hosting"]["pick"]["id"]


def test_the_tier_label_names_users_online_when_they_set_the_tier():
    from engine.export import to_markdown
    r = recommend({"app_type": "realtime_collab", "dau": 60000, "peak_concurrent": 50000, "realtime": "core"})
    line = next(l for l in to_markdown(r).splitlines() if l.startswith("- Scale tier:"))
    assert line.startswith("- Scale tier: Very large (50,000-500,000 users online at once)")
    assert "derived; 50,000 users online at once)" in line
    by_rps = recommend({"app_type": "saas", "dau": 60000}, with_counterfactuals=False)
    assert "users online" not in to_markdown(by_rps)


def test_ten_times_more_or_fewer_users_scales_users_online_too(monkeypatch):
    import engine.recommender as rec
    seen, core = {}, rec._core
    monkeypatch.setattr(rec, "_core", lambda raw, *a, **k: (seen.setdefault(raw.get("dau"), raw), core(raw, *a, **k))[1])
    raw = {"app_type": "realtime_collab", "dau": 60000, "peak_concurrent": 5000, "realtime": "core"}
    p, d = _pd(raw)
    rec._counterfactuals(raw, {"frontend": "react_spa", "backend": "express", "database": "postgres", "hosting": "flyio"}, p, d)
    assert seen[600000]["peak_concurrent"] == 50000
    assert seen[6000]["peak_concurrent"] == 500
