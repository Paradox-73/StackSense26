"""The Synergy '26 scenario format: schema of the output, hard constraints on the public scenarios, validation and
determinism (problem statement sections 3-8). The LLM-off switch is tested in tests/test_llm_off.py."""
import json
import re
from pathlib import Path

import pytest

from engine.standard import FIELD_PATHS, run

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = sorted((ROOT / "scenarios" / "public").glob("P*.json"))
STATUSES = {"ok", "ok_with_warnings", "infeasible", "invalid_input"}
STYLES = {"static", "monolith", "modular_monolith", "serverless", "service_oriented", "microservices", "hybrid", "other"}
SUPPORT = {"cache", "queue", "search", "auth", "storage", "cdn", "realtime", "payments", "ml", "ci_cd", "observability",
           "other"}
SAAS = ("Clerk", "Auth0", "Stripe", "Razorpay", "Cloudflare", "CloudFront", "Firebase", "Twilio", "MSG91", "Sentry",
        "Grafana Cloud", "Vercel", "Netlify", "Algolia", "Ably", "Pusher", "GitHub Actions", "Upstash", "Expo")


def load(name: str) -> dict:
    return json.loads((ROOT / "scenarios" / "public" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def outputs() -> dict:
    return {p.stem: run(json.loads(p.read_text(encoding="utf-8"))) for p in PUBLIC}


def check_component(c: dict, core: bool) -> None:
    assert isinstance(c["choice"], str) and c["choice"].strip()
    assert isinstance(c["justification"], str) and len(c["justification"]) > 40
    assert c["driven_by"] and set(c["driven_by"]) <= set(FIELD_PATHS), c["driven_by"]
    assert isinstance(c["alternatives"], list) and isinstance(c["tradeoffs"], list)
    if core:
        assert c["alternatives"], c["choice"]
    for alt in c["alternatives"]:
        assert alt["choice"].strip() and alt["why_not"].strip()


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z$])", text.strip()) if s]


def check_schema(out: dict) -> None:
    assert out["status"] in STATUSES
    assert isinstance(out["summary"], str) and 1 <= len(sentences(out["summary"])) <= 2, out["summary"]
    assert isinstance(out["warnings"], list) and isinstance(out["assumptions"], list)
    assert isinstance(out["validation_errors"], list)
    for w in out["warnings"]:
        assert w["severity"] in ("info", "warning", "critical") and w["code"] and w["message"]
        assert set(w["fields"]) <= set(FIELD_PATHS), w
    assert all(isinstance(a, str) and a for a in out["assumptions"])
    # Section 4: only the stack may be null; the style is always one of the enum strings and the cost always an object.
    assert out["architecture_style"] in STYLES, out["architecture_style"]
    cost = out["estimated_monthly_cost_usd"]
    assert isinstance(cost, dict) and 0 <= cost["min"] <= cost["max"] and cost["assumptions"], cost
    assert all(isinstance(a, str) and a for a in cost["assumptions"])
    if out["status"] == "invalid_input":
        assert out["stack"] is None and out["validation_errors"]
        return
    assert not out["validation_errors"]  # section 4: errors mean invalid_input; a defaulted missing field is a warning
    if out["status"] == "infeasible":
        assert out["stack"] is None and any(w["severity"] == "critical" for w in out["warnings"])
        return
    for layer in ("frontend", "backend", "database", "hosting"):
        check_component(out["stack"][layer], core=True)
    for s in out["stack"]["supporting"]:
        assert s["layer"] in SUPPORT
        check_component(s, core=False)


def test_six_public_scenarios_are_present():
    assert [p.stem for p in PUBLIC] == ["P1", "P2", "P3", "P4", "P5", "P6"]


@pytest.mark.parametrize("name", ["P1", "P2", "P3", "P4", "P5", "P6"])
def test_public_output_follows_the_schema(outputs, name):
    out = outputs[name]
    check_schema(out)
    assert out["status"] in ("ok", "ok_with_warnings") and out["scenario_id"] == name


@pytest.mark.parametrize("doc", [
    None, {"project": "web"},
    {"project": {"type": "healthtech", "platforms": ["web"]}, "scale": {"users_at_launch": 2000, "users_12_months": 20000},
     "team": {"size": 6, "experience": "intermediate", "languages": ["csharp"], "has_devops": True},
     "budget": {"monthly_infra_usd": 2500}, "timeline": {"mvp_weeks": 20},
     "infrastructure": {"cloud_preference": "none", "deployment_model": "self_hosted_cloud_vm", "data_residency": "other"},
     "compliance": ["hipaa", "iso27001"]},
])
def test_outputs_without_a_stack_keep_the_style_and_cost_types(doc):
    out = run(doc)
    assert out["status"] in ("invalid_input", "infeasible") and out["stack"] is None
    check_schema(out)


def test_summaries_are_two_sentences_specific_to_each_scenario(outputs):
    seconds = {}
    for name, out in outputs.items():
        parts = sentences(out["summary"])
        assert len(parts) == 2 and "engineer(s)" not in out["summary"], out["summary"]
        seconds[name] = parts[1]
    assert len(set(seconds.values())) == len(seconds), seconds
    assert "Python" in seconds["P2"] and "India" in seconds["P2"], seconds["P2"]
    assert "SQL Server" in seconds["P5"] and "Entra ID" in seconds["P5"], seconds["P5"]
    assert "offline" in seconds["P6"], seconds["P6"]


def test_explicit_cloud_and_residency_hold(outputs):
    assert "AWS" in outputs["P4"]["stack"]["hosting"]["choice"] and "ap-south-1" in outputs["P4"]["stack"]["hosting"]["choice"]
    assert "Azure" in outputs["P5"]["stack"]["hosting"]["choice"] and "India" in outputs["P5"]["stack"]["hosting"]["choice"]
    for name in ("P2", "P4", "P5", "P6"):
        host = outputs[name]["stack"]["hosting"]["choice"]
        assert any(city in host for city in ("Mumbai", "Pune", "Bangalore", "India")), (name, host)


def test_small_teams_get_no_microservices_or_kubernetes(outputs):
    for name in ("P1", "P2", "P5", "P6"):
        out = outputs[name]
        assert out["architecture_style"] not in ("microservices", "service_oriented"), name
        assert "Kubernetes" not in out["stack"]["hosting"]["choice"], name


def test_zero_budget_portfolio_starts_free(outputs):
    assert outputs["P1"]["estimated_monthly_cost_usd"]["min"] == 0
    assert outputs["P1"]["stack"]["database"]["choice"] == "None"
    assert outputs["P1"]["stack"]["backend"]["choice"] == "None"
    assert "content files in git" in outputs["P1"]["stack"]["database"]["justification"]


def test_same_input_gives_identical_output_in_every_process():
    """FR9. Python salts string hashing per process (PYTHONHASHSEED), so any set order that reached the output would
    differ between two runs; compare every scenario file's output, key order included, across two seeds."""
    import os
    import subprocess
    import sys
    script = ("import json; from pathlib import Path; from engine.standard import run; print(json.dumps("
              "[run(json.loads(p.read_text(encoding='utf-8'))) for p in sorted(Path('scenarios').glob('*/*.json'))]))")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("STACKSENSE_LLM", "OPENROUTER"))}
    outs = [subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=dict(env, PYTHONHASHSEED=seed), capture_output=True,
                           text=True, check=True, timeout=300).stdout for seed in ("1", "2")]
    assert len(json.loads(outs[0])) == 15 and outs[0] == outs[1]


@pytest.mark.parametrize("path,value", [
    ("scale.users_12_months", -5), ("scale.users_12_months", "30000"), ("team.size", 0), ("team.size", 2.5),
    ("project.type", "blockchain"), ("project.platforms", []), ("project.platforms", ["web", "watch"]),
    ("requirements.availability", 99.9), ("requirements.auth", True), ("requirements.p95_latency_ms", 0),
    ("budget.monthly_infra_usd", -1), ("compliance", ["sox"]), ("priorities.cost", 7), ("priorities.speed", 3),
    ("infrastructure.data_residency", "mars"), ("requirements.realtime", "yes"), ("team.languages", "python"),
])
def test_invalid_values_are_field_level_errors(path, value):
    doc = load("P2")
    node = doc
    *parents, leaf = path.split(".")
    for part in parents:
        node = node[part]
    node[leaf] = value
    out = run(doc)
    assert out["status"] == "invalid_input" and out["stack"] is None
    assert path in {e["field"] for e in out["validation_errors"]}, out["validation_errors"]


@pytest.mark.parametrize("doc", [None, [], "P1", 42, {"project": "web"}, {"priorities": [1, 2]}])
def test_malformed_files_never_crash(doc):
    out = run(doc)
    assert out["status"] == "invalid_input" and out["validation_errors"]


