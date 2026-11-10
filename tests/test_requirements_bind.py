"""A requested monolith binds, availability rules out single-node databases, and small teams or
very tight latency targets are warned about."""
import json
from pathlib import Path

from engine import recommend
from engine.kb import load_kb

AUDIT = Path(__file__).resolve().parent / "scenarios_extra"


def _audit(name):
    for f in AUDIT.glob("*.json"):
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s["name"].startswith(name):
                return s["input"]
    raise KeyError(name)


def _codes(r):
    return {w["code"] for w in r["warnings"]}


def test_monolith_team_gets_no_baas_or_is_told():
    r = recommend(_audit("E11"), with_counterfactuals=False)
    kind = r["stack"]["backend"]["pick"]["id"]
    assert kind not in ("supabase", "firebase", "serverless_functions") or "ARCHITECTURE_OVERRIDDEN" in _codes(r)


def test_monolith_request_never_silently_returns_a_baas():
    for skills in (["supabase", "react"], ["firebase", "javascript"], []):
        r = recommend({"architecture": "monolith", "team_skills": skills}, with_counterfactuals=False)
        if r["stack"]["backend"]["pick"]["id"] in ("supabase", "firebase", "serverless_functions"):
            assert "ARCHITECTURE_OVERRIDDEN" in _codes(r)


def test_single_node_database_excluded_at_high_availability():
    r = recommend({"availability": "99.95", "dau": 200, "budget_monthly": 0}, with_counterfactuals=False)
    assert "sqlite" in {e["id"] for e in r["stack"]["database"]["excluded"]}


def test_four_nines_with_a_small_team_warns():
    assert "SLA_SMALL_TEAM" in _codes(recommend(_audit("E26"), with_counterfactuals=False))


def test_sub_20ms_target_warns_in_one_region():
    assert "LATENCY_TIGHT" in _codes(recommend(_audit("E21"), with_counterfactuals=False))


def test_hybrid_names_portable_services_only():
    r = recommend(_audit("E17"), with_counterfactuals=False)
    names = " ".join(s["name"] for s in r["supporting_services"]) + " " + (r["stack"]["database"]["managed_offering"] or "")
    for aws_only in ("SQS", "Aurora", "Cognito", "CloudWatch", "Kinesis", "ElastiCache", "SageMaker"):
        assert aws_only not in names, aws_only
    assert any(s["role"] == "Hybrid split" for s in r["supporting_services"])


def test_hybrid_split_names_kubernetes_only_on_a_kubernetes_host():
    # A hybrid project on a container host that is not Kubernetes shares container images, not manifests.
    base = {"app_type": "iot_telemetry", "dau": 100000, "peak_rps": 20000, "data_shapes": ["time_series"],
            "read_write": "write_heavy", "data_volume_gb": 1000, "data_growth_gb_month": 2000, "deployment": "hybrid",
            "team_size": 5, "budget_monthly": 8000, "regions": ["europe"], "consistency": "eventual_ok"}
    seen = set()
    for extra in ({"cloud_preference": "azure", "team_skills": ["csharp", "azure", "sql"]},
                  {"cloud_preference": "aws", "team_size": 30, "team_skills": ["go", "kubernetes", "aws"],
                   "architecture": "microservices"}):
        r = recommend(dict(base, **extra), with_counterfactuals=False)
        kind = load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]]["kind"]
        split = next(s["name"] for s in r["supporting_services"] if s["role"] == "Hybrid split")
        assert ("Kubernetes manifests" in split) == (kind == "kubernetes"), (kind, split)
        seen.add(kind == "kubernetes")
    assert seen == {True, False}
