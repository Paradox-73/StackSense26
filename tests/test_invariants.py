"""Fast subset of tools/fuzz.py: must-hold rules on 60 seeded projects, the growth rule on 5.

Run the full version with `python tools/fuzz.py` (10,000 projects, growth rule on 1,000).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import fuzz  # noqa: E402

SEED = 2026
SINGLE_RULES = [r for r in fuzz.RULES if r != "no_flip_back"]


@pytest.fixture(scope="module")
def single_results():
    return [(inp, fuzz.check_profile(inp)) for inp in fuzz.build_profiles(SEED, 60)]


@pytest.mark.parametrize("rule", SINGLE_RULES)
def test_rule_holds(rule, single_results):
    bad = [(msgs, inp) for inp, res in single_results for r, msgs in res.items() if r == rule]
    assert not bad, f"{rule}: {fuzz.RULES[rule]}; first: {bad[0]}"


def test_checker_catches_a_planted_violation():
    """The checker must flag a HIPAA result on a host without a BAA (guards against a checker that passes everything)."""
    r = fuzz._run({"compliance": ["hipaa"]})
    no_baa_host = next(k for k, v in fuzz.KB.items() if "on_prem" in v and not (v.get("compliance") or {}).get("hipaa"))
    r["stack"]["hosting"]["pick"]["id"] = no_baa_host
    assert "hipaa_baa" in fuzz.constraint_violations({}, r)


def test_no_flip_back_as_users_grow():
    growth = fuzz.build_profiles(SEED + 1, 15)[10:]  # same profiles tools/fuzz.py walks
    bad = [(i, res) for i, inp in enumerate(growth, 10) if (res := fuzz.check_growth(inp))]
    assert not bad, bad[:2]
