"""The UI sends only the answers the user gave; the engine fills and lists the rest as defaults."""
from copy import deepcopy

from engine import recommend
from engine.export import to_markdown
from engine.kb import LAYERS, field_specs


def _picks(r):
    return {l: r["stack"][l]["pick"]["id"] for l in LAYERS}


def _all_answers(inp):
    full = {k: deepcopy(s.get("default")) for k, s in field_specs().items()}
    full.update(deepcopy(inp))
    return full


def _ui_payload(inp):
    """What the UI sends after loading a preset: every answer the preset states (app.js loadProject)."""
    specs = field_specs()
    return {k: v for k, v in inp.items() if k in specs}


def test_partial_and_full_answers_give_same_picks(presets):
    for pid, p in presets.items():
        partial = recommend(_ui_payload(p["input"]), with_counterfactuals=False)
        full = recommend(_all_answers(p["input"]), with_counterfactuals=False)
        assert _picks(partial) == _picks(full), pid


def test_startup_mvp_lists_defaults_with_labels(presets):
    inp = _ui_payload(presets["startup_mvp"]["input"])
    r = recommend(inp, with_counterfactuals=False)
    defaults = [a for a in r["assumptions"] if a.get("kind") == "default"]
    specs = field_specs()
    assert defaults
    for a in defaults:
        assert a["field"] not in inp
        assert a["label"] == specs[a["field"]]["label"]
    md = to_markdown(r)
    assert "Defaults used" in md and defaults[0]["label"] in md


def test_full_answers_record_no_defaults(presets):
    r = recommend(_all_answers(presets["startup_mvp"]["input"]), with_counterfactuals=False)
    assert not [a for a in r["assumptions"] if a.get("kind") == "default"]
