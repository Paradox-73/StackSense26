"""Score-noise study: repeatable, and it never changes the cached knowledge base."""
import json
from copy import deepcopy

from engine.kb import LAYERS, load_kb, load_presets
from engine.robustness import robustness

PRESETS = {p["id"]: p["input"] for p in load_presets()}


def test_same_answers_same_percentages_and_kb_untouched():
    before = json.dumps(load_kb(), sort_keys=True, default=str)
    a = robustness(deepcopy(PRESETS["startup_mvp"]), runs=8)
    b = robustness(deepcopy(PRESETS["startup_mvp"]), runs=8)
    assert a == b
    assert json.dumps(load_kb(), sort_keys=True, default=str) == before


def test_clear_winners_hold_under_noise():
    r = robustness(deepcopy(PRESETS["india_ecommerce_scale"]), runs=8)
    for l in LAYERS:
        assert r["layers"][l][0]["held_pct"] >= 75, (l, r["layers"][l])
    for l in LAYERS:
        for row in r["layers"][l]:
            assert 0 <= row["held_pct"] <= 100 and sum(o["pct"] for o in row["others"]) <= 100 - row["held_pct"] + 1


def test_startup_mvp_backend_holds_under_noise():
    """The team-skill window and the budget-fit tie-break keep the startup_mvp backend stable when every
    knowledge-base score is shifted by +/-0.25 (it held in 30-40% of runs before)."""
    r = robustness(deepcopy(PRESETS["startup_mvp"]), runs=10)
    assert r["layers"]["backend"][0]["held_pct"] >= 70, r["layers"]["backend"]
