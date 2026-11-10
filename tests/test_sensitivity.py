"""'Not sure' support: sensitivity of each layer's pick to answers the user marked unknown,
plus the regulated-at-scale hosting criterion and the glossary that explains every term."""
import json
from pathlib import Path

import pytest

from engine import recommend
from engine.kb import LAYERS, field_specs, load_glossary, load_kb
from engine.sensitivity import MAX_RUNS, options_for, sensitivity

ROOT = Path(__file__).resolve().parent.parent
HYPERSCALERS = {"aws", "gcp", "azure"}


def test_base_matches_recommend_with_defaults():
    s = sensitivity({"app_type": "saas", "dau": 50000}, ["budget_monthly"])
    r = recommend({"app_type": "saas", "dau": 50000}, with_counterfactuals=False)  # budget left at default
    assert s["base"] == {l: r["stack"][l]["pick"]["name"] for l in LAYERS}


def test_unknown_overrides_given_value_with_default():
    """'Not sure' means the default is used even if a stale value is still in the answers."""
    a = sensitivity({"dau": 5_000_000}, ["dau"])
    b = sensitivity({}, ["dau"])
    assert a["base"] == b["base"]


def test_irrelevant_unknown_is_robust():
    s = sensitivity({}, ["project_name"])
    assert s["fields"] == [] and s["robust_layers"] == list(LAYERS) and s["runs"] == 1


def test_scale_unknown_reports_ordered_segments():
    s = sensitivity({"app_type": "saas"}, ["dau"])
    f = s["fields"][0]
    assert f["key"] == "dau" and f["ordered"] and f["tested"] == 6
    assert f["matters"], "a 100,000x range of users must change at least one layer"
    for l in LAYERS:
        segs = f["layers"][l]["segments"]
        assert segs[0]["from"] == 100 and segs[-1]["to"] == 10_000_000
        assert all(a["pick_id"] != b["pick_id"] for a, b in zip(segs, segs[1:])), "segments merge equal neighbours"
        assert f["layers"][l]["robust"] == (len(segs) == 1)
    assert set(s["depends"]) == set(f["matters"])
    assert set(s["robust_layers"]) == set(LAYERS) - set(f["matters"])


def test_compliance_unknown_flips_hosting_to_baa_vendor():
    s = sensitivity({"app_type": "saas"}, ["compliance"])
    kb = load_kb()
    groups = s["fields"][0]["layers"]["hosting"]["groups"]
    hipaa_group = next(g for g in groups if any(o["value"] == ["hipaa"] for o in g["options"]))
    assert kb["index"][hipaa_group["pick_id"]]["compliance"]["hipaa"]


def test_run_cap_is_respected():
    every = list(field_specs())
    s = sensitivity({}, every)
    assert s["runs"] <= MAX_RUNS and s["capped"]
    assert all(f["tested"] >= 2 for f in s["fields"])
    assert len(s["fields"]) + len(s["skipped"]) == sum(1 for k, sp in field_specs().items() if len(options_for(k, sp)) >= 2)


def test_every_question_has_options_or_is_free_text():
    for k, spec in field_specs().items():
        opts = options_for(k, spec)
        # Currency is the unit of the budget, not a fact about the project, so it is never varied on its own.
        assert len(opts) >= 2 or spec["type"] == "text" or k == "currency", k


def test_every_question_has_a_hint():
    for k, spec in field_specs().items():
        assert spec.get("hint") and len(spec["hint"]) <= 200, k


def test_glossary_covers_question_terms():
    g = load_glossary()
    for field, terms in g["field_terms"].items():
        assert field in field_specs(), field
        for t in terms:
            e = g["terms"][t]
            assert e["definition"] and e["applies"] and e["source"].startswith("https://"), t
    official = {"hipaa": "hhs.gov", "gdpr": "europa.eu", "dpdp": "meity.gov.in",
                "pci_dss": "pcisecuritystandards.org", "soc2": "aicpa-cima.com"}
    for t, host in official.items():
        assert host in g["terms"][t]["source"], t


# ----------------------------------------------------------------------------- regulated workloads at scale

def _telehealth(dau):
    s = json.loads((ROOT / "tests" / "scenarios" / "hipaa_telehealth.json").read_text(encoding="utf-8"))
    return recommend(dict(s["input"], dau=dau), with_counterfactuals=False)


@pytest.mark.parametrize("dau", [1_000_000, 10_000_000])
def test_hipaa_at_very_large_scale_picks_hyperscaler(dau, kb):
    r = _telehealth(dau)
    host = kb["index"][r["stack"]["hosting"]["pick"]["id"]]
    assert host["provider"] in HYPERSCALERS, host["name"]
    assert r["stack"]["backend"]["pick"]["id"] != "supabase", "no second multi-tenant processor in the PHI path at 1M+ DAU"
    weights = {x["criterion"]: x for x in r["weights"]}
    assert weights["compliance_maturity"]["weight"] >= 4
    assert any(d["input"] == "dau" for d in weights["compliance_maturity"]["drivers"])


def test_compliance_maturity_is_inert_without_regulated_data():
    r = recommend({"compliance": ["gdpr"], "dau": 2_000_000}, with_counterfactuals=False)
    weights = {x["criterion"]: x["weight"] for x in r["weights"]}
    assert weights.get("compliance_maturity", 0) == 0


def test_hosting_and_baas_carry_cited_maturity(kb):
    for it in kb["hosting"] + [b for b in kb["backend"] if b.get("kind") == "baas"]:
        c = it["compliance"]
        assert 1 <= c["maturity"] <= 5 and c["maturity_note"] and c["maturity_sources"], it["id"]
