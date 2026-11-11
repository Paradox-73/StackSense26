"""Hard-filter facts from the vendors' own pages (each entry whose facts were corrected cites the page it rests on)."""
import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from engine import recommend
from engine.advice import _object_storage
from engine.kb import load_kb
from engine.profile import INR_PER_USD

AUDIT = Path(__file__).resolve().parent / "scenarios_extra"


def _audit(name):
    for f in AUDIT.glob("*.json"):
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s["name"].startswith(name):
                return s["input"]
    raise KeyError(name)


def test_india_residency_picks_neither_flyio_nor_firebase():
    r = recommend(_audit("G11"), with_counterfactuals=False)
    picks = {r["stack"][l]["pick"]["id"] for l in ("backend", "hosting")}
    assert not picks & {"flyio", "firebase"}


def test_eu_residency_keeps_firebase_with_the_auth_caveat():
    """Firestore, Storage and Functions can be pinned to EU locations (eur3, europe-west*); only Firebase
    Authentication runs in the US. X1's Firebase team keeps the backend it knows, with the work needed to
    keep sign-in data in the EU stated as a risk."""
    r = recommend(_audit("X1"), with_counterfactuals=False)
    be = r["stack"]["backend"]
    assert "firebase" not in {e["id"] for e in be["excluded"]}
    assert be["pick"]["id"] == "firebase"
    assert any("Authentication runs only in US" in x for x in be["explanation"]["risks"])
    assert "https://firebase.google.com/docs/firestore/locations" in r["sources"]


def test_residency_caveat_applies_to_india_too():
    kb = load_kb()
    fb = kb["index"]["firebase"]
    assert {"europe", "india"} <= set(fb["residency_regions"]) and fb["residency_caveat"]
    raw = {"app_type": "mobile_first", "platforms": ["android"], "team_skills": ["flutter", "firebase"],
           "compliance": ["data_residency_india"], "regions": ["india"]}
    r = recommend(raw, with_counterfactuals=False)
    fire = next(x for x in r["stack"]["backend"]["ranking"] if x["id"] == "firebase")
    assert fire  # scored, not excluded
    if r["stack"]["backend"]["pick"]["id"] == "firebase":
        assert any("Authentication runs only in US" in x for x in r["stack"]["backend"]["explanation"]["risks"])


def test_corrected_facts_cite_their_pages():
    kb = load_kb()
    for iid in ("flyio", "cloudflare", "vercel", "render", "netlify", "digitalocean", "firebase", "supabase"):
        sources = kb["index"][iid].get("sources") or []
        assert sources and all(u.startswith("https://") for u in sources), iid


def test_compliance_floors():
    kb = load_kb()
    assert kb["index"]["render"]["compliance"]["hipaa_min_usd"] >= 499
    assert kb["index"]["netlify"]["compliance"]["pci"] and not kb["index"]["digitalocean"]["compliance"]["pci"]
    r = recommend({"compliance": ["soc2"], "team_skills": ["supabase"], "dau": 2000}, with_counterfactuals=False)
    if r["stack"]["backend"]["pick"]["id"] == "supabase":
        assert next(x for x in r["cost"]["lines"] if x["component"].startswith("Backend"))["low"] >= 599


def test_planning_fx_rate():
    assert INR_PER_USD == 96


def test_firebase_app_names_firebase_hosting():
    r = recommend(_audit("G5"), with_counterfactuals=False)
    assert "Firebase Hosting" in r["stack"]["hosting"]["runs_here"]


def test_large_document_corpus_gets_a_search_engine():
    r = recommend(_audit("E18"), with_counterfactuals=False)
    search = next(s for s in r["supporting_services"] if s["role"] == "Search")
    assert any(engine in search["name"] for engine in ("OpenSearch", "Meilisearch", "AI Search", "Elastic Cloud"))


def test_global_four_nines_sql_names_distributed_sql():
    r = recommend(_audit("G1_"), with_counterfactuals=False)
    assert any("distributed SQL" in x for x in r["stack"]["database"]["explanation"]["risks"])


