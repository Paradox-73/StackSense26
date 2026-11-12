"""Text and service names that must follow the scenario: trade-offs only where they apply, and supporting services
that keep the hard constraints (residency, deployment model) instead of naming a product that breaks them."""
import copy
import json
from pathlib import Path

from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent


def _doc(name: str) -> dict:
    return json.loads((ROOT / "scenarios" / "public" / f"{name}.json").read_text(encoding="utf-8"))


def _with(name: str, **sections) -> dict:
    doc = copy.deepcopy(_doc(name))
    for sec, fields in sections.items():
        if isinstance(fields, dict):
            doc.setdefault(sec, {}).update(fields)
        else:
            doc[sec] = fields
    return doc


def _supporting(out: dict) -> list[str]:
    return [s["choice"] for s in out["stack"]["supporting"]]


def test_learning_time_is_said_only_for_frontend_and_backend():
    for name in ("P2", "P3", "P4", "P6"):
        out = run(_doc(name))
        for layer in ("database", "hosting"):
            assert not [t for t in out["stack"][layer]["tradeoffs"] if t.startswith("Nobody on the team listed")], \
                (name, layer, out["stack"][layer]["tradeoffs"])
    api = run(_with("P3", project={"platforms": ["api_only"]}, requirements={"realtime": False}))
    assert not [t for t in api["stack"]["frontend"]["tradeoffs"] if "No frontend" in t], api["stack"]["frontend"]


AIR_GAPPED_PLANT = {  # an air-gapped plant dashboard that lands on on-premises Kubernetes
    "scenario_id": "T1",
    "project": {"name": "Plant", "type": "internal_tool", "platforms": ["web", "desktop"]},
    "scale": {"users_at_launch": 300, "users_12_months": 600, "peak_concurrent_users": 300, "data_volume_gb_12_months": 200},
    "team": {"has_devops": True, "size": 4, "experience": "senior", "languages": ["java", "typescript", "sql"]},
    "budget": {"monthly_infra_usd": 1000}, "timeline": {"mvp_weeks": 16},
    "infrastructure": {"cloud_preference": "none", "deployment_model": "air_gapped", "data_residency": "none",
                       "existing_systems": ["Active Directory"]},
    "requirements": {"realtime": True, "offline_support": True, "full_text_search": True, "file_media_storage": True,
                     "payments": False, "auth": "enterprise_sso", "multi_tenant": False, "ml_features": "none",
                     "seo_critical": False, "availability": "99.95", "p95_latency_ms": 200},
    "compliance": [],
}


def test_platform_skills_line_is_dropped_when_the_team_runs_infrastructure():
    out = run(AIR_GAPPED_PLANT)
    assert "Kubernetes" in out["stack"]["hosting"]["choice"], out["stack"]["hosting"]["choice"]
    text = json.dumps(out["stack"]["hosting"]["tradeoffs"])
    assert "platform/DevOps skills your team did not list" not in text, text


def test_no_behind_login_or_slow_phones_for_a_login_free_internal_tool():
    doc = _with("P3", project={"type": "internal_tool", "platforms": ["web"]},
                requirements={"auth": "none", "realtime": False, "payments": False, "seo_critical": False})
    out = run(doc)
    fe = out["stack"]["frontend"]
    assert "behind login" not in fe["justification"], fe["justification"]
    assert not [t for t in fe["tradeoffs"] if "slow phones" in t], fe["tradeoffs"]


def test_retired_products_are_flagged_and_never_kept_as_a_system_of_record():
    systems = ["Spring Boot 2.7 monolith", "Google Cloud IoT Core", "jQuery 1.8", "AWS IoT Core"]
    out = run(_with("P5", infrastructure={"existing_systems": systems}))
    eol = [w["message"] for w in out["warnings"] if w["code"] == "EOL_EXISTING_SYSTEM"]
    for product in ("Spring Boot 2.x", "Google Cloud IoT Core", "jQuery 1.x"):
        assert any(product in m for m in eol), (product, eol)
    assert not any("AWS IoT Core" in m for m in eol), eol  # still a running AWS service
    for text in systems[:3]:
        notes = [a for a in out["assumptions"] if f"'{text}'" in a]
        assert notes and not any("stays the system of record" in a for a in notes), notes


def test_an_existing_ci_system_runs_the_new_pipelines():
    for system, name in (("Jenkins", "Jenkins"), ("GitLab self-managed", "GitLab CI/CD"),
                         ("Azure DevOps boards and pipelines", "Azure Pipelines")):
        out = run(_with("P5", infrastructure={"existing_systems": [system]}))
        ci = [s for s in out["stack"]["supporting"] if s["layer"] == "ci_cd"]
        assert len(ci) == 1 and ci[0]["choice"].startswith(name) and "(existing)" in ci[0]["choice"], ci
        assert not any(f"'{system}': no known integration path" in a for a in out["assumptions"]), out["assumptions"]
    plain = run(_doc("P5"))
    assert [s["choice"] for s in plain["stack"]["supporting"] if s["layer"] == "ci_cd"] == ["GitHub Actions"]


