"""A team whose skills match no server language (not even adjacently) hires or learns for the backend, so
the backend's hiring pool counts, as it does when no skills are listed at all."""
from copy import deepcopy

from engine import recommend
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import HIRING_LEVEL_POINTS, adjustments, no_server_language

# 1M daily users, realtime core, 100 ms target, a mobile team that knows Flutter and Firebase.
SOCIAL = {"app_type": "social_network", "platforms": ["android", "ios"], "dau": 1_000_000, "realtime": "core",
          "latency_target_ms": 100, "team_size": 6, "team_skills": ["flutter", "dart", "firebase"],
          "budget_monthly": 20000}


def _hiring_delta(raw, backend):
    p, a, w = normalize(deepcopy(raw))
    d = derive(p, a, w)
    return sum(x["delta"] for x in adjustments("backend", load_kb()["index"][backend], p, d) if "hiring pool" in x["reason"])


def test_only_teams_with_no_server_language_at_all():
    assert no_server_language(frozenset({"flutter", "dart", "firebase"}))
    assert not no_server_language(frozenset({"typescript", "react"}))  # TypeScript is adjacent to Node.js
    assert not no_server_language(frozenset({"python"}))


def test_hiring_pool_moves_the_backend_score():
    kb = load_kb()["index"]
    assert _hiring_delta(SOCIAL, "phoenix") == HIRING_LEVEL_POINTS * (kb["phoenix"]["scores"]["hiring"] - 3) < 0
    assert _hiring_delta(SOCIAL, "express") == HIRING_LEVEL_POINTS * (kb["express"]["scores"]["hiring"] - 3) > 0
    assert _hiring_delta(dict(SOCIAL, team_skills=["typescript", "react"]), "phoenix") == 0
    assert _hiring_delta(dict(SOCIAL, team_skills=[]), "phoenix") == 0  # the hiring weight covers that case


def test_mobile_team_without_a_server_language_is_not_sent_to_the_smallest_hiring_pool():
    r = recommend(SOCIAL, with_counterfactuals=False)
    be = r["stack"]["backend"]["pick"]["id"]
    assert be != "phoenix"
    assert load_kb()["index"][be]["scores"]["hiring"] >= 4


def test_team_with_no_frontend_skill_weighs_the_frontend_hiring_pool():
    """A Python + GCP team lists no frontend skill, so it hires or learns for whichever frontend it picks: the
    frontend's hiring pool counts, as it does for the backend of a team with no server language."""
    from engine.recommender import _core
    x = {"app_type": "ecommerce", "seo": "important", "dau": 2000, "team_skills": ["python", "gcp"],
         "cloud_preference": "gcp", "budget_monthly": 1000}
    scored = {c["id"]: c for c in _core(x)["scored"]["frontend"]}
    assert any("hiring pool 5/5" in a["reason"] for a in scored["nextjs"]["adjustments"])
    assert not any("hiring pool" in a["reason"] for a in scored["sveltekit"]["adjustments"])
    assert recommend(x, with_counterfactuals=False)["stack"]["frontend"]["pick"]["id"] in ("nextjs", "react_spa")
    # A team that lists a frontend skill keeps its own skill match instead.
    scored = {c["id"]: c for c in _core(dict(x, team_skills=["python", "gcp", "svelte"]))["scored"]["frontend"]}
    assert not any("hiring pool" in a["reason"] for a in scored["nextjs"]["adjustments"])