def test_sql_server_is_kept_and_bigquery_is_the_gcp_warehouse(kb):
    """SQL Server / Azure SQL Database and BigQuery are in the knowledge base with cited sources: a .NET shop that
    must keep SQL Server keeps it (no migration warning), and a Google Cloud team's 10 TB dashboard gets BigQuery
    as its analytics store, while an AWS-hosted one keeps ClickHouse."""
    from engine.kb import validate_kb
    assert not validate_kb()
    for i in ("sqlserver", "bigquery"):
        assert all(s.startswith("https://") for s in kb["index"][i]["sources"])
    r = recommend({"app_type": "saas", "team_skills": ["csharp", "azure", "sql"], "existing_systems": ["sqlserver"],
                   "cloud_preference": "azure", "dau": 5000, "budget_monthly": 1000}, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "sqlserver"
    assert not {"EXISTING_SYSTEM_UNKNOWN", "EXISTING_SYSTEM_NOT_PICKED"} & {w["code"] for w in r["warnings"]}
    gcp = recommend({"app_type": "analytics_dashboard", "team_skills": ["python", "gcp", "sql"], "cloud_preference": "gcp",
                     "data_volume_gb": 10000, "data_shapes": ["analytical", "relational"], "dau": 2000,
                     "budget_monthly": 5000}, with_counterfactuals=False)
    names = " ".join(s["name"] for s in gcp["supporting_services"])
    assert gcp["stack"]["database"]["pick"]["id"] == "bigquery" or "BigQuery" in names
    aws = recommend({"app_type": "analytics_dashboard", "team_skills": ["python", "aws", "sql"], "cloud_preference": "aws",
                     "data_volume_gb": 10000, "data_shapes": ["analytical", "relational"], "dau": 2000,
                     "budget_monthly": 5000}, with_counterfactuals=False)
    assert aws["stack"]["database"]["pick"]["id"] != "bigquery"
    assert "BigQuery" not in " ".join(s["name"] for s in aws["supporting_services"])


def test_digitalocean_app_platform_is_scored_as_a_managed_paas():
    """App Platform builds from Git and runs, scales and patches the app with no servers to manage
    (https://docs.digitalocean.com/products/app-platform/), the same operating burden as Render or Railway."""
    idx = load_kb()["index"]
    assert idx["digitalocean"]["scores"]["ops"] == idx["render"]["scores"]["ops"] == idx["railway"]["scores"]["ops"] == 5


def test_digitalocean_has_no_free_app_service():
    """App Platform hosts static sites free; a service that runs code starts at $5 a month
    (https://www.digitalocean.com/pricing/app-platform)."""
    from engine.profile import derive, normalize
    from engine.scoring import tier_cost
    do = load_kb()["index"]["digitalocean"]

    def floor(raw):
        p, a, w = normalize(raw)
        d = derive(p, a, w)
        return tier_cost(do, 0, p, d)[0]
    assert floor({"app_type": "internal_tool", "dau": 50}) == 5
    assert floor({"app_type": "content_site", "dau": 50, "data_volume_gb": 0, "data_growth_gb_month": 0}) == 0


def test_static_hosts_claim_only_the_audits_a_public_page_lists_them_for():
    """Google's services-in-scope page lists Cloud Storage, Cloud CDN, Cloud Load Balancing and Firebase Hosting for
    ISO 27001, SOC 2 and PCI DSS, and its HIPAA page lists the first three. No public Microsoft page lists Front Door or
    Static Web Apps: Azure's per-service audit scope is an appendix in a Service Trust Portal document."""
    import re
    from engine.standard import run
    kb = load_kb()
    scope, hipaa = "https://cloud.google.com/security/compliance/services-in-scope", "https://cloud.google.com/security/compliance/hipaa"
    for iid in ("gcp_storage_cdn", "firebase_hosting"):
        c = kb["index"][iid]["compliance"]
        assert c["pci"] and c["soc2"] and c["iso27001"] and {scope, hipaa} <= set(c["maturity_sources"]), iid
    assert kb["index"]["gcp_storage_cdn"]["compliance"]["hipaa"] and not kb["index"]["firebase_hosting"]["compliance"]["hipaa"]
    for iid in ("azure_blob_frontdoor", "azure_static_web_apps"):
        c = kb["index"][iid]["compliance"]
        assert not [k for k in ("hipaa", "pci", "soc2", "iso27001") if c[k]], iid
    doc = json.loads((Path(__file__).resolve().parent.parent / "scenarios" / "public" / "P1.json").read_text(encoding="utf-8"))
    doc["infrastructure"]["cloud_preference"], doc["compliance"] = "azure", ["pci_dss"]
    out = run(doc)
    assert not (out["stack"] and re.match(r"Azure (Blob Storage|Static Web Apps)", out["stack"]["hosting"]["choice"])), out["stack"]


# The site of each object store's own documentation; a line is sourced to the first store it names.
STORE_SITES = {"Ceph Object Gateway": "docs.ceph.com", "Amazon S3": "amazon.com", "Cloud Storage": "cloud.google.com",
               "Blob Storage": "learn.microsoft.com", "DigitalOcean Spaces": "docs.digitalocean.com",
               "Cloudflare R2": "developers.cloudflare.com", "Tigris": "fly.io"}
BAA_PAGES = {"Amazon S3": "https://aws.amazon.com/compliance/hipaa-eligible-services-reference/",
             "Cloud Storage": "https://cloud.google.com/security/compliance/hipaa",
             "Blob Storage": "https://learn.microsoft.com/en-us/azure/compliance/offerings/offering-hipaa-us"}
NO_RULES = {"onprem": False, "hybrid": False, "cloud": None, "hipaa": False, "self_managed": False, "no_hyperscaler": False,
            "india": False, "eu": False, "us": False, "audit_rules": []}


@pytest.mark.parametrize("env,prov", [
    ({"onprem": True}, "onprem"), ({"hybrid": True}, "aws"), *[({"cloud": c}, c) for c in ("aws", "gcp", "azure")],
    *[({"cloud": c, "hipaa": True}, c) for c in ("aws", "gcp", "azure")], ({"hipaa": True, "self_managed": True}, "hetzner"),
    ({"hipaa": True}, "render"), ({"hipaa": True, "no_hyperscaler": True}, "flyio"),
    ({"india": True, "no_hyperscaler": True}, "digitalocean"), ({"india": True}, "render"), ({"eu": True}, "render"),
    ({}, "cloudflare"), ({}, "digitalocean"), ({}, "render")])
def test_each_object_store_line_cites_the_store_it_names(env, prov):
    """Every line cited Amazon S3's product page, Google Cloud Storage and Azure Blob Storage included. A line cites
    the first store it names, and a HIPAA line that names a cloud's store cites that cloud's HIPAA page; no public
    Microsoft page lists the services its BAA covers, so the Azure line does not say Blob Storage is under it."""
    name, src = _object_storage(dict(NO_RULES, **env), prov)
    first = min((name.index(k), k) for k in STORE_SITES if k in name)[1]
    assert STORE_SITES[first] in urlparse(src).netloc, (name, src)
    if "BAA" in name and first in BAA_PAGES:
        assert src == BAA_PAGES[first] and "under Microsoft's BAA" not in name, (name, src)


@pytest.mark.parametrize("rules,front_door", [([], True), (["hipaa"], True), (["pci_dss"], False), (["soc2"], False),
                                              (["iso27001"], False), (["hipaa", "iso27001"], False)])
def test_azure_uploads_skip_front_door_under_an_audit_it_does_not_publish(rules, front_door):
    """The knowledge base records Blob Storage + Front Door with no PCI DSS, SOC 2 or ISO 27001 audit (no public Microsoft
    page lists Front Door's scope), and Microsoft's Azure Storage page puts Blobs in all three: under any of them uploads
    skip Front Door, citing that page. HIPAA alone keeps Front Door for public, non-PHI files."""
    held = load_kb()["index"]["azure_blob_frontdoor"]["compliance"]
    assert not (held["pci"] or held["soc2"] or held["iso27001"])
    env = dict(NO_RULES, cloud="azure", hipaa="hipaa" in rules, audit_rules=[r for r in rules if r != "hipaa"])
    name, src = _object_storage(env, "azure")
    assert ("without Front Door" not in name) == front_door and "Front Door" in name, name
    assert ("in scope for Microsoft's HIPAA BAA" in name) == ("hipaa" in rules), name
    if not front_door and "hipaa" not in rules:
        assert src == "https://learn.microsoft.com/en-us/azure/storage/common/storage-compliance-offerings", src