def test_missing_required_fields_use_listed_defaults():
    out = run({"scenario_id": "few", "project": {"type": "internal_tool", "platforms": ["web"]}})
    check_schema(out)
    assert out["status"] == "ok_with_warnings"
    missing = {w["fields"][0] for w in out["warnings"] if w["code"] == "MISSING_REQUIRED_FIELD"}
    assert missing == {"scale.users_at_launch", "scale.users_12_months", "team.size", "team.experience",
                       "team.languages", "budget.monthly_infra_usd", "timeline.mvp_weeks"}
    assert any(a.startswith("budget.monthly_infra_usd missing") for a in out["assumptions"])


def test_extra_fields_are_ignored_not_fatal():
    doc = load("P1")
    doc["scale"]["requests_per_second"] = 50
    doc["vendor_lock_in"] = "low"
    out = run(doc)
    assert out["status"] in ("ok", "ok_with_warnings")
    assert {"scale.requests_per_second", "vendor_lock_in"} <= {w["fields"][0] for w in out["warnings"] if w["code"] == "UNKNOWN_FIELD"}


@pytest.mark.parametrize("cloud,word", [("aws", "AWS"), ("gcp", "Google"), ("azure", "Azure")])
def test_explicit_cloud_is_a_hard_constraint(cloud, word):
    doc = load("P2")
    doc["infrastructure"]["cloud_preference"] = cloud
    out = run(doc)
    check_schema(out)
    assert word in out["stack"]["hosting"]["choice"]


# Services an air-gapped network cannot reach: SaaS by name, cloud identity providers, and any CDN.
UNREACHABLE = SAAS + ("Datadog", "New Relic", "Okta", "Entra", "Azure AD", "Google Workspace", "Cognito", "Vonage",
                      "QStash", "SaaS")
CDN = re.compile(r"\bCDN\b")
NO_CDN = re.compile(r"no public CDN|instead of a CDN")


@pytest.mark.parametrize("systems", [[], ["Microsoft Entra ID (Azure AD)", "On-prem SQL Server 2019", "Microsoft 365"]])
def test_air_gapped_stack_has_no_saas_or_cdn(systems):
    doc = load("P5")
    doc["infrastructure"].update(deployment_model="air_gapped", cloud_preference="none", existing_systems=systems)
    out = run(doc)
    check_schema(out)
    parts = [out["stack"][l] for l in ("frontend", "backend", "database", "hosting")] + out["stack"]["supporting"]
    for c in parts:
        assert not [n for n in UNREACHABLE if n in c["choice"]], c["choice"]
        assert not CDN.search(c["choice"]) or NO_CDN.search(c["choice"]), c["choice"]
    watch = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "observability"]
    assert watch and all("self-hosted" in c for c in watch), watch
    assert out["stack"]["hosting"]["choice"].startswith("On-prem")
    unreachable = [w["message"] for w in out["warnings"] if w["code"] == "EXISTING_SYSTEM_UNREACHABLE"]
    assert len(unreachable) == (2 if systems else 0), unreachable


def test_air_gapped_payments_and_sms_are_flagged():
    doc = load("P2")
    doc["infrastructure"].update(deployment_model="air_gapped", cloud_preference="none")
    out = run(doc)
    codes = {w["code"]: w["severity"] for w in out["warnings"]}
    assert codes.get("AIR_GAPPED_EXTERNAL") == "critical", codes
    assert any(a.startswith("Relaxed or flagged (AIR_GAPPED_EXTERNAL)") for a in out["assumptions"])


def test_outside_service_warnings_name_only_the_services_the_project_uses():
    for deploy, code, payment_words in (("air_gapped", "AIR_GAPPED_EXTERNAL", "payments run on a separate connected system"),
                                        ("on_premise", "ONPREM_EXTERNAL", "a payment gateway's hosted checkout")):
        pays, free = ([w for w in edited("P2", infrastructure={"deployment_model": deploy}, requirements={"payments": on})["warnings"]
                       if w["code"] == code][0] for on in (True, False))
        assert payment_words in pays["message"] and "requirements.payments" in pays["fields"], deploy
        assert payment_words not in free["message"] and "requirements.payments" not in free["fields"], free["message"]
        assert "SMS" in free["message"], deploy


def test_api_only_has_no_frontend():
    doc = load("P2")
    doc["project"].update(type="api_platform", platforms=["api_only"])
    doc["requirements"]["seo_critical"] = False
    out = run(doc)
    check_schema(out)
    assert out["stack"]["frontend"]["choice"] == "None"
    assert "API only" in out["stack"]["frontend"]["justification"]


def test_end_of_life_existing_systems_are_warned():
    doc = load("P5")
    doc["infrastructure"]["existing_systems"] = ["SQL Server 2014 on Windows Server 2012 R2", "CentOS 7 file server"]
    out = run(doc)
    eol = [w for w in out["warnings"] if w["code"] == "EOL_EXISTING_SYSTEM"]
    assert len(eol) == 3 and all(w["fields"] == ["infrastructure.existing_systems"] for w in eol)  # SQL Server 2014, Windows Server 2012, CentOS 7


def test_existing_sql_server_is_reused(outputs):
    assert "SQL Server" in outputs["P5"]["stack"]["database"]["choice"]


def test_driven_by_names_the_strongest_inputs_only(outputs):
    for name, out in outputs.items():
        for layer in ("frontend", "backend", "database", "hosting"):
            assert len(out["stack"][layer]["driven_by"]) <= 7, (name, layer)
    assert outputs["P5"]["stack"]["database"]["driven_by"][0] == "infrastructure.existing_systems"
    assert "infrastructure.cloud_preference" in outputs["P5"]["stack"]["hosting"]["driven_by"]


def edited(name: str, **sections) -> dict:
    doc = load(name)
    for sec, values in sections.items():
        doc[sec].update(values)
    return run(doc)


def codes(out: dict) -> dict:
    return {w["code"]: w["severity"] for w in out["warnings"]}


def test_public_cloud_with_on_premise_is_a_critical_conflict():
    out = edited("P5", infrastructure={"deployment_model": "on_premise", "cloud_preference": "azure"})
    assert codes(out)["CLOUD_VS_DEPLOYMENT"] == "critical"
    assert out["stack"]["hosting"]["choice"].startswith("On-prem")
    assert any("Relaxed: infrastructure.cloud_preference" in a for a in out["assumptions"])


def test_rbi_localisation_with_eu_residency_is_a_critical_conflict():
    out = edited("P4", infrastructure={"data_residency": "eu"})
    assert codes(out)["RESIDENCY_CONFLICT"] == "critical"


def test_unnamed_residency_country_is_a_warning():
    out = edited("P2", infrastructure={"data_residency": "other"})
    assert codes(out)["RESIDENCY_UNVERIFIED"] == "warning"


def test_enterprise_availability_from_a_beginner_solo_developer_is_critical():
    doc = load("P1")
    doc["requirements"].update(availability="99.99", auth="email_password")
    out = run(doc)
    assert codes(out)["BEGINNER_HIGH_AVAILABILITY"] == "critical"
    assert out["status"] == "ok_with_warnings" and out["stack"] is not None
    doc["team"]["experience"] = "senior"
    assert "BEGINNER_HIGH_AVAILABILITY" not in codes(run(doc))


def test_many_platforms_on_a_short_timeline_is_critical():
    out = edited("P2", project={"platforms": ["web", "android", "ios", "desktop"]}, timeline={"mvp_weeks": 3})
    assert codes(out)["MANY_PLATFORMS_SHORT_TIMELINE"] == "critical"
    assert "MANY_PLATFORMS_SHORT_TIMELINE" not in codes(edited("P2", timeline={"mvp_weeks": 3}))


def test_self_hosted_servers_without_operators_are_warned():
    assert codes(edited("P5", infrastructure={"deployment_model": "on_premise", "cloud_preference": "any"}))[
        "SELF_HOSTED_NO_OPS"] == "warning"
    assert "SELF_HOSTED_NO_OPS" not in codes(edited("P5", team={"has_devops": True},
                                                    infrastructure={"deployment_model": "on_premise", "cloud_preference": "any"}))


def test_self_hosted_cloud_vms_run_every_server_themselves():
    out = edited("P4", infrastructure={"deployment_model": "self_hosted_cloud_vm"})
    check_schema(out)
    stack = out["stack"]
    assert stack["hosting"]["choice"].startswith("AWS EC2 VMs") and "ap-south-1" in stack["hosting"]["choice"]
    assert "Self-managed" in stack["database"]["choice"]
    auth = [s["choice"] for s in stack["supporting"] if s["layer"] == "auth"]
    assert any("Keycloak" in a for a in auth) and not any("Cognito" in a for a in auth)
    assert not any(w["code"] == "RELAXED_CONSTRAINT" for w in out["warnings"])


