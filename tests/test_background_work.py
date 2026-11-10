"""Background work: jobs over 15 minutes exclude function-only hosts; GPU work keeps only hosts that rent GPUs."""
from engine import recommend
from engine.kb import load_kb

FUNCTION_HOSTS = {"vercel", "netlify", "cloudflare", "aws_lambda"}
BASE = {"app_type": "prototype", "dau": 500, "budget_monthly": 0, "team_skills": ["javascript", "react", "nextjs"],
        "regions": ["india"]}


def _run(**kw):
    return recommend(dict(BASE, **kw), with_counterfactuals=False)


def test_default_changes_nothing():
    a, b = _run(), _run(background_work="none")
    assert {l: a["stack"][l]["pick"]["id"] for l in a["stack"]} == {l: b["stack"][l]["pick"]["id"] for l in b["stack"]}
    assert a["cost"] == b["cost"]
    assert a["stack"]["hosting"]["pick"]["id"] == "vercel"


def test_long_jobs_exclude_function_only_hosts():
    r = _run(background_work="long")
    host = load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]]
    assert host["runs"]["long_running"]
    assert FUNCTION_HOSTS <= {e["id"] for e in r["excluded"]["hosting"]}


def test_gpu_work_keeps_only_gpu_hosts():
    r = _run(background_work="gpu")
    host = load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]]
    assert host["runs"]["gpu"]
    out = {e["id"] for e in r["excluded"]["hosting"]}
    assert {"aws_ecs", "render", "flyio", "digitalocean"} <= out  # Fargate, Render, Fly (GPUs retired), App Platform
    assert any(a["field"] == "background_work" for a in r["assumptions"])


def test_every_gpu_fact_is_cited():
    for h in load_kb()["hosting"]:
        assert isinstance(h["runs"]["gpu"], bool), h["id"]
        if h["runs"]["gpu"]:
            assert h["gpu_source"].startswith("https://"), h["id"]
