"""What a host or a database file can physically do: a file database pins the app to one instance,
a static bucket runs no server code, an ephemeral disk loses a database file, and one writer at a
time cannot carry a write-heavy realtime workload."""
import random

from engine import recommend
from engine.advice import architecture, estimate_cost, single_instance, supporting_services
from engine.kb import LAYERS, load_kb
from engine.profile import derive, normalize
from engine.scoring import adjustments
from engine.stack import matching_rules
from tools.profiles import random_input


def _pd(raw: dict):
    p, a, w = normalize(raw)
    return p, derive(p, a, w)


def _stack(**ids) -> dict:
    kb = load_kb()
    return {l: kb["index"][ids[l]] for l in LAYERS}


def _rule_ids(stack: dict, p: dict, d: dict) -> set:
    return {r["id"] for r in matching_rules(stack, load_kb()["rules"], p, d)}


API = {"app_type": "saas", "dau": 10000, "budget_monthly": 100, "team_size": 3,
       "team_skills": ["javascript", "node"]}


def test_single_file_database_is_priced_as_one_instance_and_says_it_misses_the_target():
    p, d = _pd(dict(API, availability="99.9"))
    one = _stack(frontend="react_spa", backend="express", database="sqlite", hosting="render")
    two = dict(one, database=load_kb()["index"]["postgres"])
    assert single_instance(one) and not single_instance(two)
    host = lambda s: next(l for l in estimate_cost(p, d, s, supporting_services(p, d, s, []))["lines"]
                          if l["component"].startswith("Hosting"))
    h1, h2 = host(one), host(two)
    assert "x1.5" not in h1["basis"] and "one instance" in h1["basis"]
    assert "x1.5" in h2["basis"] and h2["high"] > h1["high"]
    red = architecture(p, d, one)["redundancy"]
    assert "does not meet the 99.9% target" in red and "2+ app instances" not in red


def test_single_file_database_penalty_counts_as_a_miss_at_the_default_target():
    p, d = _pd(API)  # availability left at its 99.9% default
    adj = adjustments("database", load_kb()["index"]["sqlite"], p, d)
    assert any(a["input"] == "availability" and a["delta"] < 0 and a.get("binding") for a in adj)


def test_static_bucket_host_cannot_run_server_code():
    p, d = _pd(dict(API, app_type="content_site", user_actions=["read"]))
    static = _stack(frontend="nextjs", backend="no_custom_backend", database="none_static", hosting="aws_s3_cloudfront")
    server = dict(static, backend=load_kb()["index"]["express"], database=load_kb()["index"]["postgres"])
    assert "static_host_runs_no_server" not in _rule_ids(static, p, d)
    assert "static_host_runs_no_server" in _rule_ids(server, p, d)
    host = load_kb()["index"]["aws_s3_cloudfront"]
    assert host["runs"]["static"] and not any(v for k, v in host["runs"].items() if k != "static")


def test_static_aws_site_gets_the_bucket_not_a_container_service():
    r = recommend({"app_type": "content_site", "dau": 50000, "seo": "critical", "team_size": 2,
                   "team_skills": ["react", "typescript", "aws"], "cloud_preference": "aws",
                   "budget_monthly": 300, "user_actions": ["read"]}, with_counterfactuals=False)
    assert r["stack"]["hosting"]["pick"]["id"] == "aws_s3_cloudfront"
    assert r["stack"]["backend"]["pick"]["id"] == "no_custom_backend"


def test_signing_in_never_gets_a_static_host():
    rng = random.Random(11)
    for _ in range(80):
        raw = random_input(rng)
        raw["user_actions"] = rng.choice([["read", "sign_in"], ["sign_in", "post"]])
        r = recommend(raw, with_counterfactuals=False)
        if r.get("feasible"):
            assert not load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]].get("static_only"), raw


def test_sqlite_on_an_ephemeral_disk_conflicts():
    p, d = _pd(API)
    rules = _rule_ids(_stack(frontend="react_spa", backend="express", database="sqlite", hosting="digitalocean"), p, d)
    assert "sqlite_ephemeral_disk" in rules
    assert "sqlite_ephemeral_disk" not in _rule_ids(
        _stack(frontend="react_spa", backend="express", database="postgres", hosting="digitalocean"), p, d)


