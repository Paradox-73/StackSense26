"""Layer paragraphs: the stack-points unit is defined once, an on-prem host is not said to have a cloud region, IoT
counts devices, and the backend sentence follows a service-oriented architecture."""
from engine import recommend
from engine.explain import STACK_POINTS_DEF


def _paras(raw):
    r = recommend(raw, with_counterfactuals=False)
    return [r["stack"][l]["explanation"]["paragraph"] for l in ("frontend", "backend", "database", "hosting")]


def test_stack_points_defined_once():
    paras = _paras({"app_type": "iot_telemetry", "dau": 15_000, "team_skills": ["python", "aws"],
                    "budget_monthly": 1500, "team_size": 4})
    assert sum(STACK_POINTS_DEF in x for x in paras) <= 1
    assert " ".join(paras).count("out of 100 on the whole-stack score") >= 1


def test_iot_counts_devices():
    text = " ".join(_paras({"app_type": "iot_telemetry", "dau": 3_000, "team_size": 3, "budget_monthly": 300}))
    assert "active devices" in text and "daily users" not in text


def test_on_prem_host_runs_in_your_data_centre():
    hosting = _paras({"app_type": "internal_tool", "dau": 3000, "deployment": "on_prem", "budget_monthly": 800,
                      "team_size": 5, "compliance": ["data_residency_india"], "regions": ["india"]})[3]
    assert "own data centre" in hosting and "has a region in India" not in hosting


def test_backend_sentence_follows_service_oriented_architecture():
    backend = _paras({"app_type": "saas", "dau": 60_000, "architecture": "microservices", "budget_monthly": 4000,
                      "team_size": 14})[1]
    if "long-running" in backend:
        assert "one deployable process" not in backend and "services" in backend