def _engine_stack(**ids) -> dict:
    from engine.kb import LAYERS, load_kb
    kb = load_kb()
    return {layer: kb["index"][ids[layer]] for layer in LAYERS}


def _services(raw: dict, **ids) -> dict:
    from engine.advice import supporting_services
    from engine.profile import derive, normalize
    p, a, w = normalize(raw)
    return {s["role"]: s for s in supporting_services(p, derive(p, a, w), _engine_stack(**ids), [])}


def test_offline_sync_follows_the_deployment_model_and_the_residency_region():
    sync = lambda out: next(s for s in out["stack"]["supporting"] if "PowerSync" in s["choice"])  # noqa: E731
    p6 = sync(run(_doc("P6")))  # India residency
    assert "India region (ap-south-1)" in p6["choice"] and "cloud-instances" in p6["source"], p6
    for deploy in ("on_premise", "air_gapped"):
        doc = _with("P6", infrastructure={"deployment_model": deploy, "cloud_preference": "none"})
        s = sync(run(doc))
        assert "Open Edition, self-hosted" in s["choice"] and "self-hosting" in s["source"], (deploy, s)


def test_the_hosted_sync_subscription_is_in_the_cost_band_and_the_self_hosted_one_is_not():
    def sync_line(doc):
        lines = run(doc)["estimated_monthly_cost_usd"]["assumptions"]
        return next((a for a in lines if a.startswith("Offline sync")), None)
    assert sync_line(_doc("P6")).startswith("Offline sync: $0-49 (PowerSync Cloud Free plan"), sync_line(_doc("P6"))
    assert "Pro plan from $49/month" in sync_line(_doc("P6"))
    onprem = _with("P6", infrastructure={"deployment_model": "on_premise", "cloud_preference": "none"})
    assert sync_line(onprem) is None


def test_vercel_postgres_offering_under_india_residency_is_supabase_in_mumbai():
    from engine.advice import database_offering
    from engine.kb import load_kb
    from engine.profile import derive, normalize
    kb = load_kb()
    for rules, want in (([], "Supabase Postgres via Vercel Marketplace"),
                        (["data_residency_india"], "Supabase Postgres in ap-south-1 (Mumbai) via Vercel Marketplace"),
                        (["iso27001"], "Neon Postgres via Vercel Marketplace")):
        p, a, w = normalize({"app_type": "saas", "dau": 2000, "compliance": rules})
        derive(p, a, w)
        offer = database_offering(kb["index"]["postgres"], kb["index"]["vercel"], p)
        assert offer == want, (rules, offer)
        assert " or " not in offer and " / " not in offer, offer


def test_functions_only_queue_stays_inside_the_residency_rule():
    raw = {"app_type": "saas", "dau": 2000, "team_size": 3, "team_skills": ["javascript", "node"], "budget_monthly": 100}
    ids = dict(frontend="react_spa", backend="express", database="postgres", hosting="vercel")
    assert _services(raw, **ids)["Background jobs"]["name"].startswith("Upstash QStash (")
    eu = _services(dict(raw, compliance=["data_residency_eu"]), **ids)["Background jobs"]
    assert eu["name"].startswith("Upstash QStash in its EU region"), eu
    india = _services(dict(raw, compliance=["data_residency_india"]), **ids)["Background jobs"]
    assert "QStash" not in india["name"] and "jobs table in PostgreSQL" in india["name"], india


RAG_EU = {  # a contract-review assistant under EU residency on a host outside AWS, Google Cloud and Azure
    "scenario_id": "T2",
    "project": {"name": "Contracts", "type": "ai_ml_product", "platforms": ["web"]},
    "scale": {"users_at_launch": 500, "users_12_months": 4000, "data_volume_gb_12_months": 60},
    "team": {"has_devops": False, "size": 3, "experience": "intermediate", "languages": ["typescript", "python"]},
    "budget": {"monthly_infra_usd": 800}, "timeline": {"mvp_weeks": 10},
    "infrastructure": {"cloud_preference": "any", "deployment_model": "managed_cloud", "data_residency": "eu",
                       "existing_systems": []},
    "requirements": {"realtime": False, "offline_support": False, "full_text_search": True, "file_media_storage": True,
                     "payments": False, "auth": "enterprise_sso", "multi_tenant": True, "ml_features": "llm_rag",
                     "seo_critical": False, "availability": "99.9", "p95_latency_ms": None},
    "compliance": ["gdpr", "soc2"],
}


