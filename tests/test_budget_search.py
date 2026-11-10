"""The budget guard looks past the top 5 options per layer and may change the database or backend."""
from copy import deepcopy

from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.recommender import (_changes, _cheapest_extras, _core, _first_flip_back, _growth_path, _stack_cost,
                               _tier_options, _walk, _wider)
from engine.stack import TOP_K, combo_ids, search

CHAT = {"app_type": "realtime_collab", "dau": 10000, "budget_monthly": 25, "team_size": 1,
        "team_skills": ["javascript", "typescript", "react", "node"]}


# Solo PHP developer, internal tool, $5, ~1 GB of data within a year: past the 1 GB free MySQL plan a managed
# MySQL with its standby is over budget, SQLite on a $5 host is not.
INTERNAL = {"app_type": "internal_tool", "dau": 300, "budget_monthly": 5, "team_size": 1, "team_skills": ["php"],
            "data_volume_gb": 0.5, "data_growth_gb_month": 0.05, "regions": ["india"]}


def test_tight_budget_stack_fits_by_changing_the_database():
    core = _core(INTERNAL)
    best, p, d = core["combos"][0], core["p"], core["d"]
    assert _stack_cost(p, d, best, core["scored"]["database"]) <= d["budget_usd"]
    guard = best["tie_break"]["budget_guard"]
    assert guard["over_cost"] > d["budget_usd"]
    assert guard["over_stack"]["database"] != best["picks"]["database"]["name"]
    assert best["tie_break"]["margin"] <= 5.0 + 1e-9


def test_budget_swap_never_makes_the_growth_path_change_technology_more_often():
    # Realtime chat at $25: PostgreSQL is over budget from 1k users up. Swapping it for SQLite at one tier
    # would mark PostgreSQL as left, so the larger tiers would move on to a third database.
    for inp in (CHAT, INTERNAL):
        p, a, w = normalize(deepcopy(inp))
        d = derive(p, a, w)
        options = _tier_options(load_kb(), p, d)
        narrow, _ = _walk(p, options, [dict() for _ in options], [dict() for _ in options],
                          {k for k, o in enumerate(options) if o is not None})
        assert _changes(_growth_path(load_kb(), p, d)[0]) <= _changes(narrow)


# On-prem analytics app, about $2,600 a month (found at $2,077 before the cost model priced add-ons at the app's
# tier and estimated unanswered data from the scale; the same walk now needs this budget): at larger scales the Kubernetes stack is over budget and the
# narrow guard swapped in a single Docker host, which has no option past 10M users, so the path went
# Kubernetes -> Docker -> Kubernetes (seed 2026 fuzz growth walk).
ONPREM = {"app_type": "analytics_dashboard", "platforms": ["ios"], "user_actions": ["pay"],
          "special_workloads": ["phone_otp"], "dau": 100, "traffic_pattern": "spiky", "cacheable_share": "most",
          "data_growth_gb_month": 0.03, "read_write": "balanced", "data_shapes": ["time_series", "key_value"],
          "consistency": "strong", "latency_target_ms": 196.58, "seo": "critical", "offline": True,
          "availability": "99.0", "regions": ["global"], "team_size": 239,
          "team_skills": ["react", "kubernetes", "react_native", "swift", "aws", "django"],
          "architecture": "serverless", "budget_monthly": 250000, "currency": "INR", "deployment": "on_prem",
          "lock_in_tolerance": "low", "priorities": ["proven", "cost", "performance"]}


def test_budget_guard_never_gives_up_a_technology_the_growth_path_holds():
    p, a, w = normalize(deepcopy(ONPREM))
    d = derive(p, a, w)
    picks, _, holds, _, _ = _growth_path(load_kb(), p, d)
    assert _first_flip_back(picks) is None
    assert {x[3] for x in picks if x} == {"onprem_k8s"}
    assert any(h.get("hosting") == "onprem_k8s" for h in holds)

def test_widened_pool_adds_cheap_options_but_never_a_frontend_or_a_far_worse_option():
    core = _core(CHAT)
    extras = _cheapest_extras(core["scored"], core["p"], core["d"])
    assert "frontend" not in extras
    for layer, cands in extras.items():
        top = core["scored"][layer][0]["score"]
        assert all(c["score"] >= top - 35 and c["id"] not in {x["id"] for x in core["scored"][layer][:TOP_K]}
                   for c in cands)
    wide = search(core["scored"], load_kb()["rules"], core["p"], core["d"], widen=extras)
    narrow = search(core["scored"], load_kb()["rules"], core["p"], core["d"])
    assert len(wide) > len(narrow)
    assert {combo_ids(c) for c in narrow} <= {combo_ids(c) for c in wide}
    assert any(c["picks"][l]["id"] in {x["id"] for x in extras[l]} for c in wide for l in extras)


def test_wider_search_is_remembered_per_window():
    core = _core(CHAT)
    wide = _wider(load_kb(), core["p"], core["d"], core["scored"])
    assert wide(6.0) is wide(6.0)


def test_budget_guard_looks_past_free_plans_to_a_cheap_paid_host():
    """At $5 the hosts outside the top K start with $0-floor free plans; the $5 host the SQLite stack fits on is
    still among the extras the guard searches."""
    core = _core(INTERNAL)
    extras = _cheapest_extras(core["scored"], core["p"], core["d"])["hosting"]
    assert "railway" in [c["id"] for c in extras]
