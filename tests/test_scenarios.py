"""End-to-end checks: eight realistic scenarios must produce architecturally sound stacks."""
import pytest

from engine import recommend
from engine.kb import LAYERS, load_kb

from conftest import load_scenarios

SCENARIOS = load_scenarios()


@pytest.fixture(scope="module")
def results():
    return {s["id"]: recommend(s["input"], with_counterfactuals=False) for s in SCENARIOS}


def test_eight_scenarios_present():
    assert len(SCENARIOS) == 8


@pytest.mark.parametrize("scen", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_expectations(scen, results):
    r = results[scen["id"]]
    e = scen["expect"]
    kb = load_kb()
    assert r["feasible"], r["warnings"]
    picks = {l: r["stack"][l]["pick"]["id"] for l in LAYERS}
    for layer, allowed in e.get("pick_in", {}).items():
        assert picks[layer] in allowed, f"{layer}: {picks[layer]} not in {allowed}"
    for layer, banned in e.get("pick_not_in", {}).items():
        assert picks[layer] not in banned, f"{layer}: {picks[layer]} should not be picked"
    for layer, ids in e.get("excluded", {}).items():
        excl = {x["id"] for x in r["stack"][layer]["excluded"]}
        assert set(ids) <= excl, f"{layer}: expected {set(ids) - excl} to be excluded"
    if "max_cost_high" in e:
        assert r["cost"]["total_high"] <= e["max_cost_high"]
    if "max_cost_low" in e:
        assert r["cost"]["total_low"] <= e["max_cost_low"]
    if e.get("companion"):
        assert r["companion"] and r["companion"]["id"] in ("react_native", "flutter", "native_mobile")
    if "hosting_flag" in e:
        assert kb["index"][picks["hosting"]]["compliance"][e["hosting_flag"]]
    if "hosting_provider" in e:
        assert kb["index"][picks["hosting"]]["provider"] == e["hosting_provider"]
    roles = {s["role"] for s in r["supporting_services"]}
    for role in e.get("services_include", []):
        assert role in roles, f"missing supporting service {role}: {roles}"


@pytest.mark.parametrize("scen", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_every_pick_is_explained(scen, results):
    r = results[scen["id"]]
    for layer in LAYERS:
        s = r["stack"][layer]
        ex = s["explanation"]
        assert ex["why"] or ex["strengths"], f"{layer} has no reasons"
        assert ex["tradeoffs"], f"{layer} has no trade-offs"
        assert ex["input_contributions"], f"{layer} has no input attribution"
        assert ex["confidence"] in ("high", "medium", "low")
        if layer == "database":  # weak database alternatives (poor data fit, unused specialty) are not listed
            assert len(s["alternatives"]) <= min(2, len(s["ranking"]) - 1)
        else:
            assert len(s["alternatives"]) == min(2, len(s["ranking"]) - 1)
        assert s["pick"]["sources"], "every pick cites sources"
    assert r["cost"]["total_low"] <= r["cost"]["total_high"]
    assert r["sources"]


def test_residency_respected(results):
    kb = load_kb()
    r = results["india_ecommerce_scale"]
    assert "india" in kb["index"][r["stack"]["hosting"]["pick"]["id"]]["regions"]
    r = results["iot_telemetry"]
    assert "europe" in kb["index"][r["stack"]["hosting"]["pick"]["id"]]["regions"]