CHAT = {"app_type": "realtime_collab", "dau": 2000, "read_write": "write_heavy", "realtime": "core",
        "data_shapes": ["relational", "key_value"], "availability": "99.0", "team_size": 2,
        "team_skills": ["javascript", "react", "node"], "budget_monthly": 0}


def test_one_writer_at_a_time_is_penalised_for_write_heavy_core_realtime():
    sqlite = load_kb()["index"]["sqlite"]
    # The realtime rule (every message is a write); the traffic rule of test_sqlite_traffic.py is separate.
    hit = lambda raw: [a for a in adjustments("database", sqlite, *_pd(raw)) if "every message queues" in a["reason"]]
    assert hit(CHAT)
    assert not hit(dict(CHAT, dau=50))  # a few dozen users (Hobby tier): the lock is not the bottleneck
    assert not hit(dict(CHAT, read_write="balanced"))
    assert not hit(dict(CHAT, app_type="saas", realtime="some"))  # a chat app type forces core realtime
    assert not any("One writer" in a["reason"] for a in adjustments("database", load_kb()["index"]["postgres"], *_pd(CHAT)))
    r = recommend(CHAT, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] != "sqlite"


def test_sqlite_on_a_network_share_conflicts():
    p, d = _pd(API)
    assert "sqlite_network_share" in _rule_ids(
        _stack(frontend="htmx", backend="laravel", database="sqlite", hosting="azure_apps"), p, d)
    assert "sqlite_network_share" not in _rule_ids(
        _stack(frontend="htmx", backend="laravel", database="mysql", hosting="azure_apps"), p, d)


def test_a_database_file_on_a_host_without_a_free_disk_is_not_free():
    raw = {"app_type": "prototype", "dau": 100, "budget_monthly": 0, "team_size": 1, "team_skills": ["python"]}
    p, d = _pd(raw)
    stack = _stack(frontend="htmx", backend="django", database="sqlite", hosting="render")
    floor = load_kb()["index"]["render"]["local_file_disk_min_usd"]
    cost = estimate_cost(p, d, stack, [], usage=False)
    assert cost["total_low"] >= floor and cost["status"] == "over"
    server_db = estimate_cost(p, d, _stack(frontend="htmx", backend="django", database="postgres", hosting="render"),
                              [], usage=False)
    assert not any("persistent disk" in x["basis"] for x in server_db["lines"])


def test_stated_three_nines_for_many_users_never_gets_a_file_database():
    rng = random.Random(5)
    for _ in range(40):
        raw = random_input(rng)
        raw["availability"] = "99.9"
        raw["dau"] = rng.choice([2000, 5000, 20000])
        r = recommend(raw, with_counterfactuals=False)
        if r.get("feasible"):
            assert not load_kb()["index"][r["stack"]["database"]["pick"]["id"]].get("single_node"), raw


def _redundancy_text(hosting, backend="express", database="postgres", **extra):
    p, d = _pd(dict(API, availability="99.9", **extra))
    return architecture(p, d, _stack(frontend="react_spa", backend=backend, database=database, hosting=hosting))["redundancy"]


def test_availability_text_follows_the_host_kind():
    for host in ("aws_lambda", "vercel", "gcp_cloud_run"):
        red = _redundancy_text(host)
        assert "load balancer" not in red and "platform runs the functions across zones" in red, (host, red)
    red = _redundancy_text("render")
    assert "2+ app instances behind a load balancer" in red
    red = _redundancy_text("aws_s3_cloudfront")
    assert "CDN edge" in red and "load balancer" not in red


def test_functions_only_hosting_gets_a_platform_queue():
    p, d = _pd(dict(API, dau=2000))
    for host, want in (("aws_lambda", "SQS"), ("cloudflare", "Cloudflare Queues"), ("vercel", "QStash")):
        svc = supporting_services(p, d, _stack(frontend="react_spa", backend="express", database="postgres", hosting=host), [])
        jobs = next(s["name"] for s in svc if s["role"] == "Background jobs")
        assert want in jobs and "BullMQ" not in jobs, (host, jobs)
    split = dict(_stack(frontend="react_spa", backend="express", database="postgres", hosting="vercel"),
                 api_host=load_kb()["index"]["render"])
    jobs = next(s["name"] for s in supporting_services(p, d, split, []) if s["role"] == "Background jobs")
    assert jobs.startswith("BullMQ") and "Render" in jobs


