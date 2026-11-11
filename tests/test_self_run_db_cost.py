"""A database the team runs on its own servers (on-premises, or a VPS host with no managed service for it) costs one
more server of that host at the host's own rates, not a managed service's price band."""
from engine.advice import estimate_cost
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import tier_cost


def _db_line(host_id: str, db_id: str = "postgres", **answers) -> tuple[dict, dict, dict]:
    kb = load_kb()["index"]
    p, a, w = normalize(dict({"app_type": "saas", "dau": 2000, "data_volume_gb": 500, "data_growth_gb_month": 0,
                              "availability": "99.0"}, **answers))
    d = derive(p, a, w)
    stack = {"frontend": kb["react_spa"], "backend": kb["django"], "database": kb[db_id], "hosting": kb[host_id]}
    cost = estimate_cost(p, d, stack, [])
    return next(x for x in cost["lines"] if x["component"].startswith("Database")), p, d


def test_a_database_on_a_vps_is_priced_as_one_more_server_of_that_host():
    line, p, d = _db_line("hetzner")
    lo, hi = tier_cost(load_kb()["index"]["hetzner"], d["db_tier"], p)
    assert (line["low"], line["high"]) == (round(lo * 1.2), round(hi * 1.2)), line  # + Hetzner's 20% backups
    assert "Hetzner" in line["basis"] and "rds" not in line["basis"].lower(), line["basis"]


def test_a_database_on_premises_is_priced_at_the_on_premises_server_band():
    line, p, d = _db_line("onprem_docker", deployment="on_prem")
    lo, hi = tier_cost(load_kb()["index"]["onprem_docker"], d["db_tier"], p)
    assert (line["low"], line["high"]) == (round(lo), round(hi)), line


def test_a_managed_database_keeps_its_managed_price():
    line, p, d = _db_line("aws_ecs")
    assert "server of its own" not in line["basis"], line["basis"]
