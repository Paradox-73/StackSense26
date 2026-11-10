"""'Why not X?': pinning a layer (or the whole stack) to a named technology and comparing."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from engine import recommend
from engine.export import to_markdown
from engine.kb import LAYERS, load_presets
from engine.whynot import why_not

PRESETS = {p["id"]: p["input"] for p in load_presets()}


@pytest.mark.parametrize("pid", sorted(PRESETS))
def test_grading_the_recommended_stack_returns_its_own_score(pid):
    r = recommend(deepcopy(PRESETS[pid]), with_counterfactuals=False)
    if not r["feasible"]:
        return
    pins = {l: r["stack"][l]["pick"]["id"] for l in LAYERS}
    x = why_not(PRESETS[pid], pins, try_changes=False)
    assert x["ok"] and "already the recommendation" in x["verdict"]
    assert x["stack_score"] == pytest.approx(x["best_score"]) and x["gap"] == 0


def test_hipaa_netlify_shows_the_baa_exclusion():
    x = why_not(PRESETS["hipaa_telehealth"], {"hosting": "netlify"}, try_changes=False)
    assert x["approximate"] and "Business Associate Agreement" in x["verdict"]
    assert x["gap"] > 0


def _content_site_runner_up():
    """content_site's frontend runner-up, which sits inside the tie margin of the pick."""
    r = recommend(deepcopy(PRESETS["content_site"]), with_counterfactuals=False)
    alt = r["stack"]["frontend"]["alternatives"][0]
    assert abs(alt["delta_vs_pick"]) < 1.0, alt
    return alt["id"]


def test_each_returned_change_makes_the_named_choice_win():
    fe = _content_site_runner_up()
    x = why_not(PRESETS["content_site"], {"frontend": fe})
    assert x["changes"], f"some single answer change should make {fe} the pick"
    base = recommend(deepcopy(PRESETS["content_site"]), with_counterfactuals=False)["profile"]
    for c in x["changes"]:
        r = recommend(dict(deepcopy(base), **{c["key"]: c["value"]}), with_counterfactuals=False)
        assert r["stack"]["frontend"]["pick"]["id"] == fe, c


def test_tie_wording_inside_the_margin():
    x = why_not(PRESETS["content_site"], {"frontend": _content_site_runner_up()}, try_changes=False)
    assert x["tie"] and "either is defensible" in x["verdict"]
    assert "-" not in x["verdict"].split("(")[1].split(")")[0]  # a gap is never written as negative


def test_whynot_api():
    res = TestClient(app).post("/api/whynot", json={"answers": PRESETS["hipaa_telehealth"], "pins": {"hosting": "netlify"}}).json()
    assert res["ok"] and res["layers"]["hosting"]["excluded"]
    bad = TestClient(app).post("/api/whynot", json={"answers": {}, "pins": {"hosting": "nope"}}).json()
    assert bad["ok"] is False


def test_why_not_list_covers_runner_up_and_popular_options():
    r = recommend(deepcopy(PRESETS["content_site"]), with_counterfactuals=False)
    md = to_markdown(r)
    ru = r["stack"]["frontend"]["explanation"]["vs_runner_up"]["runner_up"]
    assert f"Why not {ru}?" in md
    for pid in ("hipaa_telehealth", "startup_mvp"):
        r = recommend(deepcopy(PRESETS[pid]), with_counterfactuals=False)
        for l in LAYERS:
            names = {x["name"] for x in r["stack"][l]["why_not"]}
            vs = r["stack"][l]["explanation"]["vs_runner_up"]
            if vs and not r["stack"][l].get("optional_host"):
                assert vs["runner_up"] in names, (pid, l)
