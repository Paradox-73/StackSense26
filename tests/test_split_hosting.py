"""Split hosting: a server-framework API on a frontend platform gets its own long-running host
once traffic is large or realtime is core; the frontend platform keeps the pages."""
import sys
from pathlib import Path

import pytest

from engine import recommend
from engine.advice import API_HOST_KINDS
from engine.export import to_markdown
from engine.kb import load_kb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.profiles import profiles  # noqa: E402

FOOD = {"app_type": "ecommerce", "dau": 5_000_000, "budget_monthly": 4_000_000, "currency": "INR",
        "team_skills": ["javascript", "typescript", "react", "node", "sql"]}


def _kind(item_id):
    return load_kb()["index"][item_id]["kind"]


def test_food_delivery_5m_dau_has_a_long_running_api_host():
    for team in (3, 30):
        r = recommend(dict(FOOD, team_size=team), with_counterfactuals=False)
        h = r["stack"]["hosting"]
        if _kind(h["pick"]["id"]) == "frontend_paas":
            api = h["api_host"]
            assert _kind(api["id"]) in API_HOST_KINDS
            assert "long-running" in h["runs_here"] and api["name"] in h["runs_here"]
            assert any(x["component"] == f"API host: {api['name']}" for x in r["cost"]["lines"])
            assert f"API on {api['name']}" in r["summary"]
            notes = " ".join(c["note"] for c in r["compatibility"])
            assert "lose in-memory state" not in notes and "Split hosting" in notes
            md = to_markdown(r)
            assert f"API host: **{api['name']}**" in md
        else:
            assert "as long-running processes" in h["runs_here"]


def test_food_delivery_preset_runs_the_api_long_running(presets):
    r = recommend(presets["india_food_delivery"]["input"], with_counterfactuals=False)
    assert "long-running" in r["stack"]["hosting"]["runs_here"]


def test_small_app_keeps_the_api_on_the_frontend_platform():
    r = recommend(dict(FOOD, dau=10_000, team_size=3), with_counterfactuals=False)
    h = r["stack"]["hosting"]
    assert "api_host" not in h
    assert not [x for x in r["cost"]["lines"] if x["component"].startswith("API host")]


@pytest.mark.parametrize("dau", [3_000, 10_000, 30_000])
def test_core_realtime_gets_an_api_host(dau):
    """Chat app (realtime is core for this app type) on a $25 budget: the WebSocket API always runs in a
    process that stays up. Either the whole stack is on a long-running host, or the static SPA stays on
    the frontend platform and the API gets a long-running host of its own (at 30k users here)."""
    r = recommend({"app_type": "realtime_collab", "dau": dau, "budget_monthly": 25, "team_size": 3,
                   "team_skills": ["javascript", "typescript", "react", "node"]}, with_counterfactuals=False)
    h = r["stack"]["hosting"]
    if _kind(h["pick"]["id"]) == "frontend_paas":
        assert h["api_host"] and "WebSocket" in h["api_host"]["why"]
        assert _kind(h["api_host"]["id"]) in API_HOST_KINDS
    else:
        assert _kind(h["pick"]["id"]) in API_HOST_KINDS and "api_host" not in h
    if dau == 30_000:
        assert _kind(h["pick"]["id"]) == "frontend_paas"


def test_api_host_passes_the_hard_constraints():
    """The API host comes from the hosts that passed the hard constraints (residency, compliance,
    deployment), and the stack's own pick never changes because of the split."""
    seen = 0
    # Split hosting needs a frontend platform and a server backend; most random projects now state long-running or
    # GPU work or many open connections, which rule the platform out, so two seeds that hold such projects are used.
    for inp in profiles(9, 60) + profiles(11, 60):
        r = recommend(inp, with_counterfactuals=False)
        if not r.get("feasible"):
            continue
        h = r["stack"]["hosting"]
        if h.get("api_host"):
            seen += 1
            assert h["api_host"]["id"] in {x["id"] for x in h["ranking"]}
            assert _kind(h["api_host"]["id"]) in API_HOST_KINDS
            assert _kind(h["pick"]["id"]) == "frontend_paas"
            assert load_kb()["index"][r["stack"]["backend"]["pick"]["id"]]["kind"] == "server"
    assert seen
