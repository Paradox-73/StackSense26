"""Read-only sites need no database or server code, and raising the budget never moves the answer
to a stack that no longer fits it."""
import json
import random
from copy import deepcopy
from pathlib import Path

import pytest

from engine import recommend
from engine.kb import load_presets
from tools.profiles import random_input

STATIC = {"none_static", "no_custom_backend"}
AUDIT = Path(__file__).resolve().parent / "scenarios_extra"
LADDER = [0, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 50000]


def _ids(r):
    return {r["stack"][l]["pick"]["id"] for l in ("backend", "database")}


def _audit(name):
    for f in AUDIT.glob("*.json"):
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s["name"].startswith(name):
                return s["input"]
    raise KeyError(name)


def test_read_only_site_needs_no_database_or_server(presets):
    r = recommend(presets["content_site"]["input"], with_counterfactuals=False)
    assert _ids(r) == STATIC
    assert r["cost"]["total_high"] <= 20 and r["cost"]["status"] == "within"
    assert not any(s["role"] == "Authentication" for s in r["supporting_services"])
    assert r["stack"]["database"]["fallback"] and r["stack"]["backend"]["fallback"]
    assert any("sign in, post or pay" in w for w in r["stack"]["database"]["explanation"]["why"])


def test_college_fest_site_at_zero_budget_has_no_critical_warning():
    r = recommend(_audit("J01"), with_counterfactuals=False)
    assert not [w for w in r["warnings"] if w["severity"] == "critical"]
    assert r["cost"]["total_low"] == 0


def test_signing_in_never_gets_a_static_pick():
    rng = random.Random(9)
    for _ in range(120):
        raw = random_input(rng)
        raw["user_actions"] = rng.choice([["read", "sign_in"], ["sign_in", "post"], ["read", "post", "pay"]])
        r = recommend(raw, with_counterfactuals=False)
        if r.get("feasible"):
            assert not _ids(r) & STATIC, raw


def test_other_presets_keep_server_and_database(presets):
    for pid, pr in presets.items():
        if pid != "content_site":
            r = recommend(pr["input"], with_counterfactuals=False)
            if r.get("feasible"):
                assert not _ids(r) & STATIC, pid


CASES = ["startup_mvp", "hipaa_telehealth", "student_project", "content_site", "ml_product", "india_social_mobile"]


@pytest.mark.parametrize("case", CASES + ["J01", "hipaa_startup"])
def test_budget_monotone(presets, case):
    """Going up the budget ladder, a stack whose minimum fitted the new budget is never replaced
    by one whose minimum exceeds it."""
    if case == "hipaa_startup":
        base = {"app_type": "healthcare", "platforms": ["web", "ios", "android"], "dau": 3000, "team_size": 2,
                "compliance": ["hipaa"], "team_skills": ["typescript", "react", "nextjs"], "regions": ["north_america"]}
    elif case == "J01":
        base = _audit("J01")
    else:
        base = deepcopy(presets[case]["input"])
    base["currency"] = "USD"
    prev = None
    for b in LADDER:
        r = recommend(dict(base, budget_monthly=b), with_counterfactuals=False)
        if not r.get("feasible"):
            prev = None
            continue
        low = r["cost"]["total_low"]
        if prev is not None and prev <= b:
            assert low <= b, (case, b, prev, low, r["summary"])
        prev = low


def test_read_only_site_stays_static_for_a_team_with_server_skills():
    """No server code and content files need no skill of their own: a PHP/Vue team's small read-only site
    is static like a JavaScript team's, on a static host, not Laravel on containers."""
    for skills in (["php", "vue"], ["python"], ["javascript", "html", "react"]):
        for dau in (500, 2000, 20000):
            r = recommend({"app_type": "content_site", "user_actions": ["read"], "team_skills": skills,
                           "budget_monthly": 50, "dau": dau}, with_counterfactuals=False)
            assert r["stack"]["backend"]["pick"]["id"] == "no_custom_backend", (skills, dau)
            assert r["stack"]["database"]["pick"]["id"] == "none_static", (skills, dau)
            assert r["stack"]["hosting"]["pick"]["id"] in ("vercel", "netlify", "cloudflare", "aws_s3_cloudfront", "firebase_hosting",
                                                              "azure_static_web_apps", "render", "digitalocean"), (skills, dau)
