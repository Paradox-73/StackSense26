"""Shown text must follow the chosen stack and the user's answers: no service text for a database
that is not in the stack, no regime the user did not select, no load balancer for a hosted backend,
and no knowledge-base line about a technology, region or regime that does not apply."""
import json
import random
from copy import deepcopy

import pytest

from engine import recommend
from engine.advice import BUILTIN_SEARCH
from engine.kb import LAYERS, load_presets
from tools.profiles import random_input

N_RANDOM = 150


@pytest.fixture(scope="module")
def runs():
    inputs = [(p["id"], p["input"]) for p in load_presets()]
    rng = random.Random(4242)
    inputs += [(f"random {i}", random_input(rng)) for i in range(N_RANDOM)]
    out = []
    for name, inp in inputs:
        r = recommend(deepcopy(inp), with_counterfactuals=False)
        if r["feasible"]:
            out.append((name, r))
    return out


@pytest.fixture(scope="module")
def presets():
    return {p["id"]: recommend(deepcopy(p["input"]), with_counterfactuals=False) for p in load_presets()}


def test_search_text_names_the_stack_database(runs):
    for name, r in runs:
        db = r["stack"]["database"]["pick"]["id"]
        for s in r["supporting_services"] + r.get("deferred_services", []):
            if s["role"] != "Search":
                continue
            for dbid, text in BUILTIN_SEARCH.items():
                if text in s["name"]:
                    assert BUILTIN_SEARCH.get(db) == text, (name, db, s["name"])


def test_hosted_backend_has_no_load_balancer_text(runs):
    for name, r in runs:
        if r["stack"]["backend"]["pick"]["id"] in ("supabase", "firebase"):
            assert "load balancer" not in r["architecture"]["redundancy"], (name, r["architecture"]["redundancy"])


def test_audit_text_names_only_selected_regimes(runs):
    names = {"hipaa": "HIPAA", "pci_dss": "PCI-DSS"}
    for name, r in runs:
        comp = r["profile"]["compliance"]
        for s in r["supporting_services"]:
            if s["role"] == "Audit & security":
                for k, label in names.items():
                    assert (label in s["why"]) == (k in comp), (name, comp, s["why"])


def test_hipaa_push_names_the_baa_limit(runs):
    for name, r in runs:
        if "hipaa" in r["profile"]["compliance"]:
            for s in r["supporting_services"]:
                if s["role"] == "Push notifications":
                    assert "BAA" in s["why"], (name, s["why"])


def test_mysql_stack_uses_mysql_fulltext():
    inp = deepcopy(next(p["input"] for p in load_presets() if p["id"] == "india_ecommerce_scale"))
    r = recommend(inp, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "mysql"
    txt = json.dumps(r["supporting_services"])
    assert "Postgres full-text" not in txt


def _kb_lines(r):
    for l in LAYERS:
        e = r["stack"][l]["explanation"]
        yield l, e["strengths"] + e["tradeoffs"]


def test_kb_lines_match_stack_and_answers(runs):
    for name, r in runs:
        p = r["profile"]
        ids = {r["stack"][l]["pick"]["id"] for l in LAYERS}
        india = bool(set(p["regions"]) & {"india", "global"} or set(p["compliance"]) & {"dpdp", "data_residency_india"})
        for l, lines in _kb_lines(r):
            for x in lines:
                if "phoenix" not in ids:
                    assert "Elixir" not in x, (name, l, x)
                if "nextjs" not in ids:
                    assert "OpenNext" not in x and "Next.js deploys" not in x, (name, l, x)
                if not india:
                    assert not any(w in x for w in ("Mumbai", "Hyderabad", "Delhi", "India")), (name, l, x)
                if "hipaa" not in p["compliance"]:
                    assert "HIPAA" not in x, (name, l, x)


def test_conditional_kb_line_appears_where_it_applies(presets):
    hosting = presets["hipaa_telehealth"]["stack"]["hosting"]
    assert hosting["pick"]["id"] == "aws_ecs"
    assert any("BAA" in x for x in hosting["explanation"]["strengths"])
    assert not any("Mumbai" in x for x in hosting["explanation"]["strengths"])


def test_skill_reason_is_never_the_headline_and_names_its_kind(runs):
    for name, r in runs:
        for l in LAYERS:
            why = r["stack"][l]["explanation"]["why"]
            assert not why[0].startswith("Team skill match"), (name, l, why[0])
            skill = [x for x in why if x.startswith("Team skill match")]
            assert len(skill) <= 1, (name, l, skill)
            if skill:
                assert ", direct)" in skill[0] or ", related)" in skill[0], (name, l, skill[0])


SENTENCE_END = __import__("re").compile(r"[.!?](?:\s|$)")


def test_every_layer_has_a_justification_paragraph_with_project_numbers(runs):
    for name, r in runs:
        for l in LAYERS:
            para = r["stack"][l]["explanation"]["paragraph"]
            n = len(SENTENCE_END.findall(para))
            assert 3 <= n <= 5, (name, l, n, para)
            assert any(ch.isdigit() for ch in para), (name, l, para)
            assert "{" not in para and "None" not in para, (name, l, para)


def test_hipaa_hosting_paragraph_names_the_baa(presets):
    para = presets["hipaa_telehealth"]["stack"]["hosting"]["explanation"]["paragraph"]
    assert "Business Associate Agreement" in para and "99.95%" in para


def test_close_calls_say_when_to_choose_the_other(runs):
    for name, r in runs:
        tol = r["profile"]["lock_in_tolerance"]
        for l in LAYERS:
            vs = r["stack"][l]["explanation"]["vs_runner_up"]
            if not vs or not vs["tie"]:
                continue
            if tol == "high":
                assert "lock-in (" not in vs["text"], (name, l, vs["text"])
            assert "kept rather than switching" not in vs["text"]
        tb = r.get("tie_break") or {}
        if tol == "high":
            assert "lock-in" not in (tb.get("decided_by") or ""), (name, tb)


def test_student_tie_is_not_decided_by_lock_in(presets):
    r = presets["student_project"]
    assert r["profile"]["lock_in_tolerance"] == "high"
    for l in LAYERS:
        vs = r["stack"][l]["explanation"]["vs_runner_up"]
        assert not vs or "lock-in (" not in vs["text"], vs["text"]


def test_how_the_parts_fit_has_four_steps(runs):
    for name, r in runs:
        steps = r["architecture"]["how_parts_fit"]
        assert [s["step"] for s in steps] == ["Request path", "Sign-in", "Data", "Deploy"], name
        assert all(s["text"].strip() for s in steps), name
        if "hipaa" in r["profile"]["compliance"]:
            assert "PHI" in steps[2]["text"], (name, steps[2]["text"])
        assert any(ch.isdigit() for ch in r["architecture"]["why"]), (name, r["architecture"]["why"])
