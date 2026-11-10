"""Vendor SLAs (hosting KB field sla, each with the provider's SLA page) bound the availability a host can be
recommended for, and a host that scales to zero by default is marked down for a strict latency target."""
from engine import recommend
from engine.kb import load_kb, validate_kb
from engine.profile import derive, normalize
from engine.scoring import adjustments, hard_constraints


def _pd(raw):
    p, a, w = normalize(raw)
    return p, derive(p, a, w)


def _sla_excluded(target):
    p, d = _pd({"availability": target})
    return {it["id"] for it in load_kb()["hosting"]
            if any("SLA" in r[0] for r in hard_constraints("hosting", it, p, d))}


def test_sla_facts_are_cited():
    assert not validate_kb()
    idx = load_kb()["index"]
    for hid in ("aws_ecs", "aws_eks", "aws_lambda", "gcp_cloud_run", "gcp_gke", "azure_apps", "digitalocean", "hetzner"):
        assert idx[hid]["sla"]["source"] in idx[hid]["sources"], hid


def test_hosts_whose_sla_is_below_the_target_are_excluded():
    four_nines = _sla_excluded("99.99")
    # EKS: 99.99% with a Provisioned Control Plane and EC2 nodes across zones (EKS and Compute SLA pages); App Service
    # across two or more Availability Zones commits 99.99%, like ECS tasks across zones.
    assert {"digitalocean", "gcp_cloud_run", "gcp_gke", "aws_lambda", "hetzner"} <= four_nines
    assert not {"aws_ecs", "aws_eks", "azure_apps"} & four_nines
    three_nines_five = _sla_excluded("99.95")
    assert {"gcp_gke", "hetzner"} <= three_nines_five
    assert not {"gcp_cloud_run", "digitalocean", "azure_apps", "aws_ecs", "aws_eks"} & three_nines_five
    assert not _sla_excluded("99.9")


def test_solo_developer_at_four_nines_is_not_put_on_a_99_95_platform():
    r = recommend({"app_type": "fintech", "dau": 2000, "availability": "99.99", "team_size": 1,
                   "team_skills": ["python", "django", "sql"], "budget_monthly": 200, "regions": ["north_america"],
                   "user_actions": ["read", "sign_in", "pay"]}, with_counterfactuals=False)
    host = r["stack"]["hosting"]["pick"]["id"]
    sla = load_kb()["index"][host].get("sla")
    assert sla is None or sla["percent"] >= 99.99


def test_scale_to_zero_host_is_marked_down_for_a_strict_latency_target():
    run = load_kb()["index"]["gcp_cloud_run"]
    strict = adjustments("hosting", run, *_pd({"latency_target_ms": 10}))
    relaxed = adjustments("hosting", run, *_pd({"latency_target_ms": 200}))
    assert any("kept warm" in a["reason"] and a["delta"] < 0 for a in strict)
    assert not any("kept warm" in a["reason"] for a in relaxed)


def test_low_latency_trading_api_is_not_on_a_scale_to_zero_host():
    r = recommend({"app_type": "fintech", "dau": 5000, "latency_target_ms": 10, "peak_rps": 20000, "team_size": 8,
                   "team_skills": ["go", "postgres", "linux", "kubernetes"], "budget_monthly": 30000,
                   "regions": ["north_america"], "availability": "99.99", "platforms": ["web"]}, with_counterfactuals=False)
    assert not load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]].get("scale_to_zero")


def test_cloud_bound_database_is_not_paired_with_another_cloud():
    """A content site with sign-in, EU residency and no budget: a database that runs on one cloud only (Firestore,
    DynamoDB, BigQuery) is not paired with compute on another (compat rules *_off_gcp / *_off_aws)."""
    r = recommend({"app_type": "content_site", "regions": ["europe"], "compliance": ["data_residency_eu"], "dau": 5000,
                   "budget_monthly": 0, "user_actions": ["read", "sign_in", "post"]}, with_counterfactuals=False)
    idx = load_kb()["index"]
    db = idx[r["stack"]["database"]["pick"]["id"]]
    host = (r["stack"]["hosting"].get("api_host") or r["stack"]["hosting"]["pick"])["id"]
    assert not db.get("cloud") or db["cloud"] == idx[host].get("provider")


def test_a_host_without_a_published_sla_fails_a_stated_target_above_three_nines():
    assert {"render", "railway", "flyio", "vercel"} <= _sla_excluded("99.95")
    assert not {"render", "onprem_docker"} & _sla_excluded("99.9")
    r = recommend({"app_type": "saas", "availability": "99.99"}, with_counterfactuals=False)
    sla = load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]].get("sla")
    assert sla and sla["percent"] >= 99.99


def test_a_defaulted_availability_does_not_exclude_hosts_by_sla():
    p, d = _pd({"app_type": "saas"})
    assert "availability" in d["defaulted"]
    render = load_kb()["index"]["render"]
    assert not any("SLA" in r[0] for r in hard_constraints("hosting", render, p, d))


def test_each_hyperscaler_sla_cites_its_own_service_page():
    idx = load_kb()["index"]
    assert idx["aws_eks"]["sla"]["source"] == "https://aws.amazon.com/eks/sla/"
    assert idx["aws_ecs"]["sla"]["source"] == "https://aws.amazon.com/ecs/sla/"
    assert idx["aws_lambda"]["sla"]["source"] == "https://aws.amazon.com/lambda/sla/"
    assert idx["gcp_cloud_run"]["sla"]["source"] == "https://cloud.google.com/run/sla"
    assert idx["gcp_gke"]["sla"]["source"] == "https://cloud.google.com/kubernetes-engine/sla"
