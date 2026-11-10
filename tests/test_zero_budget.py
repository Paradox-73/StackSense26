"""A $0 budget: no Redis instance just for a job queue at small scale, and a host with no free plan at all gives way
to one whose free plan passes every hard constraint."""
import pytest

from engine import recommend
from engine.kb import load_kb
from engine.scoring import tier_cost


@pytest.mark.parametrize("skills,dau", [(["python"], 300), (["typescript", "react", "node"], 2500)])
def test_zero_budget_queue_keeps_jobs_in_the_database(skills, dau):
    r = recommend({"app_type": "saas", "dau": dau, "budget_monthly": 0, "team_size": 1, "team_skills": skills},
                  with_counterfactuals=False)
    jobs = [s for s in r["supporting_services"] if s["role"] == "Background jobs"]
    assert all("Redis" not in s["name"] for s in jobs)
    assert not any("Redis" in l["component"] for l in r["cost"]["lines"])


def test_paid_budget_still_uses_the_redis_queue():
    r = recommend({"app_type": "saas", "dau": 300, "budget_monthly": 200, "team_size": 2, "team_skills": ["python"]},
                  with_counterfactuals=False)
    assert any("Redis" in s["name"] for s in r["supporting_services"] if s["role"] == "Background jobs")


@pytest.mark.parametrize("raw", [
    {"app_type": "prototype", "dau": 2500, "budget_monthly": 0, "team_size": 1, "team_skills": ["python"]},
    {"app_type": "internal_tool", "dau": 400, "budget_monthly": 0, "team_size": 1, "team_skills": ["python"]},
    {"app_type": "saas", "dau": 2500, "budget_monthly": 0, "team_size": 1, "team_skills": ["typescript", "react", "node"],
     "realtime": "some"},
])
def test_zero_budget_host_has_a_free_plan(raw):
    r = recommend(raw, with_counterfactuals=False)
    host = load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]]
    assert tier_cost(host, 0, r["profile"])[0] == 0, host["id"]