def test_small_text_search_uses_the_database_index_first():
    raw = dict(API, dau=3000, special_workloads=["text_search"])
    p, d = _pd(raw)
    for db in ("postgres", "mysql"):
        svc = supporting_services(p, d, _stack(frontend="react_spa", backend="express", database=db, hosting="render"), [])
        search = next(s for s in svc if s["role"] == "Search")
        assert search["name"].startswith(("Postgres full-text", "MySQL FULLTEXT")) and not search.get("system"), search


def test_a_managed_database_offering_runs_on_the_hosting_cloud():
    from engine.advice import portable_offering
    names = {"aws": ("AWS", "Amazon"), "gcp": ("Google", "GCP", "GKE", "Compute Engine", "Cloud SQL"), "azure": ("Azure",)}
    kb = load_kb()
    for item in (x for x in kb["index"].values() if x.get("layer") == "database" or "models" in x):
        for cloud in names:
            text = portable_offering(item, {"provider": cloud}, False, False) or ""
            others = [w for c, ws in names.items() if c != cloud for w in ws if f" {w}" in f" {text}"]
            own = any(f" {w}" in f" {text}" for w in names[cloud])
            assert own or not others, (item["id"], cloud, text)  # multi-cloud services name the hosting cloud too


def test_single_host_hosting_fails_a_high_availability_target():
    # Docker Compose places containers on one host: an on-premises project at 99.95%+ gets the option that can
    # fail over between hosts, and a team too small to run it is warned, not handed a host that misses the target.
    base = {"app_type": "fintech", "deployment": "on_prem", "compliance": ["pci_dss"], "team_size": 2,
            "team_skills": ["java"], "dau": 20000, "budget_monthly": 5000}
    for av in ("99.95", "99.99"):
        r = recommend(dict(base, availability=av), with_counterfactuals=False)
        assert r["stack"]["hosting"]["pick"]["id"] == "onprem_k8s", av
        assert "onprem_docker" in {e["id"] for e in r["stack"]["hosting"]["excluded"]}, av
    assert "SLA_SMALL_TEAM" in {w["code"] for w in r["warnings"]}
    r = recommend(dict(base, availability="99.9"), with_counterfactuals=False)
    assert "onprem_docker" not in {e["id"] for e in r["stack"]["hosting"]["excluded"]}


def test_user_code_needs_a_host_with_long_running_workers():
    """Submitted code runs in a sandbox worker pool; functions-only hosts and static buckets are excluded."""
    base = {"app_type": "prototype", "dau": 500, "budget_monthly": 0, "team_skills": ["javascript", "react", "nextjs"],
            "regions": ["india"]}
    assert recommend(base, with_counterfactuals=False)["stack"]["hosting"]["pick"]["id"] == "vercel"
    r = recommend(dict(base, special_workloads=["user_code"]), with_counterfactuals=False)
    host = load_kb()["index"][r["stack"]["hosting"]["pick"]["id"]]
    assert host["runs"]["long_running"]
    out = {e["id"] for e in r["excluded"]["hosting"]}
    assert {"vercel", "netlify", "cloudflare", "aws_lambda"} <= out


def test_live_location_raises_realtime_to_some():
    r = recommend({"app_type": "ecommerce", "special_workloads": ["live_location"]}, with_counterfactuals=False)
    assert r["profile"]["realtime"] == "some"
    r = recommend({"app_type": "ecommerce", "realtime": "core", "special_workloads": ["live_location"]}, with_counterfactuals=False)
    assert r["profile"]["realtime"] == "core"


def test_availability_text_for_a_defaulted_target_says_it_is_not_priced():
    stack = _stack(frontend="react_spa", backend="express", database="postgres", hosting="render")
    p, d = _pd(dict(API))
    assert "availability" in d["defaulted"]
    assert "not priced: no availability target was stated" in architecture(p, d, stack)["redundancy"]
    assert "not priced" not in _redundancy_text("render")
