"""Recommendation stability as scale grows, tie handling, and team cloud skills."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from engine import recommend
from engine.kb import LAYERS, load_kb, load_presets
from engine.recommender import BUDGET_GUARD_POINTS, _core, _picks
from engine.sensitivity import sensitivity
from engine.stack import RETURN_MARGIN, TIE_MARGIN

SCEN = Path(__file__).parent / "scenarios"
# The sensitivity sweep's user counts plus the half-decades between them.
DAUS = [100, 300, 1_000, 3_000, 10_000, 30_000, 100_000, 300_000, 1_000_000, 3_000_000, 10_000_000]


def _runs(seq):
    """Collapse consecutive repeats: [a, a, b, b, a] -> [a, b, a]."""
    return [x for i, x in enumerate(seq) if i == 0 or seq[i - 1] != x]


@pytest.mark.parametrize("preset", load_presets(), ids=lambda p: p["id"])
def test_no_flip_back_as_users_grow(preset):
    """With every other answer fixed, raising the user count may change a layer's pick at most
    twice and never back to an earlier pick (no A -> B -> A)."""
    rows = []
    for dau in DAUS:
        raw = deepcopy(preset["input"])
        raw["dau"], raw["peak_rps"] = dau, None
        rows.append(_picks(_core(raw)))
    for layer in LAYERS:
        runs = _runs([r.get(layer) for r in rows])
        assert len(runs) == len(set(runs)), f"{layer} returns to an earlier pick: {' > '.join(map(str, runs))}"
        assert len(runs) <= 3, f"{layer} changes {len(runs) - 1} times: {' > '.join(map(str, runs))}"


def test_sensitivity_dau_segments_never_repeat_a_pick():
    """The /api/sensitivity view of the default SaaS preset: each pick occupies one contiguous range."""
    preset = next(p for p in load_presets() if p["id"] == "startup_mvp")
    out = sensitivity(preset["input"], ["dau"])
    for layer, info in out["fields"][0]["layers"].items():
        ids = [s["pick_id"] for s in info["segments"]]
        assert len(ids) == len(set(ids)), f"{layer}: {ids}"


def test_tie_break_is_explained():
    """When the chosen stack is not the single highest scorer, the summary and the per-layer
    runner-up text both say it was a tie and why this stack won."""
    found = False
    for p in load_presets():
        r = recommend(p["input"], with_counterfactuals=False)
        if not r["feasible"]:
            continue
        tb = r["tie_break"]
        if tb:
            found = True
            if tb.get("budget_guard"):  # a stack that fits the budget, from up to BUDGET_GUARD_POINTS lower
                assert tb["margin"] < BUDGET_GUARD_POINTS + TIE_MARGIN and "budget" in tb["text"]
            elif tb.get("avoided_return"):
                assert tb["margin"] < RETURN_MARGIN and "switch back" in tb["text"]
            elif tb["kept_on_growth_path"]:
                assert tb["margin"] < RETURN_MARGIN and "migrate away and back" in tb["text"]
            else:
                assert tb["margin"] < TIE_MARGIN
                assert "tie margin" in tb["text"]
            assert tb["text"] in r["summary"]
        for layer in LAYERS:
            vs = r["stack"][layer]["explanation"]["vs_runner_up"]
            if vs and abs(vs["margin"]) < TIE_MARGIN:
                assert vs["tie"] and "tie margin" in vs["text"]
                assert "beats" not in vs["text"]  # never claim a win the scores do not show
    assert found, "expected at least one preset to exercise the tie-break"


def _hipaa(dau, cloud):
    raw = json.loads((SCEN / "hipaa_telehealth.json").read_text(encoding="utf-8"))["input"]
    raw["dau"] = dau
    raw["team_skills"] = [s for s in raw["team_skills"] if s not in ("aws", "gcp", "azure")] + [cloud]
    return raw


@pytest.mark.parametrize("dau", [20_000, 1_000_000, 10_000_000])
def test_aws_skilled_team_gets_aws(dau):
    """hipaa_telehealth lists AWS in team_skills and states no cloud preference: hosting stays on AWS
    at every scale instead of moving to Azure for an ASP.NET pairing bonus."""
    r = recommend(_hipaa(dau, "aws"), with_counterfactuals=False)
    host = r["stack"]["hosting"]["pick"]
    assert load_kb()["index"][host["id"]]["provider"] == "aws", host["name"]
    assert any("AWS" in a["reason"] and a["input"] == "team_skills" for a in host["adjustments"])


@pytest.mark.parametrize("cloud", ["aws", "gcp", "azure"])
def test_team_cloud_skill_picks_that_cloud_at_scale(cloud):
    r = recommend(_hipaa(1_000_000, cloud), with_counterfactuals=False)
    host_id = r["stack"]["hosting"]["pick"]["id"]
    assert load_kb()["index"][host_id]["provider"] == cloud


@pytest.mark.parametrize("preset", load_presets(), ids=lambda p: p["id"])
def test_single_run_is_its_tier_on_the_growth_path(preset):
    """Every run works out the recommendation at all scale tiers; its own answer is the entry for its tier,
    so runs at different user counts agree with one another."""
    from engine.kb import load_kb as _kb
    from engine.profile import derive, normalize
    from engine.recommender import _growth_path
    p, a, w = normalize(deepcopy(preset["input"]))
    d = derive(p, a, w)
    picks, _, _, _, _ = _growth_path(_kb(), p, d)
    got = _picks(_core(deepcopy(preset["input"])))
    assert picks[d["compute_tier"]] == tuple(got[l] for l in LAYERS)


def test_an_earlier_pick_is_not_kept_on_a_single_run():
    """Q08 (solo PHP developer, static content site): Nuxt used to be kept because it was the pick one tier
    down; the growth path never comes back to it. The team lists no frontend skill, so among the tied static stacks
    the frontend's hiring pool decides (Next.js; Astro before that rule)."""
    raw = next(s["input"] for s in json.loads((Path(__file__).parent / "scenarios_extra"
                                               / "consumer_quick.json").read_text(encoding="utf-8"))
               if s["name"].startswith("Q08"))
    r = recommend(raw, with_counterfactuals=False)
    assert r["stack"]["frontend"]["pick"]["id"] in ("astro", "nextjs")
    assert not (r.get("tie_break") or {}).get("kept_on_growth_path")