def _ml(out: dict) -> tuple[str, list[str]]:
    ml = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "ml" and "pgvector" not in s["choice"]]
    lines = [a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith("Model serving")]
    return ml[0], lines


def test_hosted_model_under_residency_is_an_in_region_api_unless_no_cloud_may_hold_it():
    out = run(RAG_EU)
    assert out["stack"]["hosting"]["choice"].split(",")[0] not in ("AWS", "Google Cloud", "Azure")
    name, lines = _ml(out)
    assert name.startswith("Azure OpenAI") and "Sweden Central" in name, name
    assert any(x.startswith("Model serving: inference") for x in lines), lines
    india = copy.deepcopy(RAG_EU)
    india["infrastructure"]["data_residency"] = "india"
    assert "South India" in _ml(run(india))[0]
    none = copy.deepcopy(RAG_EU)
    none["infrastructure"]["cloud_preference"] = "none"
    name, lines = _ml(run(none))
    assert "vLLM" in name and "EU region" in name, name
    assert not any(x.startswith("Model serving: inference") for x in lines), lines  # no tokens to pay for
    assert any("GPU server" in x for x in lines), lines


def test_hipaa_storage_and_monitoring_off_the_big_clouds_name_one_product():
    doc = _with("P3", project={"type": "healthtech", "platforms": ["web"]},
                infrastructure={"cloud_preference": "none", "data_residency": "eu"},
                requirements={"payments": False, "realtime": False}, compliance=["gdpr", "hipaa"])
    out = run(doc)
    by_layer = {s["layer"]: s["choice"] for s in out["stack"]["supporting"]}
    assert by_layer["storage"].startswith("Wasabi object storage in EU Central 2"), by_layer
    assert "Datadog on its EU site" in by_layer["observability"], by_layer
    for layer in ("storage", "observability"):
        assert " or " not in by_layer[layer] and "a vendor that" not in by_layer[layer], by_layer[layer]


def test_second_runtimes_language_gaps_and_outside_services_are_stated():
    p3 = run(_doc("P3"))  # Go backend, live whiteboard
    sync = next(s for s in p3["stack"]["supporting"] if "Yjs" in s["choice"])
    assert "Node.js service beside the Go API" in sync["choice"] and " or " not in sync["choice"], sync["choice"]
    p4 = run(_doc("P4"))  # native apps, team lists Java, Kotlin and TypeScript; AWS required; RBI localisation
    assert "does not list Swift" in p4["stack"]["frontend"]["justification"], p4["stack"]["frontend"]["justification"]
    push = next(s for s in p4["stack"]["supporting"] if "Firebase Cloud Messaging" in s["choice"])
    assert "run outside AWS" in push["justification"] and "leaves your residency region" in push["justification"]
    sms = next(s for s in p4["stack"]["supporting"] if s["choice"].startswith("MSG91"))
    assert "runs outside AWS" in sms["justification"], sms["justification"]
    p6 = run(_doc("P6"))
    push = next(s for s in p6["stack"]["supporting"] if s["choice"].startswith("Expo push"))
    assert "leaves your residency region" in push["justification"], push["justification"]


def test_summary_and_database_pick_agree_on_where_kept_data_goes():
    out = run(_doc("P5"))  # existing on-premises SQL Server 2019, picked as Azure SQL Database
    assert out["stack"]["database"]["choice"].startswith("Microsoft SQL Server: Azure SQL Database")
    assert "Microsoft SQL Server data (moved to Azure SQL Database)" in out["summary"], out["summary"]


def test_on_premises_postgres_setup_follows_the_host_kind():
    k8s = run(AIR_GAPPED_PLANT)
    assert "CloudNativePG" in k8s["stack"]["database"]["choice"] and "Patroni" not in k8s["stack"]["database"]["choice"]
    vms = run(_with("P2", infrastructure={"deployment_model": "on_premise", "cloud_preference": "none"}))
    assert vms["stack"]["hosting"]["choice"].startswith("On-prem VMs + Docker Compose"), vms["stack"]["hosting"]["choice"]
    assert "Patroni" in vms["stack"]["database"]["choice"] and "CloudNativePG" not in vms["stack"]["database"]["choice"]


def _info(out: dict) -> dict:
    return {w["code"]: w for w in out["warnings"] if w["severity"] == "info"}


