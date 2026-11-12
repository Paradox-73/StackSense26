"""A database the team runs on its own servers (on-premises, or a VPS host with no managed service for it) costs one
more server of that host at the host's own rates, not a managed service's price band. Like every band, the server's
is read where the project sits in the database tier (engine/scoring.py placed_cost)."""
from engine.advice import estimate_cost, scale_places
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import placed_cost


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
    lo, hi = placed_cost(load_kb()["index"]["hetzner"], d["db_tier"], scale_places(p, d)["db"][0], p)
    assert (line["low"], line["high"]) == (round(lo * 1.2), round(hi * 1.2)), line  # + Hetzner's 20% backups
    assert "Hetzner" in line["basis"] and "rds" not in line["basis"].lower(), line["basis"]


def test_a_database_on_premises_is_priced_at_the_on_premises_server_band():
    line, p, d = _db_line("onprem_docker", deployment="on_prem")
    lo, hi = placed_cost(load_kb()["index"]["onprem_docker"], d["db_tier"], scale_places(p, d)["db"][0], p)
    assert (line["low"], line["high"]) == (round(lo), round(hi)), line


def test_a_managed_database_keeps_its_managed_price():
    line, p, d = _db_line("aws_ecs")
    assert "server of its own" not in line["basis"], line["basis"]


def test_a_file_database_or_content_files_take_no_server_of_their_own():
    from engine.advice import self_run_db
    kb = load_kb()["index"]
    for db in ("sqlite", "none_static"):
        assert not self_run_db(kb[db], kb["onprem_docker"], ""), db


def test_any_database_on_self_managed_vms_is_priced_as_a_server():
    line, p, d = _db_line("aws_ec2", "mongodb", self_managed=True)
    assert "server of its own" in line["basis"], line["basis"]