def _combo(score, miss_input=None):
    adj = [{"input": miss_input, "delta": -6, "reason": "x"}] if miss_input else []
    pick = {"id": "a", "name": "A", "score": score, "raw": {}, "item": {"lock_in": 1}, "adjustments": []}
    picks = {l: dict(pick) for l in LAYERS}
    picks["database"] = dict(pick, id=f"db{score}", adjustments=adj)
    return {"picks": picks, "rules": [], "score": score, "no_skills": False, "lock_in_ok": False,
            "defaulted": {"availability"}}


def test_a_tie_goes_to_the_stack_that_meets_the_stated_requirements():
    """Inside the tie margin, a stack whose database misses a stated requirement (here the data shape)
    loses to one that meets it, even when it scores a little higher."""
    from engine.stack import choose
    top, other = _combo(80.0, "data_shapes"), _combo(80.0 - TIE_MARGIN / 2)
    win = choose([top, other])
    assert win is other and "stated requirements" in win["tie_break"]["decided_by"]


def test_a_defaulted_input_does_not_decide_a_tie():
    """An input left at its default is a planning assumption: its penalty is in the score but does not
    count as a missed requirement in the tie-break."""
    from engine.stack import choose
    top, other = _combo(80.0, "availability"), _combo(80.0 - TIE_MARGIN / 2)
    assert choose([top, other]) is top


def test_a_requirement_miss_and_an_over_budget_bill_count_alike():
    """A cheaper stack that misses a stated requirement does not beat one that meets every requirement
    but is over the budget: both are one miss, and the higher score wins."""
    from engine.stack import choose
    over, cheap = _combo(80.0), _combo(80.0 - TIE_MARGIN / 2, "seo")
    assert choose([over, cheap], fits=lambda c: c is cheap) is over


def test_backend_does_not_return_as_users_grow_inside_one_tier():
    """Found by the fuzzer: the tiers a peak reaches above the daily users' tier flickered between 0 and 1 inside one
    tier, so the steady-traffic penalty on functions came and went and the backend went express -> functions ->
    express. The burst is now measured from the peak-to-users ratio, a fixed property of the traffic shape."""
    base = {"app_type": "saas", "platforms": ["web"], "user_actions": ["sign_in"], "special_workloads": ["video_on_demand", "text_search"],
            "tenancy": "isolated", "traffic_pattern": "spiky", "data_volume_gb": 0.61, "data_growth_gb_month": 0,
            "read_write": "write_heavy", "data_shapes": ["key_value"], "realtime": "none", "latency_target_ms": 397.24,
            "seo": "critical", "regions": ["india", "north_america", "europe"], "team_skills": ["node", "mongodb", "linux"],
            "timeline_weeks": 5, "architecture": "serverless", "budget_monthly": 14415.36, "currency": "INR",
            "deployment": "hybrid", "cloud_preference": "gcp", "lock_in_tolerance": "high", "priorities": ["proven"],
            "existing_systems": ["oracle"]}
    seq = [recommend(dict(base, dau=n), with_counterfactuals=False)["stack"]["backend"]["pick"]["id"] for n in DAUS]
    runs = _runs(seq)
    assert len(runs) == len(set(runs)), runs


def test_stated_users_online_lift_every_step_of_the_growth_path():
    """Found by the fuzzer: 1,461 users online at once lift the compute tier at every user count, but the growth path
    lifted only a run's own step, so runs at 1,000 and 3,000 daily users walked different paths and the backend went
    dotnet -> express -> dotnet. No step now sits below the tier of the users online at once."""
    base = {"app_type": "analytics_dashboard", "platforms": ["ios", "web", "android"], "user_actions": ["read", "pay", "post"],
            "special_workloads": ["user_code"], "background_work": "none", "tenancy": "shared", "data_growth_gb_month": 0.05,
            "read_write": "balanced", "data_shapes": ["key_value", "vector"], "consistency": "eventual_ok", "realtime": "none",
            "peak_concurrent": 1461, "latency_target_ms": 48.0, "seo": "important", "offline": False, "regions": ["india"],
            "team_size": 5, "team_skills": [], "timeline_weeks": 24, "architecture": "auto", "budget_monthly": 0,
            "currency": "INR", "deployment": "hybrid", "cloud_preference": "azure", "compliance": ["soc2"],
            "enterprise_sso": False, "priorities": ["cost"], "existing_systems": ["mongodb"]}
    rows = [_picks(_core(dict(base, dau=n))) for n in DAUS]
    for layer in LAYERS:
        runs = _runs([r.get(layer) for r in rows])
        assert len(runs) == len(set(runs)), f"{layer}: {' > '.join(map(str, runs))}"