def test_a_scoring_model_is_served_from_a_cpu_endpoint(outputs):
    ml = [s["choice"] for s in outputs["P4"]["stack"]["supporting"] if s["layer"] == "ml"]
    assert len(ml) == 1 and ml[0].startswith("Amazon SageMaker real-time endpoint")


def test_existing_systems_in_extended_support_get_an_info_note(outputs):
    notes = [w for w in outputs["P5"]["warnings"] if w["code"] == "EXISTING_SYSTEM_EXTENDED_SUPPORT"]
    assert len(notes) == 1 and notes[0]["severity"] == "info" and "2030" in notes[0]["message"]
    assert outputs["P5"]["status"] == "ok"


def test_search_is_added_only_when_the_scenario_asks_for_it(outputs):
    assert "search" not in {s["layer"] for s in outputs["P1"]["stack"]["supporting"]}
    assert any("full_text_search is false" in a for a in outputs["P1"]["assumptions"])
    assert "search" in {s["layer"] for s in outputs["P2"]["stack"]["supporting"]}


def core(out: dict) -> list[str]:
    return [out["stack"][l]["choice"] for l in ("frontend", "backend", "database", "hosting")]


@pytest.mark.parametrize("name", ["P1", "P2", "P3", "P4", "P5", "P6"])
def test_small_input_changes_give_local_changes(name, outputs):
    """Judges run modified copies of the public scenarios: a rename, a reordered list or a 5% change in users must not
    move the stack, and the output must never depend on scenario_id."""
    base = core(outputs[name])
    doc = load(name)
    doc["project"]["name"] = "Renamed project"
    doc["scenario_id"] = "hidden_copy"
    for path in (("project", "platforms"), ("team", "languages")):
        doc[path[0]][path[1]] = list(reversed(doc[path[0]][path[1]]))
    doc["compliance"] = list(reversed(doc["compliance"]))
    assert core(run(doc)) == base
    doc["scale"]["users_12_months"] = round(doc["scale"]["users_12_months"] * 1.05)
    assert core(run(doc)) == base


def test_every_absent_optional_field_has_its_default_in_assumptions(outputs):
    out = run({"scenario_id": "few", "project": {"type": "internal_tool", "platforms": ["web"]}, "priorities": {"cost": 5}})
    given = [a for a in out["assumptions"] if " not given: " in a]
    assert "scale.traffic_pattern not given: default 'steady'" in given
    assert "infrastructure.deployment_model not given: default 'managed_cloud'" in given
    assert "requirements.availability not given: default '99.9'" in given
    assert "priorities.security not given: default 3" in given and not any(a.startswith("priorities.cost") for a in given)
    assert "project.name not given: the project is called 'Unnamed project'" in given
    assert len(given) == 23 + 5  # the 23 optional fields of table 3.1 and the five priorities not given
    assert not [a for name, o in outputs.items() for a in o["assumptions"] if " not given: " in a]


def test_each_regulation_gets_an_explicit_note(outputs):
    def notes(name, rule):
        return [a for a in outputs[name]["assumptions"] if a.startswith(f"{rule}:")]
    assert notes("P3", "gdpr") and "Standard Contractual Clauses" in notes("P3", "gdpr")[0]
    assert notes("P4", "iso27001") and notes("P5", "iso27001") and notes("P4", "rbi_localisation")
    assert any("DPDP" in a for a in outputs["P2"]["assumptions"])


def test_no_component_credits_the_description_which_is_never_parsed():
    files = sorted((ROOT / "scenarios").glob("*/*.json"))
    for f in files:
        out = run(json.loads(f.read_text(encoding="utf-8")))
        if out["stack"] is None:
            continue
        parts = [out["stack"][l] for l in ("frontend", "backend", "database", "hosting")] + out["stack"]["supporting"]
        assert not [c["choice"] for c in parts if "project.description" in c["driven_by"]], f.name


def test_every_end_of_life_product_in_one_line_is_warned_without_past_dates():
    doc = load("P5")
    doc["infrastructure"]["existing_systems"] = ["SQL Server 2014 on Windows Server 2012 R2", "CentOS Stream 9 build box",
                                                 "Node.js 20 API", "MySQL 8.0 reports"]
    eol = [w["message"] for w in run(doc)["warnings"] if w["code"] == "EOL_EXISTING_SYSTEM"]
    named = [m.split(": ", 1)[1].split(" is past")[0] for m in eol]
    assert named == ["SQL Server 2014", "Windows Server 2012", "Node.js 20", "MySQL 8.0"], eol
    assert not [m for m in eol if any(y in m for y in ("2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"))
                and "Server 2012" not in m and "Server 2014" not in m]


def edit(name: str, **sections) -> dict:
    doc = load(name)
    for sec, values in sections.items():
        if isinstance(doc.get(sec), dict):
            doc[sec].update(values)
        else:
            doc[sec] = values
    return doc


def test_review_fixes_for_odd_but_valid_scenarios():
    huge = run(edit("P2", scale={"users_12_months": 10 ** 309}))
    assert huge["status"] == "invalid_input" and huge["validation_errors"][0]["field"] == "scale.users_12_months"
    launch = run(edit("P2", scale={"users_at_launch": 2_000_000, "users_12_months": 30_000}))
    assert any("sized for the launch" in a for a in launch["assumptions"])
    uploads = run(edit("P1", requirements={"file_media_storage": True}))
    assert uploads["stack"]["backend"]["choice"] != "None"
    rbi = run(edit("P4", infrastructure={"data_residency": "us"}))
    assert any(a.startswith("Relaxed: infrastructure.data_residency 'us'") for a in rbi["assumptions"])
    assert "Frankfurt" in run(edit("P2", infrastructure={"data_residency": "eu"}))["stack"]["hosting"]["choice"]
    assert not [a for a in run(load("P1"))["assumptions"] if a.startswith("Preferred cloud")]
    assert not [a for a in run(load("P2"))["assumptions"] if "Data must stay in India" in a]
    assert "Yjs" not in json.dumps(run(edit("P3", project={"type": "gaming", "platforms": ["android", "ios"]}))["stack"])
    nulls = run(edit("P2", scale={"traffic_pattern": None}, priorities={"cost": None}))
    assert {"scale.traffic_pattern not given: default 'steady'", "priorities.cost not given: default 3"} <= set(nulls["assumptions"])
    assert run(edit("P1", scenario_id=None))["status"] == "ok"
    assert run(edit("P1", scenario_id=True))["status"] == "invalid_input"


def test_mobile_companion_is_not_listed_as_its_own_rival(outputs):
    front = outputs["P2"]["stack"]["frontend"]
    assert "React Native (Expo)" in front["choice"] and "React Native (Expo)" not in [a["choice"] for a in front["alternatives"]]


def test_existing_system_patterns_match_whole_names():
    out = run(edit("P2", requirements={"auth": "email_password"}, infrastructure={"existing_systems": [
        "Central MySQL database", "ASP.NET 4.8 Web Forms portal", ".NET Framework 4.6.2 app", "Flash sale engine",
        "Oracle Database 19c", "Active Directory"]}))
    auth = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "auth"]
    assert not any("Entra" in a for a in auth) and any("Active Directory (existing)" in a and "Keycloak" in a for a in auth)
    assert not [w for w in out["warnings"] if w["code"] == "EOL_EXISTING_SYSTEM"]
    assert not [a for a in out["assumptions"] if "Oracle" in a and "bonus" in a]


def test_a_relaxed_preference_is_named_in_assumptions():
    """HIPAA, PCI DSS, EU residency and no AWS, Google Cloud or Azure leave no host whose SLA backs P4's 99.95%: the
    output must say that exactly this limit was relaxed, for which host, and point at the field (statement section 4)."""
    out = run(edit("P4", project={"type": "healthtech", "platforms": ["web"]}, compliance=["hipaa", "gdpr", "pci_dss"],
                   infrastructure={"cloud_preference": "none", "data_residency": "eu"}))
    relaxed = [w for w in out["warnings"] if w["code"] == "RELAXED_CONSTRAINT"]
    assert len(relaxed) == 1, codes(out)
    host = out["stack"]["hosting"]["choice"].split(",")[0]
    assert relaxed[0]["fields"] == ["requirements.availability"], relaxed[0]
    assert f"so {host} is kept with these limits relaxed: " in relaxed[0]["message"] and "SLA" in relaxed[0]["message"]
    assert "99.95%" in relaxed[0]["message"] and "lock-in" not in relaxed[0]["message"]
    assert f"Relaxed or flagged (RELAXED_CONSTRAINT): {relaxed[0]['message']}" in out["assumptions"]


