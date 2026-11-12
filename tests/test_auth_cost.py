"""Sign-in is priced per monthly user from the vendors' pricing pages, and a hosted one that would cost more than
AUTH_SELF_HOST_ABOVE_USD a month gives way: phone codes move into the app, other sign-in to Keycloak."""
import copy
import json
from pathlib import Path

from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent


def _out(name: str, **sections) -> dict:
    doc = copy.deepcopy(json.loads((ROOT / "scenarios" / "public" / f"{name}.json").read_text(encoding="utf-8")))
    for sec, fields in sections.items():
        doc[sec].update(fields)
    return run(doc)


def _auth(out: dict) -> str:
    return next(s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "auth")


def _line(out: dict) -> str | None:
    return next((a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith("Authentication")), None)


def test_social_sign_in_at_fifty_thousand_users_is_clerk_on_its_free_plan():
    p3 = _out("P3")
    assert _auth(p3) == "Clerk" and _line(p3).startswith("Authentication: $0-25 (Clerk's free Hobby plan"), _line(p3)


def test_an_eu_residency_rule_keeps_auth0_in_the_eu_until_it_costs_more_than_running_keycloak():
    small = _out("P3", infrastructure={"data_residency": "eu"}, scale={"users_at_launch": 2000, "users_12_months": 20000})
    assert _auth(small) == "Auth0 (EU tenant)" and "Auth0's Free plan" in _line(small), _line(small)
    big = _out("P3", infrastructure={"data_residency": "eu"})  # 50,000 users: $3,500 a month on B2C Essentials
    assert _auth(big).startswith("Keycloak (self-hosted in your EU region): Auth0 would cost about $3,500"), _auth(big)
    assert _line(big).startswith("Authentication: $60-120 (two containers"), _line(big)


def test_phone_codes_at_scale_move_into_the_app_instead_of_a_per_user_service():
    p4 = _out("P4")  # 300,000 users: Cognito Essentials would be about $4,350 a month
    assert _auth(p4).startswith("Spring Security's one-time token login in your API"), _auth(p4)
    assert "Amazon Cognito would cost about $4,350" in _auth(p4) and _line(p4) is None
    small = _out("P4", scale={"users_at_launch": 2000, "users_12_months": 30000, "peak_concurrent_users": 500})
    assert _auth(small).startswith("Amazon Cognito"), _auth(small)
    assert _line(small).startswith("Authentication: $300-300 (Amazon Cognito Essentials"), _line(small)


def test_a_team_with_no_one_to_run_servers_keeps_costly_sign_in_inside_its_api():
    out = _out("P3", team={"has_devops": False}, scale={"users_at_launch": 20000, "users_12_months": 200000})
    choice = _auth(out)  # 200,000 users: Clerk Pro would be about $3,025 a month and nobody can run Keycloak
    assert "in your API, with the users in your database" in choice and "Clerk would cost about" in choice, choice
    assert not choice.startswith("Keycloak") and _line(out) is None
