"""Every switch (what-if note, 'What would change' line, 'Depends on' entry) names its real cause:
an exclusion, a criterion whose score or weight differs, a penalty or bonus, or a stack rule."""
import re
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from engine import recommend
from engine.kb import load_presets
from engine.recommender import switch_reasons
from engine.sensitivity import sensitivity

CAUSE = re.compile(r"ruled out|hard constraints|/5|penalty|bonus|stack rule|tie-break|compatibility rules|only how it is shown")
GAP = re.compile(r"moved the gap [\d.]+ points toward .+? \((.+?) ([\d.]+)/5 vs (.+?) ([\d.]+)/5(, weight [\d.]+ -> [\d.]+)?")


def _check(why: str, ctx):
    assert why and CAUSE.search(why), (ctx, why)
    for m in GAP.finditer(why):
        # A criterion cited as the cause must actually separate the two picks or have changed weight.
        assert m.group(2) != m.group(4) or m.group(5) or "was " in why, (ctx, why)


@pytest.fixture(scope="module")
def results():
    return {p["id"]: recommend(deepcopy(p["input"])) for p in load_presets()}


def test_every_counterfactual_switch_names_a_cause(results):
    n = 0
    for pid, r in results.items():
        for cf in r["counterfactuals"]:
            for e in cf["effects"]:
                _check(e["why"], (pid, cf["change"], e["layer"]))
                n += 1
    assert n > 50


def test_switch_reason_cites_the_exclusion():
    inp = deepcopy(next(p["input"] for p in load_presets() if p["id"] == "startup_mvp"))
    after = dict(inp, deployment="on_prem")
    sw = switch_reasons(inp, after)
    assert "hosting" in sw and "ruled out" in sw["hosting"]["why"]


def test_switch_api_explains_a_slider_change():
    inp = deepcopy(next(p["input"] for p in load_presets() if p["id"] == "startup_mvp"))
    after = dict(inp, team_size=15)
    res = TestClient(app).post("/api/switch", json={"before": inp, "after": after}).json()
    assert res, "a team of 15 should switch at least one layer"
    for l, x in res.items():
        _check(x["why"], l)
        assert x["from"] != x["to"]


def test_depends_entries_name_a_cause():
    inp = deepcopy(next(p["input"] for p in load_presets() if p["id"] == "startup_mvp"))
    s = sensitivity(inp, ["team_size", "deployment"])
    seen = 0
    for f in s["fields"]:
        for l in f["matters"]:
            for g in f["layers"][l]["groups"]:
                if g["pick"] != s["base"][l] and g["pick_id"]:
                    _check(g["why"], (f["key"], l))
                    seen += 1
    assert seen