def test_a_long_description_is_accepted_and_moves_nothing(outputs):
    """Table 3.1 sets no maximum length for project.description (the request body limit bounds the size), and the
    description sets no field of a scenario file."""
    out = run(edit("P2", project={"description": "Customers book electricians and plumbers. " * 500}))
    assert out["status"] == outputs["P2"]["status"] and not out["validation_errors"]
    assert core(out) == core(outputs["P2"])


def test_description_keywords_add_notes_that_quote_them_and_change_no_pick(outputs):
    notes = lambda out: [a for a in out["assumptions"] if a.startswith("Read from project.description")]  # noqa: E731
    p4, p6 = notes(outputs["P4"]), notes(outputs["P6"])
    assert [n.split("'")[1] for n in p4] == ["UPI", "KYC", "double-entry", "credit scoring"], p4
    assert [n.split("'")[1] for n in p6] == ["GPS", "intermittent", "low-end"], p6
    for name in ("P2", "P4", "P6"):
        blank = run(edit(name, project={"description": ""}))
        assert not notes(blank) and core(blank) == core(outputs[name]), name
        assert blank["estimated_monthly_cost_usd"] == outputs[name]["estimated_monthly_cost_usd"], name
    unrelated = run(edit("P2", project={"description": "An online bookstore with a book club and stockists"}))
    assert not notes(unrelated), notes(unrelated)


def test_a_native_app_in_an_unlisted_language_is_a_warning(outputs):
    code = "MOBILE_LANGUAGE_NOT_LISTED"
    kotlin = run(edit("P4", team={"languages": ["java", "kotlin"]}))  # no TypeScript or Dart: native still leads
    hit = [w for w in kotlin["warnings"] if w["code"] == code]
    assert "Native iOS + Android" in kotlin["stack"]["frontend"]["choice"], kotlin["stack"]["frontend"]["choice"]
    assert len(hit) == 1 and "Swift" in hit[0]["message"] and hit[0]["severity"] == "warning", hit
    swift = run(edit("P4", team={"languages": ["java", "kotlin", "swift"]}))
    assert not [w for w in swift["warnings"] if w["code"] == code]
    # P4's team writes TypeScript, so React Native carries both phones in a language it knows and no warning is due.
    assert "React Native (Expo)" in outputs["P4"]["stack"]["frontend"]["choice"]
    for name in ("P2", "P4", "P6"):
        assert not [w for w in outputs[name]["warnings"] if w["code"] == code], name


def test_gdpr_without_residency_places_the_stack_in_an_eu_region(outputs):
    p3 = outputs["P3"]  # gdpr, data_residency none
    assert p3["stack"]["hosting"]["choice"] == "Fly.io, region fra (Frankfurt)", p3["stack"]["hosting"]["choice"]
    assert "users in Europe" in p3["stack"]["hosting"]["justification"]
    assert any(a.startswith("gdpr with no data_residency") for a in p3["assumptions"])
    plain = run(edit("P3", compliance=[]))
    assert ", region" not in plain["stack"]["hosting"]["choice"]
    assert not any(a.startswith("gdpr with no data_residency") for a in plain["assumptions"])


@pytest.mark.parametrize("cloud,host", [("aws", "AWS S3 + CloudFront"), ("gcp", "Firebase Hosting"),
                                        ("azure", "Azure Static Web Apps")])
def test_a_static_site_on_a_named_cloud_gets_that_clouds_static_host(cloud, host):
    """Statement 5.3: an explicit cloud is a hard constraint, and P1 is a free static portfolio on any of them."""
    out = edited("P1", infrastructure={"cloud_preference": cloud})
    stack = out["stack"]
    assert out["architecture_style"] == "static" and stack["hosting"]["choice"].startswith(host), stack["hosting"]["choice"]
    assert stack["backend"]["choice"] == stack["database"]["choice"] == "None" and stack["frontend"]["choice"] == "Astro"


@pytest.mark.parametrize("cloud,residency,host,region", [
    ("any", "eu", "AWS S3 + CloudFront", "eu-central-1"), ("any", "us", "Netlify", "US ("),
    ("none", "india", "DigitalOcean", "BLR1"), ("none", "eu", "DigitalOcean", "FRA1"),
    ("gcp", "eu", "Google Cloud Storage + Cloud CDN", "europe-west3"),
    ("azure", "india", "Azure Blob Storage + Front Door", "Central India")])
def test_a_static_site_under_a_residency_rule_names_where_its_files_stay(cloud, residency, host, region):
    """A static site's data is its files and their logs: the host must keep them in the region, and say where. A CDN
    that cannot pin them (Vercel, Firebase Hosting, Static Web Apps, Netlify outside the US) does not count."""
    out = edited("P1", infrastructure={"cloud_preference": cloud, "data_residency": residency})
    choice = out["stack"]["hosting"]["choice"]
    assert out["architecture_style"] == "static" and choice.startswith(host) and region in choice, choice
    assert "for functions" not in choice and not out["stack"]["frontend"]["choice"].startswith("Server-rendered")


def test_the_relaxed_hipaa_variant_keeps_a_backend_and_services_its_host_can_run():
    """Vercel runs Java, .NET, PHP and Elixir only through its beta Container runtime, and no container beside the
    API; uploads with health information get no public CDN."""
    out = run(edit("P4", project={"type": "healthtech", "platforms": ["web"]}, compliance=["hipaa", "gdpr", "pci_dss"],
                   infrastructure={"cloud_preference": "none", "data_residency": "eu"}))
    assert out["stack"]["hosting"]["choice"].startswith("Vercel")
    assert not re.search(r"Spring|ASP\.NET|Laravel|Phoenix", out["stack"]["backend"]["choice"]), out["stack"]["backend"]
    services = [s["choice"] for s in out["stack"]["supporting"]]
    assert not [s for s in services if "container beside the API" in s], services
    assert not [s for s in services if CDN.search(s) and not NO_CDN.search(s)], services


def test_an_inference_api_is_a_cpu_scoring_endpoint_only_where_a_scoring_model_fits(outputs):
    def ml(out):
        return ([s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "ml"],
                [a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith("Model serving")])
    sage, cost = ml(outputs["P4"])  # fintech: a credit-scoring model of its own
    assert sage[0].startswith("Amazon SageMaker real-time endpoint") and cost[0].startswith("Model serving: CPU endpoint: $75-180")
    hosted, cost = ml(edited("P3", requirements={"ml_features": "inference_api"}))  # a whiteboard calls a hosted model
    assert "endpoint for your own model" not in hosted[0] and cost[0].startswith("Model serving: inference")
    apart, cost = ml(edited("P4", infrastructure={"cloud_preference": "none"}))  # functions only: a service apart
    assert "service of its own" in apart[0] and "called over HTTPS" in apart[0] and cost[0].startswith(
        "Model serving: CPU endpoint: $75-180"), (apart, cost)


def test_each_service_stays_on_the_named_cloud_and_the_deployment_model():
    sms = lambda out: [s["choice"] for s in out["stack"]["supporting"] if "Verify" in s["choice"]]
    sms = lambda out: [s["choice"] for s in out["stack"]["supporting"]  # noqa: E731
                       if s["layer"] != "auth" and ("SMS" in s["choice"] or "Verify" in s["choice"])]
    assert sms(edited("P2", infrastructure={"cloud_preference": "gcp", "data_residency": "eu"})) == ["Twilio Verify"]
    assert sms(edited("P2", infrastructure={"cloud_preference": "aws", "data_residency": "eu"})) == [
        "Amazon Cognito SMS sign-in codes (sent through AWS End User Messaging SMS)"]  # Cognito is the sign-in there
    assert sms(edited("P2", infrastructure={"deployment_model": "self_hosted_cloud_vm", "data_residency": "eu"})) == [
        "Twilio Verify"]
    for cloud in ("aws", "gcp", "none"):
        assert "Azure" not in edited("P5", infrastructure={"cloud_preference": cloud})["stack"]["database"]["choice"], cloud
    queue = [s["choice"] for s in edited("P4", infrastructure={"deployment_model": "self_hosted_cloud_vm"})["stack"][
        "supporting"] if s["layer"] == "queue"]
    assert queue and not [q for q in queue if "SQS" in q], queue


