"""Inputs added for the Synergy '26 schema, tested on the engine's own answers: deployment models (self-managed cloud
VMs, air-gapped), a required cloud, ISO 27001 and US residency, API-only and desktop platforms, team experience and
infrastructure skills, machine-learning features, and the contradiction checks they bring."""
import pytest

from engine import recommend
from engine.kb import load_kb

HYPERSCALERS = {"aws", "gcp", "azure"}
BASE = {"app_type": "saas", "platforms": ["web"], "dau": 5000, "team_size": 4, "budget_monthly": 800,
        "team_skills": ["python"], "timeline_weeks": 12}


def rec(**answers) -> dict:
    return recommend(dict(BASE, **answers), with_counterfactuals=False)


def pick(r: dict, layer: str) -> dict:
    return load_kb()["index"][r["stack"][layer]["pick"]["id"]]


def codes(r: dict) -> dict:
    return {w["code"]: w["severity"] for w in r["warnings"]}


def services(r: dict) -> dict:
    return {s["role"]: s["name"] for s in r["supporting_services"]}


def test_self_managed_cloud_vms_keep_every_server_with_the_team():
    r = rec(cloud_preference="aws", cloud_required=True, self_managed=True, availability="99.95")
    assert r["feasible"] and pick(r, "hosting")["id"] == "aws_ec2"
    assert "Self-managed" in r["stack"]["database"]["managed_offering"]
    assert services(r)["Authentication"] == "Keycloak (self-hosted)"
    assert "RELAXED_CONSTRAINT" not in codes(r)


def test_managed_cloud_never_gets_plain_vms():
    assert not pick(rec(), "hosting").get("vm")


@pytest.mark.parametrize("cloud", ["aws", "gcp", "azure"])
def test_a_required_cloud_is_a_hard_constraint(cloud):
    r = rec(cloud_preference=cloud, cloud_required=True, team_skills=["javascript"])
    assert pick(r, "hosting")["provider"] == cloud


def test_ruling_out_the_big_three_clouds_needs_no_extra_tick():
    r = rec(cloud_preference="no_hyperscaler")
    assert pick(r, "hosting")["provider"] not in HYPERSCALERS


def test_iso27001_and_us_residency_filter_vendors():
    r = rec(compliance=["iso27001", "data_residency_us"])
    host = pick(r, "hosting")
    assert host["compliance"].get("iso27001") and "north_america" in host.get("residency_regions", host["regions"])


def test_air_gapped_runs_on_premises_and_flags_outside_services():
    r = rec(air_gapped=True, platforms=["web", "android"], user_actions=["read", "sign_in", "pay"],
            special_workloads=["phone_otp"])
    assert pick(r, "hosting")["on_prem"] and codes(r)["AIR_GAPPED_EXTERNAL"] == "critical"
    names = " ".join(services(r).values())
    for saas in ("Stripe", "Razorpay", "Twilio", "MSG91", "Firebase", "CloudFront", "Clerk", "Auth0"):
        assert saas not in names, saas


def test_api_only_has_no_frontend_and_desktop_adds_a_shell():
    assert pick(rec(platforms=["api_only"]), "frontend")["kind"] == "none"
    assert pick(rec(platforms=["web", "api_only"]), "frontend")["kind"] != "none"
    assert "Electron" in services(rec(platforms=["web", "desktop"]))["Desktop app"]


def test_beginner_team_promising_four_nines_is_critical():
    r = rec(team_experience="beginner", team_size=1, availability="99.99")
    assert codes(r)["BEGINNER_HIGH_AVAILABILITY"] == "critical"
    assert "BEGINNER_HIGH_AVAILABILITY" not in codes(rec(team_experience="senior", team_size=1, availability="99.99"))


def test_three_platforms_in_three_weeks_is_critical():
    r = rec(platforms=["web", "ios", "android"], timeline_weeks=3)
    assert codes(r)["MANY_PLATFORMS_SHORT_TIMELINE"] == "critical"
    assert "MANY_PLATFORMS_SHORT_TIMELINE" not in codes(rec(platforms=["web", "ios", "android"], timeline_weeks=10))


def test_self_hosting_without_an_operator_is_warned_only_when_stated():
    assert codes(rec(deployment="on_prem", has_devops=False))["SELF_HOSTED_NO_OPS"] == "warning"
    assert "SELF_HOSTED_NO_OPS" not in codes(rec(deployment="on_prem"))


def test_experience_and_infrastructure_skills_move_the_weights():
    def weight(r, criterion):
        return next(b["weight"] for b in r["stack"]["hosting"]["pick"]["breakdown"] if b["criterion"] == criterion)
    beginner, senior = rec(team_experience="beginner"), rec(team_experience="senior")
    assert weight(beginner, "ease") > weight(senior, "ease")
    assert weight(rec(has_devops=False), "ops") > weight(rec(), "ops")


def test_a_scoring_model_gets_a_cpu_endpoint_on_the_projects_cloud():
    r = rec(ml_features="inference_api", cloud_preference="aws", cloud_required=True)
    assert services(r)["Model serving"].startswith("Amazon SageMaker real-time endpoint")
    assert any(x["component"] == "Model serving: CPU endpoint" for x in r["cost"]["lines"])


def test_ruling_out_the_big_three_reaches_services_and_raises_no_preference_warning():
    r = rec(cloud_preference="no_hyperscaler", compliance=["data_residency_india"], special_workloads=["media_uploads"])
    assert "CLOUD_PREFERENCE_OVERRIDDEN" not in codes(r)
    text = " ".join(services(r).values()) + r["stack"]["database"]["managed_offering"]
    assert not [n for n in ("Amazon", "AWS", "Azure", "Google Cloud", "Cloud SQL") if n in text], text
    assert "CLOUD_PREFERENCE_OVERRIDDEN" not in codes(rec(cloud_preference="gcp", cloud_required=True))


def test_self_managed_vps_runs_its_own_database():
    r = rec(self_managed=True, cloud_preference="no_hyperscaler", compliance=["data_residency_eu"])
    assert pick(r, "hosting")["kind"] == "vps"
    assert "Self-managed" in r["stack"]["database"]["managed_offering"]


def test_on_premises_names_its_outside_services_and_serves_uploads_itself():
    r = rec(deployment="on_prem", platforms=["web", "android"], user_actions=["read", "sign_in", "pay"],
            special_workloads=["phone_otp", "media_uploads"])
    assert codes(r)["ONPREM_EXTERNAL"] == "critical" and "AIR_GAPPED_EXTERNAL" not in codes(r)
    assert "nginx" in services(r)["Media delivery"]
    assert "ONPREM_EXTERNAL" not in codes(rec(deployment="on_prem"))


def test_stated_user_actions_without_paying_mean_no_payment_service():
    assert "Payments" in services(rec(app_type="ecommerce"))
    assert "Payments" not in services(rec(app_type="ecommerce", user_actions=["read", "sign_in", "post"]))
