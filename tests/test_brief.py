"""Brief parser: the pattern reader, schema validation, and the evidence-quote check on model output. No network."""
import json
from pathlib import Path

import pytest

from engine.brief import check_value, parse_brief, quote_in_text, question_keys, validate_llm_fields
from engine.brief_rules import read_all

BRIEF = ("We are the tech team for our college fest and need a site to sell passes and event tickets. About 20,000 students "
         "visit per day. Three of us know React, Node.js and MongoDB, we have 4 weeks, and the college gives us ₹5,000 a month.")


def values(text):
    return {k: h.value for k, h in read_all(text).items()}


def test_rule_parser_reads_numbers_money_skills_and_app_type():
    v = values(BRIEF)
    assert v["dau"] == 20000 and v["team_size"] == 3 and v["timeline_weeks"] == 4
    assert v["budget_monthly"] == 5000 and v["currency"] == "INR"
    assert set(v["team_skills"]) == {"react", "node", "mongodb"} and v["app_type"] == "ecommerce"


@pytest.mark.parametrize("text, amount, currency", [
    ("Our budget is $25/month.", 25, "USD"),
    ("We can spend 50 USD a month on hosting.", 50, "USD"),
    ("Hosting budget of ₹1.2 lakh per year.", 10000, "INR"),
    ("Infra budget is 3 lakh rupees monthly", 300000, "INR"),
    ("We have a zero budget.", 0, None),
    ("Only free tiers are acceptable, free tier only.", 0, None),
])
def test_budget_forms(text, amount, currency):
    v = values(text)
    assert v["budget_monthly"] == amount and v.get("currency") == currency


def test_prices_that_are_not_a_budget_are_ignored():
    assert "budget_monthly" not in values("Each user pays $5 per user for the premium plan.")
    assert "budget_monthly" not in values("Last year we raised $2M.")


def test_monthly_users_are_scaled_to_daily_users():
    assert values("We expect 100k monthly active users.")["dau"] == 20000


def test_team_and_skill_edge_cases():
    assert values("I am working solo on this")["team_size"] == 1
    assert "team_size" not in values("20,000 students use it")  # users are not the team
    assert "react_native" in values("We know React Native")["team_skills"]
    assert "react" not in values("We know React Native")["team_skills"]
    assert "kubernetes" not in values("Nobody on the team knows Kubernetes").get("team_skills", [])
    assert "javascript" not in values("We write Java").get("team_skills", [])


def test_regions_compliance_and_negated_seo():
    v = values("Users in Europe, GDPR applies, data must stay in India. Pages are behind login so search engines do not matter.")
    assert set(v["regions"]) == {"europe", "india"}
    assert set(v["compliance"]) == {"gdpr", "data_residency_india"}
    assert v["seo"] == "none"


def test_every_rule_value_is_valid_and_quoted_from_the_text():
    key = json.loads((Path(__file__).parent / "benchmark" / "answer_key.json").read_text(encoding="utf-8"))
    for brief in key["briefs"]:
        text = brief["brief"]
        result = parse_brief(text, use_llm=False)
        for k, f in result["fields"].items():
            assert check_value(k, f["value"])[1] is None, (brief["id"], k, f["value"])
            assert f["source"] == "rule" and f["quotes"], (brief["id"], k)
            assert all(quote_in_text(q, text) for q in f["quotes"]), (brief["id"], k, f["quotes"])


@pytest.mark.parametrize("key, value, ok", [
    ("dau", 5000, True), ("dau", -1, False), ("dau", "5,000", True), ("dau", "lots", False), ("dau", True, False),
    ("dau", 10 ** 12, False), ("app_type", "saas", True), ("app_type", "blockchain", False),
    ("platforms", ["web", "ios"], True), ("platforms", ["web", "tv"], False), ("platforms", [], False),
    ("offline", True, True), ("offline", "yes", False), ("availability", "99.9", True), ("project_name", "x", False),
    ("not_a_question", 1, False),
])
def test_schema_validation(key, value, ok):
    clean, why = check_value(key, value)
    assert (why is None) is ok