def test_a_spa_served_from_a_cloud_storage_bucket_pays_for_its_load_balancer():
    """Cloud Storage serves no HTTPS on a custom domain by itself: the bucket sits behind an external Application Load
    Balancer whose forwarding rule costs $0.025 an hour, about $18 a month, before any traffic."""
    out = edited("P3", infrastructure={"cloud_preference": "gcp"})
    line = [a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith("Static frontend")]
    assert out["stack"]["frontend"]["choice"].startswith("React SPA") and line, out["stack"]["frontend"]
    assert "plus the $18.25 monthly base fee" in line[0], line


@pytest.mark.parametrize("cloud,residency", [("any", "none"), ("aws", "none"), ("gcp", "eu"), ("none", "india")])
def test_hipaa_uploads_are_never_put_behind_a_public_cdn(cloud, residency):
    doc = edit("P2", infrastructure={"cloud_preference": cloud, "data_residency": residency})
    doc["compliance"].append("hipaa")
    out = run(doc)
    storage = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] in ("storage", "cdn")
               and "is built to static files" not in s["justification"]]  # the app's own bundle may use a CDN
    assert storage and not [s for s in storage if CDN.search(s) and not re.search(r"non-PHI|no public CDN", s)], storage


@pytest.mark.parametrize("base,langs,comp", [("P3", ["elixir"], ["pci_dss"]), ("P4", ["ruby"], ["pci_dss"]),
                                             ("P4", ["csharp"], ["hipaa", "gdpr", "pci_dss"])])
def test_a_function_platform_never_hosts_a_framework_it_runs_only_in_beta(base, langs, comp):
    """With no hyperscaler, an EU residency and PCI DSS only function platforms remain; Vercel runs Ruby only on a beta
    runtime and Java, .NET, PHP and Elixir only in its beta Container runtime, so the backend must be one it runs."""
    doc = edit(base, team={"languages": langs}, compliance=comp, infrastructure={"cloud_preference": "none", "data_residency": "eu"})
    if base == "P4":
        doc["project"].update(type="healthtech", platforms=["web"])
    else:
        doc["requirements"]["availability"] = "99.9"
    out = run(doc)
    host, backend = out["stack"]["hosting"]["choice"], out["stack"]["backend"]["choice"]
    if host.startswith(("Vercel", "Netlify", "Cloudflare")) and "for the API" not in host:
        assert not re.search(r"Phoenix|Rails|ASP\.NET|Spring|Laravel", backend), (backend, host)


def test_a_read_only_site_gets_no_database_without_a_backend():
    doc = edit("P5", project={"type": "content_site"}, infrastructure={"cloud_preference": "aws"},
               requirements={"auth": "none", "payments": False, "realtime": False, "file_media_storage": False})
    stack = run(doc)["stack"]
    assert not (stack["backend"]["choice"] == "None" and stack["database"]["choice"] != "None"), core({"stack": stack})


def test_render_static_sites_do_not_claim_a_region():
    """Render serves static sites from a global CDN and offers no region for them (render.com/docs/regions)."""
    doc = edit("P1", compliance=["hipaa"], infrastructure={"cloud_preference": "none", "data_residency": "eu"})
    out = run(doc)
    assert not out["stack"] or not out["stack"]["hosting"]["choice"].startswith("Render"), out["stack"]["hosting"]


@pytest.mark.parametrize("ptype", ["content_site", "internal_tool"])
def test_self_run_vms_never_get_a_managed_model_service(ptype):
    doc = edit("P2", project={"type": ptype}, requirements={"ml_features": "inference_api"},
               infrastructure={"deployment_model": "self_hosted_cloud_vm", "cloud_preference": "aws"})
    ml = [s["choice"] for s in run(doc)["stack"]["supporting"] if s["layer"] == "ml"]
    assert ml and not [m for m in ml if re.search(r"Bedrock|SageMaker|Vertex|Azure AI", m)], ml


def test_a_read_only_site_past_5_gb_is_held_to_where_its_static_host_keeps_files():
    """A read-only site stays static at any size (media past ~5 GB go to object storage), so its host is judged by
    where it keeps the site's files, not by where its functions run: with no AWS, Google Cloud or Azure and data kept
    in India, no static host qualifies, and the engine says so instead of naming one whose CDN copies files abroad."""
    doc = edit("P5", project={"type": "content_site"}, compliance=["iso27001"],
               infrastructure={"cloud_preference": "none", "data_residency": "india", "existing_systems": []},
               requirements={"auth": "none", "payments": False, "realtime": False, "file_media_storage": False})
    out = run(doc)
    assert out["status"] == "infeasible" and any(w["code"] == "NO_FEASIBLE_OPTION" for w in out["warnings"]), out["status"]
    doc["infrastructure"]["cloud_preference"] = "any"  # a bucket in Mumbai behind CloudFront keeps them in India
    assert run(doc)["stack"]["hosting"]["choice"].startswith("AWS S3 + CloudFront")


def test_an_on_premises_sharepoint_server_is_reachable_from_an_air_gapped_site():
    doc = edit("P5", infrastructure={"deployment_model": "air_gapped", "cloud_preference": "none",
                                     "existing_systems": ["SharePoint Server 2019", "Active Directory"]})
    assert not [w for w in run(doc)["warnings"] if w["code"] == "EXISTING_SYSTEM_UNREACHABLE"]


@pytest.mark.parametrize("text,how", [
    ("NSE stock exchange feed", "its API"), ("Currency exchange rates API", "its API"), ("Exchange rate feed", "its API"),
    ("Exchange market data feed", "its API"), ("Exchange FIX gateway", "its API"), ("Stock exchange server", "its API"),
    ("On-premises Exchange", "the SharePoint or Exchange server's REST API"),
    ("Hybrid Exchange", "the SharePoint or Exchange server's REST API"),
    ("Microsoft Exchange Server 2019", "the SharePoint or Exchange server's REST API"),
    ("MS Exchange", "the SharePoint or Exchange server's REST API"),
    ("Exchange 2016 mail server", "the SharePoint or Exchange server's REST API"),
    ("Exchange", "the SharePoint or Exchange server's REST API"),
    ("Exchange Online", "Microsoft Graph API (mail, calendar and Teams notifications, files)"),
    ("Weather outlook feed", "its API"), ("Market outlook report", "its API"),
    ("Outlook weather forecast API", "its API"), ("Outlook for commodity markets", "its API"),
    ("Outlook forecasting service", "its API"),
    ("Microsoft Outlook", "the SharePoint or Exchange server's REST API"),
    ("MS Outlook", "the SharePoint or Exchange server's REST API"),
    ("Office Outlook 2019", "the SharePoint or Exchange server's REST API"),
    ("Outlook", "the SharePoint or Exchange server's REST API"),
    ("Outlook.com", "Microsoft Graph API (mail, calendar and Teams notifications, files)")])
def test_only_the_mail_server_reads_as_exchange(text, how):
    """'exchange' alone is a stock exchange or a currency rate as often as Microsoft's mail server, and 'outlook' a
    weather or market forecast as often as Microsoft's mail program."""
    doc = edit("P5", infrastructure={"existing_systems": [text]})
    notes = [a for a in run(doc)["assumptions"] if a.startswith(f"Existing system '{text}'")]
    if how == "its API":  # no interface on record: the note says so instead of inventing one
        assert len(notes) == 1 and notes[0].startswith(f"Existing system '{text}': no known integration path"), notes
        return
    assert notes == [f"Existing system '{text}': integrated through {how}; it stays the system of record for its own data"], notes


@pytest.mark.parametrize("text,warned", [("MinIO object store", True), ("On-prem minio cluster", True),
                                         ("MinIO AIStor", False), ("AIStor (MinIO)", False)])
def test_an_existing_minio_server_is_flagged_as_unmaintained(text, warned):
    """MinIO's repository was archived on 25 Apr 2026 and says it is no longer maintained (github.com/minio/minio); it
    names MinIO's AIStor editions as the alternatives, so a system that says AIStor is not flagged."""
    out = run(edit("P5", infrastructure={"existing_systems": [text]}))
    eol = [w["message"] for w in out["warnings"] if w["code"] == "EOL_EXISTING_SYSTEM"]
    if not warned:
        assert eol == [], eol
        return
    assert eol == [f"'{text}': MinIO is past its vendor's support: its open-source repository was archived on 25 Apr 2026 "
                   "and is no longer maintained (https://github.com/minio/minio). Integrate with it through an API or a "
                   "migration, never build new parts on it; plan the upgrade before go-live."], eol


@pytest.mark.parametrize("langs", [["go"], ["go", "typescript"]])
def test_a_go_server_never_runs_on_cloudflare_workers(langs):
    """Workers run JavaScript, TypeScript, Python and Rust, and Go only compiled to WebAssembly
    (developers.cloudflare.com/workers/languages/), so a net/http, chi or Gin server needs another host."""
    out = run(edit("P3", team={"languages": langs}, compliance=["gdpr", "pci_dss"], infrastructure={"cloud_preference": "none"}))
    host, backend = out["stack"]["hosting"]["choice"], out["stack"]["backend"]["choice"]
    assert not (host.startswith("Cloudflare") and "for the API" not in host and backend.startswith("Go")), (backend, host)