def test_compliance_duties_and_delivery_risks_are_info_warnings_once():
    p4 = run(_doc("P4"))  # PCI DSS with hosted checkout, RBI localisation
    assert {"PCI_SCOPE", "RBI_COPIES_IN_INDIA"} <= set(_info(p4)), p4["warnings"]
    # Info warnings leave the status alone: only a warning or critical one makes it ok_with_warnings.
    assert (p4["status"] == "ok") == all(w["severity"] == "info" for w in p4["warnings"]), p4["warnings"]
    assert "SAQ A" in _info(p4)["PCI_SCOPE"]["message"] and "backups" in _info(p4)["RBI_COPIES_IN_INDIA"]["message"]
    hipaa = run(_with("P3", project={"type": "healthtech", "platforms": ["web"]}, compliance=["hipaa"]))
    assert "HIPAA_BAA_NEEDED" in _info(hipaa)
    oncall = run(_with("P3", requirements={"availability": "99.95"}, team={"has_devops": False}))
    assert "ON_CALL_GAP" in _info(oncall) and "on call" in _info(oncall)["ON_CALL_GAP"]["message"]
    tight = run(_with("P2", project={"platforms": ["web", "android", "ios"]}, timeline={"mvp_weeks": 6}))
    assert "PLATFORMS_TIMELINE" in _info(tight)
    critical = run(_with("P2", project={"platforms": ["web", "android", "ios"]}, timeline={"mvp_weeks": 3}))
    codes = [w["code"] for w in critical["warnings"]]
    assert "MANY_PLATFORMS_SHORT_TIMELINE" in codes and "PLATFORMS_TIMELINE" not in codes  # said once, as critical
    new = ("HIPAA_BAA_NEEDED", "PCI_SCOPE", "RBI_COPIES_IN_INDIA", "ON_CALL_GAP", "PLATFORMS_TIMELINE")
    for out in (p4, hipaa, oncall, tight, critical):
        codes = [w["code"] for w in out["warnings"]]
        assert all(codes.count(c) <= 1 for c in new), codes


def test_no_card_scope_note_when_store_billing_takes_the_payments():
    out = run(_with("P6", project={"type": "social"}, requirements={"payments": True}))
    pay = [s["choice"] for s in out["stack"]["supporting"] if s["layer"] == "payments"]
    assert pay and "Google Play Billing" in pay[0] and "hosted checkout" not in pay[0], pay
    assert "PCI_SCOPE" not in _info(out), out["warnings"]


def test_score_trade_offs_skip_what_another_part_of_the_stack_handles():
    for name in ("P2", "P3", "P4", "P6"):
        out = run(_doc(name))
        for layer in ("database", "hosting"):
            lines = out["stack"][layer]["tradeoffs"]
            assert not [t for t in lines if t.startswith("Team skill match")], (name, layer, lines)
    p6 = run(_doc("P6"))["stack"]["database"]["tradeoffs"]  # offline is the sync service's job
    assert not [t for t in p6 if t.startswith("Offline support")], p6
    assert any("Realtime fit is only" in t for t in run(_doc("P2"))["stack"]["backend"]["tradeoffs"])  # still said


def test_gdpr_and_dpdp_duties_are_info_warnings_that_leave_the_status_alone():
    codes = lambda out: {w["code"]: w for w in out["warnings"]}  # noqa: E731
    p3, p2 = codes(run(_doc("P3"))), codes(run(_doc("P2")))
    assert p3["GDPR_DUTIES"]["severity"] == "info" and "72 hours" in p3["GDPR_DUTIES"]["message"]
    assert p2["DPDP_DUTIES"]["severity"] == "info" and "Data Protection Board" in p2["DPDP_DUTIES"]["message"]
    assert "DPDP_DUTIES" not in p3 and "GDPR_DUTIES" not in p2
    assert run(_doc("P5"))["status"] == "ok"  # P5 lists iso27001 only: no duty warning, status untouched


def test_ruled_out_options_are_listed_only_for_the_users_own_hard_constraints():
    alts = lambda out, layer: [(a["choice"], a["why_not"]) for a in out["stack"][layer]["alternatives"]]  # noqa: E731
    p1, p2 = run(_doc("P1")), run(_doc("P2"))
    assert not [a for a in alts(p1, "frontend") if a[1].startswith("Ruled out")]  # "Mobile toolkit" is padding here
    assert not [a for a in alts(p2, "database") if a[0].startswith("Redis")]
    assert ("Netlify", "Ruled out: No India region; data must stay in India") in alts(p2, "hosting")
    for out in (p1, p2, run(_doc("P5"))):
        for layer in ("frontend", "backend", "database", "hosting"):
            assert alts(out, layer), layer  # statement 4: at least one alternative per core layer


def test_every_supporting_service_of_the_public_scenarios_names_two_alternatives_except_a_reused_system():
    for name in ("P1", "P2", "P3", "P4", "P5", "P6"):
        for s in run(_doc(name))["stack"]["supporting"]:
            if "(existing)" in s["choice"]:
                continue  # a system the project already runs: the alternative is a second one beside it
            assert len(s["alternatives"]) >= 2 and all(a["why_not"] for a in s["alternatives"]), (name, s["choice"])