def test_quote_check_ignores_case_and_whitespace_but_not_invented_words():
    text = "We have   a team of\nthree people"
    assert quote_in_text("TEAM OF three", text)
    assert not quote_in_text("team of five", text) and not quote_in_text("", text) and not quote_in_text(None, text)


def test_model_values_without_a_real_quote_or_with_invalid_values_are_dropped():
    text = "Patients book appointments. We need HIPAA. Maybe 300 requests per second at peak."
    dropped = []
    data = {"fields": {
        "app_type": {"value": "healthcare", "quote": "Patients book appointments"},   # kept
        "peak_rps": {"value": 300, "quote": "300  requests per SECOND"},               # kept: case and spaces ignored
        "seo": {"value": "critical", "quote": "must rank first on Google"},            # quote not in text
        "realtime": {"value": "sometimes", "quote": "Patients book"},                  # value not allowed
        "latency_target_ms": {"value": 1, "quote": "Patients"},                        # out of range
        "dau": {"value": 100, "quote": "Patients"},                                    # not an allowed key here
        "offline": "true",                                                             # malformed entry
    }}
    kept = validate_llm_fields(data, text, ["app_type", "peak_rps", "seo", "realtime", "latency_target_ms", "offline"], dropped)
    assert set(kept) == {"app_type", "peak_rps"}
    assert kept["app_type"]["source"] == "llm" and kept["app_type"]["evidence"] == "Patients book appointments"
    assert {d["field"] for d in dropped} == {"seo", "realtime", "latency_target_ms", "offline"}
    assert any("quote" in d["reason"] for d in dropped if d["field"] == "seo")


def test_without_a_key_the_rules_still_answer_and_the_llm_is_reported_off():
    r = parse_brief(BRIEF)
    assert r["llm"] == {"enabled": False, "used": False, "model": None, "error": None, "dropped": []}
    assert r["fields"]["dau"]["source"] == "rule" and "dau" not in r["unknown"] and "peak_rps" in r["unknown"]
    assert set(r["unknown"]) | set(r["fields"]) == set(question_keys())


def test_llm_fills_only_open_fields_and_cannot_override_rules(fake_llm):
    fake = fake_llm({"fields": {
        "dau": {"value": 1, "quote": "20,000 students visit per day"},                 # rules already answered dau
        "data_shapes": {"value": ["document"], "quote": "event tickets"},
        "consistency": {"value": "strong", "quote": "this quote is made up"},
    }})
    r = parse_brief("Event tickets for 20,000 students visit per day. Never sell the same seat twice.")
    assert r["fields"]["dau"]["value"] == 20000 and r["fields"]["dau"]["source"] == "rule"
    assert r["fields"]["data_shapes"]["source"] == "llm" and r["fields"]["data_shapes"]["value"] == ["document"]
    assert "consistency" not in r["fields"] and r["llm"]["dropped"][0]["field"] == "consistency"
    assert r["llm"]["used"] and r["llm"]["model"] == "model/a:free"
    prompt = fake.calls[0][1]["messages"][1]["content"]
    assert '"data_shapes"' in prompt and '"dau"' not in prompt  # only open questions are asked, with their allowed values
    assert '"relational"' in prompt


def test_llm_failure_falls_back_to_rules_and_reports_the_error(fake_llm):
    fake_llm((429, {}))
    r = parse_brief(BRIEF)
    assert r["llm"]["used"] is False and r["llm"]["error"] and "dau" in r["fields"]


def test_a_team_skill_sentence_is_not_evidence_for_a_data_shape():
    text = "We are 5 engineers who know TypeScript and Postgres. We store orders and customers with joins."
    data = {"fields": {"data_shapes": {"value": ["relational"], "quote": "5 engineers who know TypeScript and Postgres"}}}
    dropped = []
    assert validate_llm_fields(data, text, ["data_shapes"], dropped) == {}
    assert "skills" in dropped[0]["reason"]
    data = {"fields": {"data_shapes": {"value": ["relational"], "quote": "store orders and customers with joins"}}}
    assert set(validate_llm_fields(data, text, ["data_shapes"])) == {"data_shapes"}


