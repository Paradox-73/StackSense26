"""Facts refreshed against the vendors' and regulators' pages on 2026-10-09."""
import json
from pathlib import Path

from engine import recommend
from engine.brief_rules import read_all
from engine.kb import load_kb

ROOT = Path(__file__).resolve().parent.parent


def _item(i):
    return load_kb()["index"][i]


def test_netlify_pro_is_20_dollars_with_no_seat_charge():
    n = _item("netlify")
    assert n["cost_usd"][1][0] == 20 and "seat_usd" not in n
    assert any("credits" in str(w) for w in n["weaknesses"])


def test_mongodb_lowest_paid_tier_is_flex_at_8_dollars():
    assert _item("mongodb")["cost_usd"][1][0] == 8


def test_flyio_hipaa_price_cites_the_pricing_page():
    c = _item("flyio")["compliance"]
    assert c["hipaa_min_usd"] == 99 and "https://fly.io/pricing" in c["maturity_sources"]


def test_digitalocean_baa_excludes_app_platform():
    c = _item("digitalocean")["compliance"]
    assert c["hipaa"] is False and "App Platform" in c["maturity_note"]
    assert "https://www.digitalocean.com/trust/hipaa-at-do" in c["maturity_sources"]


def test_firestore_gives_no_fixed_per_document_write_rate():
    assert not any("1 sustained write" in str(w) for w in _item("firestore")["weaknesses"])


def test_survey_citations_are_2025():
    for p in [ROOT / "data" / "glossary.json", ROOT / "data" / "questions.json", ROOT / "data" / "kb" / "frontend.json",
              ROOT / "engine" / "explain.py"]:
        text = p.read_text(encoding="utf-8")
        assert "survey.stackoverflow.co/2024" not in text, p.name


def test_dpdp_rules_2025_are_mentioned():
    g = json.loads((ROOT / "data" / "glossary.json").read_text(encoding="utf-8"))
    assert "DPDP Rules 2025" in g["terms"]["dpdp"]["definition"]
    r = recommend({"app_type": "saas", "compliance": ["dpdp"]}, with_counterfactuals=False)
    assert any("DPDP Rules 2025" in a["reason"] for a in r["assumptions"])


def test_rbi_localisation_is_assumed_only_for_payments():
    lending = {"app_type": "fintech", "regions": ["india"], "user_actions": ["read", "sign_in", "post"]}
    r = recommend(lending, with_counterfactuals=False)
    assert "data_residency_india" not in r["profile"]["compliance"]
    r = recommend(dict(lending, user_actions=["read", "sign_in", "pay"]), with_counterfactuals=False)
    assert "data_residency_india" in r["profile"]["compliance"]
    assert any("payment system providers" in a["reason"] for a in r["assumptions"])


def test_reader_maps_rbi_to_residency_only_with_payments():
    assert "compliance" not in read_all("Fintech lending app, RBI compliant, team of 25")
    assert read_all("Wallet app with UPI payments, RBI regulated")["compliance"].value == ["data_residency_india"]