@pytest.mark.parametrize("infra,service,reference", [
    ({}, "Amazon SageMaker", False), ({"cloud_preference": "gcp"}, "Vertex AI", True),
    ({"cloud_preference": "azure"}, "Azure Machine Learning", True), ({"deployment_model": "self_hosted_cloud_vm"}, "CPU container", True)])
def test_the_scoring_endpoint_band_names_sagemaker_as_the_service_only_on_aws(infra, service, reference):
    """The $75-180 band is SageMaker's list price. Off AWS it is a reference price, and the endpoint in use is the
    cloud's own or the team's container."""
    out = edited("P4", infrastructure=infra)
    ml = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "ml"]
    line = [a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith("Model serving: CPU endpoint")]
    assert ml and service in ml[0] and line, (ml, line)
    assert ("SageMaker's list prices, used as a reference" in line[0]) == reference, line
    assert reference == ("SageMaker" not in ml[0]), ml


@pytest.mark.parametrize("base,sections,style", [
    ("P4", {"infrastructure": {"cloud_preference": "none"}}, "modular_monolith"),  # the API runs as Vercel functions
    ("P1", {"project": {"type": "fintech"}, "requirements": {"ml_features": "inference_api"}}, "static")])  # Netlify static
def test_a_scoring_model_beside_functions_or_a_static_site_gets_a_service_of_its_own(base, sections, style):
    """ONNX Runtime's Node.js package unpacks to 308 MB, over the 250 MB Vercel allows a function, and a static site
    runs no server code: either way the model runs as a small CPU service of its own, priced like the endpoint."""
    out = edited(base, **sections)
    ml = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "ml"]
    cost = [a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith("Model serving: CPU endpoint")]
    assert out["architecture_style"] == style and ml and "service of its own" in ml[0], ml
    assert "inside" not in ml[0] and cost and "used as a reference" in cost[0], (ml, cost)


def test_self_run_object_storage_is_ceph_not_the_archived_minio():
    """MinIO's repository was archived on 25 Apr 2026 and says it is no longer maintained (github.com/minio/minio), so no
    recommended component names it: storage a team runs itself is Ceph Object Gateway, on-premises, in a hybrid setup,
    beside DigitalOcean Spaces in India, under on-premises video and on a self-managed HIPAA team's own servers."""
    from engine import recommend
    from engine.advice import _object_storage
    docs = {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in PUBLIC + sorted((ROOT / "scenarios" / "edge").glob("E*.json"))}
    hipaa = edit("P4", infrastructure={"deployment_model": "self_hosted_cloud_vm"})
    hipaa["compliance"] = hipaa["compliance"] + ["hipaa"]
    hipaa["requirements"]["file_media_storage"] = True
    docs.update({"P4 self-managed HIPAA": hipaa, "P2 no hyperscaler": edit("P2", infrastructure={"cloud_preference": "none"})})
    named = {k: json.dumps(run(doc)["stack"]) for k, doc in docs.items()}
    media = {"app_type": "social_network", "dau": 5000, "special_workloads": ["media_uploads", "video_on_demand"]}
    for deployment in ("hybrid", "on_prem"):
        r = recommend(dict(media, deployment=deployment), with_counterfactuals=False)
        named[deployment] = json.dumps(r["supporting_services"])
    # No scenario reaches this line (a HIPAA team on its own VMs gets a hyperscaler's BAA storage), so it is read directly.
    env = {"onprem": False, "hybrid": False, "cloud": None, "hipaa": True, "self_managed": True, "no_hyperscaler": True,
           "india": False, "eu": False, "us": False}
    named["self-managed HIPAA line"] = _object_storage(env, "hetzner")[0]
    assert [k for k, text in named.items() if "minio" in text.lower()] == []
    assert {"E7_air_gapped", "hybrid", "on_prem", "self-managed HIPAA line"} <= \
        {k for k, text in named.items() if "Ceph Object Gateway" in text}
    assert "DigitalOcean Spaces in BLR1" in named["P2 no hyperscaler"]  # one product per pick, in India


def test_hipaa_files_with_no_hyperscaler_stay_where_the_hosts_baa_reaches():
    """A team on a managed platform runs no servers, so 'storage on your BAA-covered servers' does not apply. Each host's
    HIPAA page says what holds PHI: Render lists persistent disks, Fly.io offers a BAA for Tigris, and Vercel's BAA
    lists its CDN and functions, not a file store."""
    docs = {"Render": "https://render.com/docs/hipaa-compliance", "Fly.io": "https://fly.io/compliance/",
            "Vercel": "https://vercel.com/kb/guide/hipaa-compliance-guide-vercel"}
    seen = set()
    for name in ("P1", "P2", "P3", "P4", "P5", "P6"):
        for residency in ("none", "eu", "india"):
            doc = edit(name, infrastructure={"cloud_preference": "none", "data_residency": residency})
            doc["compliance"].append("hipaa")
            doc["requirements"]["file_media_storage"] = True
            out = run(doc)
            if not out["stack"]:
                continue
            host = out["stack"]["hosting"]["choice"].split(",")[0]
            store = [s for s in out["stack"]["supporting"] if s["layer"] == "storage"]
            assert store and not [s for s in store if "your BAA-covered servers" in s["choice"]], (name, residency, host, store)
            # Wasabi signs BAAs and has US and EU regions; elsewhere the host's own HIPAA page is the source.
            want = "https://www.wasabi.com/hipaa-white-paper" if store[0]["choice"].startswith("Wasabi") else docs[host]
            assert store[0]["source"] == want, (name, residency, host, store[0])
            seen.add(host)
    assert set(docs) <= seen, seen


def test_a_hosting_rule_that_costs_the_team_its_language_says_so():
    """No hyperscaler, EU residency, PCI DSS and HIPAA leave function platforms, and Vercel runs .NET only in its beta
    Container runtime, so a C# team gets Go. Nothing else in the output says the team never listed Go (it counts as
    related to C#), so BACKEND_LANGUAGE_NOT_LISTED does, with the rule that decided it."""
    doc = edit("P4", team={"languages": ["csharp"]}, project={"type": "healthtech", "platforms": ["web"]},
               compliance=["hipaa", "gdpr", "pci_dss"], infrastructure={"cloud_preference": "none", "data_residency": "eu"})
    out = run(doc)
    hit = [w for w in out["warnings"] if w["code"] == "BACKEND_LANGUAGE_NOT_LISTED"]
    assert out["stack"]["backend"]["choice"].startswith("Go") and hit, [w["code"] for w in out["warnings"]]
    assert "C# + ASP.NET Core" in hit[0]["message"] and "Container runtime" in hit[0]["message"], hit[0]
    assert hit[0]["severity"] == "warning" and hit[0]["fields"] == ["team.languages"]
    # No long-running host passes PCI DSS here, so the warning does not offer one.
    assert "no host that runs C# + ASP.NET Core passed the other constraints" in hit[0]["message"], hit[0]
    from engine.recommender import _team_languages  # a framework the team lists stands for its language
    assert _team_languages({"django"}) == {"python"} and _team_languages({"spring"}) == {"java", "kotlin"}
    kept = edit("P4", project={"type": "healthtech", "platforms": ["web"]}, compliance=["hipaa", "gdpr", "pci_dss"],
                infrastructure={"cloud_preference": "none", "data_residency": "eu"})  # TypeScript is listed: Express
    for d in [kept] + [load(n) for n in ("P1", "P2", "P3", "P4", "P5", "P6")]:
        assert not [w for w in run(d)["warnings"] if w["code"] == "BACKEND_LANGUAGE_NOT_LISTED"], d["scenario_id"]


@pytest.mark.parametrize("base,languages,backend", [("P3", ["Rust", "C"], "Go"), ("P3", ["C++"], "Go"),
                                                    ("P4", ["Scala"], "Spring Boot")])
def test_adjacent_languages_pick_the_nearest_backend_and_warn(base, languages, backend):
    out = edited(base, team={"languages": languages})
    assert backend in out["stack"]["backend"]["choice"], out["stack"]["backend"]["choice"]
    warn = [w for w in out["warnings"] if w["code"] == "BACKEND_LANGUAGE_NOT_LISTED"]
    assert len(warn) == 1 and warn[0]["fields"] == ["team.languages"], warn
    assert "carr" in warn[0]["message"] and "plan time for the team to learn" in warn[0]["message"], warn