def test_the_reader_prompt_forbids_filling_a_field_from_another_fields_text():
    from engine.brief import SYSTEM_PROMPT
    assert "skills" in SYSTEM_PROMPT and "THAT question's subject" in SYSTEM_PROMPT


CAMPUS = ("We are 3 students building a campus marketplace app for 5000 students; budget 2000 rupees a month; "
          "we know Python and React.")


def test_audience_size_becomes_daily_users_with_the_assumption_stated():
    hit = read_all(CAMPUS)["dau"]
    assert hit.value == 1000 and hit.quotes == ["for 5000 students"]
    assert "20%" in hit.note and "5,000" in hit.note
    fields = parse_brief(CAMPUS, use_llm=False)["fields"]
    assert fields["dau"]["value"] == 1000 and fields["dau"]["source"] == "rule" and "assumption" in fields["dau"]["note"]


def test_an_explicit_daily_figure_beats_an_audience_size():
    assert values("An app for 5,000 students; about 800 students use it per day.")["dau"] == 800
    assert values("A site for 40,000 customers.")["dau"] == 8000
    assert "dau" not in values("A tool for 3 developers.")  # developers are the team, not an audience


@pytest.mark.parametrize("text, size", [
    ("We are 3 students building a campus marketplace", 3),
    ("We're four friends making a budgeting app", 4),
    ("Two students working on a notes app", 2),
])
def test_we_are_n_students_is_the_team_size(text, size):
    assert values(text)["team_size"] == size


def test_audience_students_are_not_the_team():
    assert "team_size" not in values("A marketplace for 5000 students")
    assert values(CAMPUS)["team_size"] == 3 and values(CAMPUS)["budget_monthly"] == 2000


@pytest.mark.parametrize("text, skills", [
    ("no budget, we know react", {"react"}),
    ("Not much traffic, team knows Django and Postgres", {"django", "postgres"}),
    ("We avoid lock-in, use Python", {"python"}),
    ("we r 2 frnds, no money, flutter devs", {"flutter"}),
    ("No Django experience but we know Python", {"python"}),
    ("We know Java, not Kotlin", {"java"}),
    ("Nobody on the team knows Kubernetes", set()),
    ("we don't know react or vue", set()),
])
def test_negation_stays_inside_its_clause(text, skills):
    assert set(values(text).get("team_skills", [])) == skills


def test_denied_seo_is_none():
    assert values("we don't have SEO needs")["seo"] == "none"
    assert values("No SEO needed.")["seo"] == "none"
    assert values("SEO is critical for us")["seo"] == "critical"


def test_identity_providers_and_credits_are_not_team_skills():
    assert "azure" not in values("needs SSO with Azure AD / Okta. TypeScript team").get("team_skills", [])
    assert "azure" not in values("Login through Microsoft Entra or Azure Active Directory").get("team_skills", [])
    assert "aws" not in values("We have AWS credits. Go and Postgres.").get("team_skills", [])
    assert "azure" in values("Our team knows Azure well")["team_skills"]


def test_concurrent_users_are_concurrency_not_daily_users():
    v = values("Multiplayer quiz for 10,000 concurrent players during live events, spikes to 50k.")
    assert v["peak_concurrent"] == 50000 and "dau" not in v
    v = values("about 5k users online at once and 100k daily users")
    assert v["peak_concurrent"] == 5000 and v["dau"] == 100000
    assert values("must hold 10k open WebSockets")["peak_concurrent"] == 10000


@pytest.mark.parametrize("text,skills", [("Two R programmers and a C developer", {"r", "c"}),
                                         ("we r 2 frnds, plan c is a website", set()),
                                         ("Rust and C++ engineers", {"rust", "cpp"})])
def test_one_letter_language_names_need_a_language_context(text, skills):
    from engine.brief_rules import read_skills
    found = set(read_skills(text).get("team_skills").value) if read_skills(text) else set()
    assert found == skills, found
