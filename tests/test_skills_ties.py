"""A server language nobody listed is penalised, the tie-break prefers the answers the user stressed
before lock-in, and a job queue that stores jobs in Redis pays for the Redis instance."""
import json
from pathlib import Path

from engine import recommend
from engine.advice import estimate_cost, supporting_services
from engine.kb import LAYERS, load_kb
from engine.profile import derive, normalize
from engine.scoring import adjustments

AUDIT = Path(__file__).parent / "scenarios_extra"
FLUTTER_CHAT = {"app_type": "realtime_collab", "platforms": ["android", "ios"], "dau": 100000, "team_size": 3,
                "team_skills": ["dart", "firebase"], "budget_monthly": 500, "realtime": "core"}


def _scenario(prefix):
    for f in AUDIT.glob("*.json"):
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s["name"].startswith(prefix):
                return s["input"]
    raise KeyError(prefix)


def _pd(raw):
    p, a, w = normalize(raw)
    return p, derive(p, a, w)


def test_flutter_firebase_team_does_not_get_elixir():
    """A Dart + Firebase team listed no server language: Elixir/Phoenix was picked on realtime scores alone."""
    for dau in (100000, 1000000):
        r = recommend(dict(FLUTTER_CHAT, dau=dau), with_counterfactuals=False)
        assert r["stack"]["backend"]["pick"]["id"] != "phoenix", dau


def test_unfamiliar_server_language_is_penalised_only_when_skills_are_listed():
    kb = load_kb()
    phoenix = kb["index"]["phoenix"]
    reasons = lambda raw: [a["reason"] for a in adjustments("backend", phoenix, *_pd(raw))]
    assert any("new server language" in x for x in reasons(FLUTTER_CHAT))
    assert not any("new server language" in x for x in reasons(dict(FLUTTER_CHAT, team_skills=[])))
    assert not any("new server language" in x for x in reasons(dict(FLUTTER_CHAT, team_skills=["elixir"])))
    assert not any("new server language" in x for x in reasons(dict(FLUTTER_CHAT, team_skills=["ruby"])))  # adjacent skill


def test_consumer_shop_gets_a_server_rendered_app_framework():
    """J02 and Q14: carts, filters and checkout need more client state than HTMX fragments give, and with SEO
    left unanswered a shop still defaults to SEO important, so a browser-only SPA does not win either."""
    for prefix in ("J02", "Q14"):
        r = recommend(_scenario(prefix), with_counterfactuals=False)
        assert r["stack"]["frontend"]["pick"]["id"] not in ("htmx", "react_spa"), prefix
        assert any(a["field"] == "seo" and a["value"] == "important" for a in r["assumptions"]), prefix


def test_important_inputs_decide_a_tie_before_lock_in():
    # The availability target is stated: left unanswered it is no longer priced as redundant capacity, and the
    # cheaper bill lets the budget guard choose the stack instead of the tie-break this test is about.
    r = recommend(dict(_scenario("Q14"), availability="99.9"), with_counterfactuals=False)
    tb = r["tie_break"]
    assert tb["decided_by"].startswith("your most important inputs"), tb["decided_by"]
    assert "Application type" in tb["decided_by"]


def _jobs(raw, backend, database="postgres", hosting="render"):
    p, d = _pd(raw)
    kb = load_kb()
    stack = {"frontend": kb["index"]["react_spa"], "backend": kb["index"][backend],
             "database": kb["index"][database], "hosting": kb["index"][hosting]}
    svc = supporting_services(p, d, stack, [])
    return p, d, stack, svc


def test_redis_backed_job_queue_costs_the_redis_instance():
    raw = {"app_type": "saas", "dau": 10000, "budget_monthly": 500, "team_size": 3}
    for backend in ("express", "django"):
        p, d, stack, svc = _jobs(raw, backend)
        job = next(s for s in svc if s["role"] == "Background jobs")
        assert job["cost_id"] == "redis" and job["system"] == "redis", backend
        lines = estimate_cost(p, d, stack, svc)["lines"]
        assert sum("Redis" in l["component"] for l in lines) == 1, backend


def test_redis_is_costed_once_when_realtime_already_adds_it():
    raw = {"app_type": "realtime_collab", "dau": 10000, "budget_monthly": 500, "team_size": 3, "realtime": "core"}
    p, d, stack, svc = _jobs(raw, "express", hosting="flyio")
    job = next(s for s in svc if s["role"] == "Background jobs")
    assert job["cost_id"] is None
    assert sum("Redis" in l["component"] for l in estimate_cost(p, d, stack, svc)["lines"]) == 1


