"""Questions are asked as behaviour, not jargon; an unanswered user region favours no region."""
from engine import recommend
from engine.kb import field_specs, load_kb
from engine.scoring import region_fit


def test_jargon_labels_are_reworded():
    specs = field_specs()
    labels = " ".join(s["label"] for s in specs.values())
    for jargon in ("first = primary", "Consistency requirement", "Read / write mix", "p95"):
        assert jargon not in labels, jargon
    assert "main kind first" in specs["data_shapes"]["label"]
    shapes = {o["value"]: o["label"] for o in specs["data_shapes"]["options"]}
    assert "OLAP" not in shapes["analytical"] and "Relational" not in shapes["relational"]


def test_cost_tuning_questions_say_so():
    specs = field_specs()
    for k in ("traffic_pattern", "cacheable_share"):
        assert "Mostly tunes the cost estimate" in specs[k]["help"], k


def test_regions_default_favours_no_region():
    assert field_specs()["regions"]["default"] == []
    hosts = load_kb()["hosting"]
    assert len({region_fit(h, []) for h in hosts}) == 1
    r = recommend({"app_type": "fintech", "user_actions": ["read", "sign_in", "pay"]}, with_counterfactuals=False)
    assert r["profile"]["regions"] == []
    assert "data_residency_india" not in r["profile"]["compliance"]
    assert any(a["field"] == "regions" and "no region is favoured" in a["reason"] for a in r["assumptions"])
    assert "regions you did not state" in r["stack"]["hosting"]["explanation"]["paragraph"]