def test_languages_outside_the_knowledge_base_are_kept_and_the_one_to_learn_is_named():
    out = edited("P3", team={"languages": ["Objective-C", "COBOL"]})
    warn = [w["message"] for w in out["warnings"] if w["code"] == "BACKEND_LANGUAGE_NOT_LISTED"]
    assert warn and "Objective-C, COBOL" in warn[0] and "plan time for the team to learn" in warn[0], warn
    assert any("objective-c, cobol" in a and "unfamiliar-language penalty" in a for a in out["assumptions"])
    assert not [w for w in edited("P3")["warnings"] if w["code"] == "BACKEND_LANGUAGE_NOT_LISTED"]


def test_r_carries_over_to_the_python_backends():
    from engine.kb import load_kb
    from engine.scoring import skill_fit
    backends = load_kb()["backend"]
    python = [b for b in backends if b.get("language") == "python"]
    others = [b for b in backends if b.get("kind") == "server" and b.get("language") != "python"]
    assert python and all(skill_fit(b, {"r"}) > max(skill_fit(o, {"r"}) for o in others) for b in python)


@pytest.mark.parametrize("languages", [["python"], ["javascript"]])
def test_many_platforms_on_a_short_timeline_get_one_toolkit_for_every_target(languages):
    out = edited("P2", project={"platforms": ["web", "android", "ios"]}, timeline={"mvp_weeks": 3},
                 team={"size": 1, "experience": "beginner", "languages": languages})
    front = out["stack"]["frontend"]
    assert codes(out)["MANY_PLATFORMS_SHORT_TIMELINE"] == "critical"
    assert front["choice"] in ("Flutter", "React Native (Expo)"), front["choice"]
    assert "One codebase builds the web, Android and iOS apps" in front["justification"], front["justification"]


def test_budget_infeasible_describes_the_stack_shown():
    out = edited("P3", budget={"monthly_infra_usd": 0})
    message = next(w["message"] for w in out["warnings"] if w["code"] == "BUDGET_INFEASIBLE")
    assert "the stack shown is the cheapest" not in message, message
    assert f"The stack shown starts at ${out['estimated_monthly_cost_usd']['min']:,}" in message, message


@pytest.mark.parametrize("deploy,cloud,said,unsaid", [
    ("air_gapped", "none", "The servers are your own", "AWS"), ("on_premise", "any", "The servers are your own", "Azure"),
    ("managed_cloud", "none", "independent hosts only", "AWS"), ("managed_cloud", "azure", "Pick an Azure region", "Google"),
    ("managed_cloud", "any", "AWS, Google Cloud and Azure cover the most countries", "your own")])
def test_unverified_residency_advice_follows_the_deployment(deploy, cloud, said, unsaid):
    out = edited("P2", infrastructure={"data_residency": "other", "deployment_model": deploy, "cloud_preference": cloud})
    message = next(w["message"] for w in out["warnings"] if w["code"] == "RESIDENCY_UNVERIFIED")
    assert said in message and unsaid not in message, message


@pytest.mark.parametrize("system,product", [
    ("Python 3.9 data scripts", "Python 3.9"), ("Python 3.10 batch jobs", "Python 3.10"), ("Vue 2 admin panel", "Vue 2"),
    ("Windows 7 office PCs", "Windows 7"), ("Oracle 11g ERP", "Oracle Database 11g"),
    ("Oracle Database 12c", "Oracle Database 12c"), (None, None)])
def test_more_end_of_life_systems_are_warned(system, product):
    systems = [system] if system else ["Python 3.12 scripts", "Vue 3 portal", "Windows 11 laptops", "Oracle 19c ledger"]
    out = edited("P5", infrastructure={"existing_systems": systems})
    eol = [w["message"] for w in out["warnings"] if w["code"] == "EOL_EXISTING_SYSTEM"]
    assert (len(eol) == 1 and f"{product} is past its vendor's support" in eol[0]) if system else not eol, eol


def test_an_existing_message_broker_carries_the_queue():
    base = [s["choice"] for s in edited("P2")["stack"]["supporting"] if s["layer"] == "queue"]
    out = edited("P2", infrastructure={"existing_systems": ["Apache Kafka 3.6 cluster"]})
    queues = [s for s in out["stack"]["supporting"] if s["layer"] == "queue"]
    assert base and [s["choice"] for s in queues] == ["Apache Kafka (existing)"], (base, queues)
    assert base[0].split(" (")[0] in queues[0]["justification"] and queues[0]["source"].startswith("https://kafka.apache.org")


def test_an_existing_warehouse_carries_the_analytics_and_its_cost():
    sections = dict(project={"type": "data_analytics"}, scale={"data_volume_gb_12_months": 20000},
                    budget={"monthly_infra_usd": 40000})
    base = edited("P5", **sections)
    out = edited("P5", infrastructure={"existing_systems": ["Snowflake (EU) data warehouse"]}, **sections)
    analytics = lambda o: [s["choice"] for s in o["stack"]["supporting"] if "ClickHouse" in s["choice"]  # noqa: E731
                           or "(existing)" in s["choice"]]
    assert [c for c in analytics(base) if "ClickHouse" in c], analytics(base)
    assert analytics(out) == ["Snowflake (existing)"], analytics(out)
    assert out["estimated_monthly_cost_usd"]["min"] < base["estimated_monthly_cost_usd"]["min"]
    assert not [a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith("Analytics:")]


def test_an_unscored_database_is_integrated_not_migrated():
    out = edited("P4", infrastructure={"existing_systems": ["Oracle Database 19c (core ledger)", "IBM Db2 on z/OS"]})
    texts = [w["message"] for w in out["warnings"]] + out["assumptions"]
    assert not [t for t in texts if "plan a migration" in t], texts
    said = [t for t in texts if "stays the system of record and is integrated, not migrated" in t]
    assert any("Oracle" in t for t in said) and any("Db2" in t for t in said), said


def test_systems_with_no_known_interface_say_so():
    out = edited("P5", infrastructure={"existing_systems": ["WhatsApp groups", "Windows 7 office PCs"]})
    assert any(a.startswith("Existing system 'WhatsApp groups': no known integration path") for a in out["assumptions"])
    # A product past its vendor's support is moved off, not integrated as a system of record.
    assert any(a.startswith("Existing system 'Windows 7 office PCs': past its vendor's support") for a in out["assumptions"])
    assert not [a for a in out["assumptions"] if "integrated through its API" in a]


def test_an_api_only_project_on_a_backend_service_has_no_host_of_its_own():
    out = run({"scenario_id": "bare", "project": {"type": "api_platform", "platforms": ["api_only"]},
               "scale": {"users_at_launch": 0, "users_12_months": 0}, "team": {"size": 1, "experience": "mixed", "languages": []},
               "budget": {"monthly_infra_usd": 0}, "timeline": {"mvp_weeks": 1}})
    stack = out["stack"]
    assert stack["frontend"]["choice"] == "None" and "BaaS" in stack["backend"]["choice"], stack["backend"]["choice"]
    hosting = stack["hosting"]
    assert hosting["choice"].startswith("Provided by"), hosting["choice"]
    assert "app stores" not in hosting["justification"] and "customers' own code" in hosting["justification"], hosting


def test_hosting_provided_by_a_backend_service_has_no_borrowed_region():
    """A Flutter app on a BaaS for an Indian ledger: hosting is the BaaS's, so the scored web host's region is not shown."""
    doc = load("P6")
    doc["project"]["type"], doc["team"]["languages"], doc["compliance"] = "fintech", ["dart"], ["dpdp", "rbi_localisation"]
    doc["requirements"].update(payments=True, availability="99.9")
    doc["scale"].update(users_12_months=100000, peak_concurrent_users=2000, data_volume_gb_12_months=50)
    doc["budget"]["monthly_infra_usd"] = 50
    hosting = run(doc)["stack"]["hosting"]["choice"]
    assert hosting.startswith("Provided by") and "region" not in hosting, hosting


@pytest.mark.parametrize("languages,toolkit", [(["C++"], "Qt (C++)"), (["Rust"], "Tauri (Rust)"),
                                               (["csharp"], ".NET MAUI (C#)"), (["typescript"], "Electron (JavaScript)")])
def test_a_desktop_only_project_gets_a_desktop_toolkit_in_the_team_language(languages, toolkit):
    out = edited("P3", project={"platforms": ["desktop"]}, team={"languages": languages})
    front = out["stack"]["frontend"]
    assert front["choice"] == toolkit, front["choice"]
    assert "no web pages to build or host" in front["justification"], front["justification"]
    assert not [s for s in out["stack"]["supporting"] if "Desktop" in s["choice"] or "web frontend" in s["choice"]]


