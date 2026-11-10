"""SQLite allows one writer at a time for the whole file; its own guide (https://www.sqlite.org/whentouse.html)
puts websites under 100k hits a day, demonstrated up to 10 times that. Past that traffic a client/server
database is the store of record."""
import json
from copy import deepcopy
from pathlib import Path

from engine import recommend
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import SINGLE_WRITER_REALTIME_PENALTY, adjustments, daily_hits_at_tier_floor, hard_constraints

SQLITE = load_kb()["index"]["sqlite"]
KEY = json.loads((Path(__file__).resolve().parent / "benchmark" / "answer_key.json").read_text(encoding="utf-8"))


def _pd(raw):
    p, a, w = normalize(deepcopy(raw))
    return p, derive(p, a, w)


def _traffic_penalty(raw):
    return sum(a["delta"] for a in adjustments("database", SQLITE, *_pd(raw)) if "hits a day" in a["reason"])


def test_penalty_grows_with_daily_requests_between_100k_and_1m():
    small_tool = {"app_type": "internal_tool", "dau": 300}          # Hobby tier: no requests at the tier floor
    shop_small = {"app_type": "ecommerce", "dau": 3000}             # 1k users x 60 requests: under 100k a day
    saas_small = {"app_type": "saas", "dau": 3000}                  # 1k users x 150 requests: 150k a day
    shop_medium = {"app_type": "ecommerce", "dau": 20000}           # 10k users x 60 requests: 600k a day
    assert _traffic_penalty(small_tool) == 0 == _traffic_penalty(shop_small)
    assert 0 > _traffic_penalty(saas_small) > _traffic_penalty(shop_medium) >= -SINGLE_WRITER_REALTIME_PENALTY


def test_same_penalty_at_every_user_count_of_a_tier():
    assert _traffic_penalty({"app_type": "ecommerce", "dau": 10000}) == _traffic_penalty({"app_type": "ecommerce", "dau": 40000})


def test_excluded_past_a_million_requests_a_day():
    p, d = _pd({"app_type": "saas", "dau": 10000})  # 10k users x 150 requests at the tier floor
    assert daily_hits_at_tier_floor(d) > 1_000_000
    reasons = [r for r in hard_constraints("database", SQLITE, p, d) if "requests a day" in r[0]]
    assert reasons and reasons[0][1:] == ("dau", 2)  # a capacity heuristic: relaxed last if nothing else is left
    p, d = _pd({"app_type": "ecommerce", "dau": 10000})  # 600k a day: penalised, not excluded
    assert not [r for r in hard_constraints("database", SQLITE, p, d) if "requests a day" in r[0]]


def test_tight_budget_saas_at_10k_users_gets_a_client_server_database():
    r = recommend({"app_type": "saas", "dau": 10000, "budget_monthly": 25, "team_size": 3, "team_skills": ["php"]},
                  with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] != "sqlite"


def test_college_erp_on_campus_servers_keeps_a_client_server_database():
    brief = next(b for b in KEY["briefs"] if b["id"] == "A04")
    r = recommend(deepcopy(brief["input"]), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] in brief["layers"]["database"]["acceptable"]


def test_sqlite_is_never_the_server_database_for_offline_sync_or_a_stated_999():
    """Offline devices upload their queued changes together into the one server copy, and a stated 99.9% target
    needs a second instance at any user count: a single-writer file database fits neither."""
    field_app = {"app_type": "mobile_first", "platforms": ["android", "ios"], "offline": True,
                 "team_skills": ["dart", "python"], "dau": 2000, "budget_monthly": 100}
    for extra in ({}, {"dau": 100}, {"platforms": ["web"], "app_type": "internal_tool"}):
        r = recommend({**field_app, **extra}, with_counterfactuals=False)
        assert r["stack"]["database"]["pick"]["id"] != "sqlite", extra
        assert "sqlite" in {e["id"] for e in r["stack"]["database"]["excluded"]}, extra
    r = recommend({"availability": "99.9", "dau": 200, "budget_monthly": 0}, with_counterfactuals=False)
    assert "sqlite" in {e["id"] for e in r["stack"]["database"]["excluded"]}