def test_rails_uses_its_database_queue_unless_redis_is_already_there():
    """Rails 8's default Solid Queue keeps jobs in the app database; Sidekiq only rides on a Redis the stack has anyway."""
    saas = {"app_type": "saas", "dau": 10000, "budget_monthly": 500, "team_size": 3}
    p, d, stack, svc = _jobs(saas, "rails")
    job = next(s for s in svc if s["role"] == "Background jobs")
    assert job["name"].startswith("Solid Queue") and job["cost_id"] is None
    assert not any("Redis" in l["component"] for l in estimate_cost(p, d, stack, svc)["lines"])
    chat = dict(saas, app_type="realtime_collab", realtime="core")
    job = next(s for s in _jobs(chat, "rails", hosting="flyio")[3] if s["role"] == "Background jobs")
    assert job["name"].startswith("Sidekiq") and job["cost_id"] is None


def test_input_tie_break_ignores_gaps_under_one_stack_point():
    """A gap under INPUT_STEP on an answer does not decide a tie, wherever the two values fall."""
    from engine.stack import pick_tied

    def combo(pts, lock, score):
        return {"picks": {}, "score": score, "no_skills": False, "lock_in_ok": False,
                "_inputs": (["seo", "app_type"], pts), "_tie_key": (0, 0, 0, 0, 0, 0.0, -lock, 0)}
    a = combo({"seo": 1.49, "app_type": 0.0}, 6, 80.0)
    b = combo({"seo": 1.51, "app_type": 0.0}, 5, 79.5)
    assert pick_tied([a, b]) is b  # seo gap 0.02: lock-in decides
    c = combo({"seo": 2.6, "app_type": 0.0}, 9, 79.0)
    assert pick_tied([a, b, c]) is c  # 1.09 ahead of both on the heaviest answer
    d = combo({"seo": 1.0, "app_type": 3.0}, 9, 79.0)
    assert pick_tied([a, d]) is d  # within a step on seo, ahead on the next answer


def test_queue_without_redis_adds_no_redis_line():
    raw = {"app_type": "saas", "dau": 10000, "budget_monthly": 500, "team_size": 3}
    for backend in ("spring_boot", "laravel"):
        p, d, stack, svc = _jobs(raw, backend)
        job = next(s for s in svc if s["role"] == "Background jobs")
        assert job["cost_id"] is None, backend


def test_function_backend_is_not_called_steady_for_a_burst():
    """Near-idle days with a 3,000 req/s burst when sales open: the peak reaches the Large tier but 25k daily users
    do not sustain it, so per-request functions are not marked down as dearer than always-on instances. The same
    peak from 300k daily users, or a stated steady pattern, still is."""
    kb = load_kb()
    faas = kb["index"]["serverless_functions"]
    raw = {"app_type": "saas", "dau": 25000, "peak_rps": 3000, "architecture": "serverless", "team_skills": ["node"]}
    steady = lambda r: any("traffic is steady" in a["reason"] for a in adjustments("backend", faas, *_pd(r)))  # noqa: E731
    assert not steady(raw)
    assert steady(dict(raw, dau=300000))
    assert steady(dict(raw, traffic_pattern="steady"))


def test_stated_architecture_decides_a_tie_before_skills():
    """An AWS-only ticketing SaaS that asked for serverless, with near-idle days and 3,000 req/s bursts: the
    function backend and an Express server are inside the tie margin, and the stated architecture decides."""
    raw = {"app_type": "saas", "platforms": ["web"], "dau": 25000, "peak_rps": 3000, "data_volume_gb": 30,
           "data_growth_gb_month": 5, "read_write": "read_heavy", "data_shapes": ["key_value", "document"],
           "consistency": "strong", "realtime": "some", "latency_target_ms": 200, "seo": "important",
           "availability": "99.95", "regions": ["north_america", "europe"], "team_size": 5,
           "team_skills": ["typescript", "javascript", "react", "node", "aws"], "timeline_weeks": 12,
           "architecture": "serverless", "budget_monthly": 3000, "currency": "USD", "cloud_preference": "aws",
           "lock_in_tolerance": "high", "compliance": ["soc2", "pci_dss"]}
    be = recommend(raw, with_counterfactuals=False)["stack"]["backend"]
    vs = be["explanation"]["vs_runner_up"]
    assert be["pick"]["id"] == "serverless_functions" and vs["tie"]
    assert "on your stated architecture" in vs["text"]