@pytest.mark.parametrize("languages,toolkit", [(["C++"], "Qt"), (["Rust"], "Tauri"), (["csharp"], ".NET MAUI"),
                                               (["typescript"], "Electron")])
def test_a_desktop_app_beside_the_web_frontend_uses_the_team_language(languages, toolkit):
    out = edited("P3", project={"platforms": ["web", "desktop"]}, team={"languages": languages})
    desktop = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "other" and "desktop" in s["choice"].lower()
               or s["choice"].startswith(("Qt", "Tauri", ".NET MAUI", "Electron"))]
    assert len(desktop) == 1 and desktop[0].startswith(toolkit), desktop


def game(languages: list[str], realtime: bool, platforms=("android", "ios"), **extra) -> dict:
    doc = load("P6")
    doc["project"].update(type="gaming", platforms=list(platforms))
    doc["team"].update(languages=languages, size=extra.get("size", 6), experience="intermediate")
    doc["requirements"].update(realtime=realtime, payments=True, offline_support=False)
    doc["scale"].update(users_12_months=extra.get("users", 200000), peak_concurrent_users=extra.get("peak", 20000))
    doc["budget"]["monthly_infra_usd"] = extra.get("budget", 20000)
    doc["infrastructure"].update(cloud_preference=extra.get("cloud", "any"))
    return run(doc)


@pytest.mark.parametrize("languages,engine", [(["C++"], "Unreal Engine (C++)"), (["csharp"], "Unity (C#)")])
def test_a_game_client_is_built_in_the_engine_of_the_team_language(languages, engine):
    out = game(languages, realtime=True)
    assert out["stack"]["frontend"]["choice"] == engine, out["stack"]["frontend"]["choice"]


@pytest.mark.parametrize("cloud,servers", [("aws", "Amazon GameLift Servers"), ("any", "Agones")])
def test_a_live_game_gets_dedicated_game_servers(cloud, servers):
    out = game(["C++"], realtime=True, cloud=cloud)
    live = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "realtime"]
    assert any(c.startswith(servers) for c in live), live


def test_a_turn_based_game_keeps_realtime_off():
    out = game(["csharp"], realtime=False, size=1, users=5000, peak=300, budget=50)
    codes_seen = {w["code"] for w in out["warnings"]}
    assert "IMPLIED_REALTIME" not in codes_seen, codes_seen
    parts = [s["layer"] + ": " + s["choice"] for s in out["stack"]["supporting"]]
    assert not [p for p in parts if p.startswith("realtime")], parts
    assert any("realtime stays off" in a for a in out["assumptions"])


@pytest.mark.parametrize("platforms,stores", [(["android", "ios"], ["Google Play Billing", "App Store In-App Purchase"]),
                                              (["ios"], ["App Store In-App Purchase"])])
def test_a_phone_app_sells_digital_goods_through_the_store(platforms, stores):
    out = game(["csharp"], realtime=False, platforms=platforms)
    pay = [s for s in out["stack"]["supporting"] if s["layer"] == "payments"]
    assert len(pay) == 1 and all(x in pay[0]["choice"] for x in stores) and "Stripe" not in pay[0]["choice"], pay
    assert "3.1.1" in pay[0]["justification"] if "ios" in platforms else True
    shop = edited("P2", project={"platforms": ["android", "ios"]})
    assert not [s for s in shop["stack"]["supporting"] if s["layer"] == "payments" and "In-App" in s["choice"]]


def test_budget_lines_agree_for_a_stack_on_a_backend_service():
    doc = load("P6")
    doc["project"]["platforms"], doc["team"]["languages"] = ["ios"], ["swift"]
    doc["scale"].update(users_12_months=400000, peak_concurrent_users=6000)
    doc["budget"]["monthly_infra_usd"] = 50
    out = run(doc)
    assert "BUDGET_INFEASIBLE" in codes(out) and "BaaS" in out["stack"]["backend"]["choice"], out["stack"]["backend"]
    for w in out["warnings"]:
        if w["code"] == "BUDGET_INFEASIBLE":
            floor = re.search(r"hosting \+ database alone costs about \$([\d,]+)", w["message"])
            shown = int(re.search(r"[Tt]he stack shown starts at \$([\d,]+)", w["message"]).group(1).replace(",", ""))
            assert not floor or shown >= int(floor.group(1).replace(",", "")), w["message"]
            assert "$0/month of it" not in w["message"], w["message"]


def test_a_web_game_without_an_engine_client_gets_no_game_servers():
    out = game(["typescript"], realtime=True, platforms=["web"])
    assert out["stack"]["frontend"]["choice"] not in ("Unity (C#)", "Unreal Engine (C++)")
    assert not [s for s in out["stack"]["supporting"] if s["choice"].startswith(("Agones", "Amazon GameLift"))]


def test_the_web_frontend_shares_code_with_the_mobile_app_when_they_tie():
    """A beginner JavaScript team's web + Android marketplace: Nuxt (Vue) and Next.js (React) tie on the web, and the
    Android app is React Native, so the tie goes to the framework that shares React with it."""
    out = run({"project": {"type": "marketplace", "platforms": ["web", "android"]},
               "scale": {"traffic_pattern": "seasonal", "workload": "balanced", "users_at_launch": 500,
                         "users_12_months": 20000, "peak_concurrent_users": 400, "data_volume_gb_12_months": 30},
               "team": {"has_devops": False, "size": 4, "experience": "beginner", "languages": ["javascript", "html", "css"]},
               "budget": {"monthly_infra_usd": 0}, "timeline": {"mvp_weeks": 8},
               "infrastructure": {"cloud_preference": "any", "deployment_model": "managed_cloud", "data_residency": "india"},
               "requirements": {"realtime": True, "full_text_search": True, "file_media_storage": True, "payments": True,
                                "auth": "social", "seo_critical": True, "availability": "99"},
               "compliance": ["dpdp"], "priorities": {"cost": 5, "time_to_market": 4, "scalability": 2, "performance": 2}})
    choice = out["stack"]["frontend"]["choice"]
    assert choice == "Next.js (React) + React Native (Expo) for the Android app", choice
    assert "sharing code with the mobile app" in out["stack"]["frontend"]["justification"] or "higher stack score" in         out["stack"]["frontend"]["justification"], out["stack"]["frontend"]["justification"]


def test_of_two_existing_brokers_one_carries_the_queue_and_the_other_is_kept():
    out = edited("P2", infrastructure={"existing_systems": ["IBM MQ", "Apache Kafka 2.8"]})
    queues = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "queue"]
    assert queues == ["Apache Kafka (existing)"], queues
    notes = [a for a in out["assumptions"] if a.startswith("Existing message system")]
    assert len(notes) == 2 and any("IBM MQ is kept as it is" in a and "go through Apache Kafka" in a for a in notes), notes


# A two-person beginner team's festival-sale shop: its operations budget defers the analytics store.
SMALL_TEAM_SHOP = {
    "scenario_id": "small_team_shop",
    "project": {"name": "Saree store", "type": "ecommerce", "description": "Handloom saree store with festival sales",
                "platforms": ["web"]},
    "scale": {"traffic_pattern": "seasonal", "workload": "read_heavy", "users_at_launch": 20000,
              "users_12_months": 500000, "peak_concurrent_users": 8000, "data_volume_gb_12_months": 10},
    "team": {"has_devops": False, "size": 2, "experience": "beginner", "languages": ["javascript", "typescript"]},
    "budget": {"monthly_infra_usd": 150}, "timeline": {"mvp_weeks": 6},
    "infrastructure": {"cloud_preference": "any", "deployment_model": "managed_cloud", "data_residency": "india",
                       "existing_systems": []},
    "requirements": {"realtime": False, "offline_support": False, "full_text_search": True, "file_media_storage": True,
                     "payments": True, "auth": "phone_otp", "multi_tenant": False, "ml_features": "none",
                     "seo_critical": True, "availability": "99.9", "p95_latency_ms": None},
    "compliance": ["dpdp", "pci_dss"],
    "priorities": {"cost": 5, "time_to_market": 5, "scalability": 3, "performance": 3, "maintainability": 2,
                   "security": 3},
}


def test_deferred_services_are_assumptions_not_part_of_the_stack():
    out = run(SMALL_TEAM_SHOP)
    deferred = [a for a in out["assumptions"] if a.startswith("Deferred: ")]
    assert deferred and all(" add it when " in a for a in deferred), deferred
    names = [a.split(" (", 1)[1].split(") is left out")[0] for a in deferred]
    choices = [s["choice"] for s in out["stack"]["supporting"]]
    assert not set(names) & set(choices) and "Deferred" not in json.dumps(out["stack"]["supporting"]), (names, choices)
