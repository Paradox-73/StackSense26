"""Each host says what runs on it; a mobile-only app on a BaaS has no host of its own to pay for."""
import pytest

from engine import recommend
from engine.export import to_markdown


def test_mobile_only_baas_hosting_is_provided_by_the_baas(presets):
    r = recommend(presets["india_social_mobile"]["input"], with_counterfactuals=False)
    h = r["stack"]["hosting"]
    assert h["pick"]["name"] == "Provided by Firebase"
    assert h["optional_host"]
    assert not [x for x in r["cost"]["lines"] if x["component"].startswith("Hosting")]
    md = to_markdown(r)
    assert "OpenNext" not in md


def test_every_preset_says_what_runs_on_the_host(presets):
    for pid, pr in presets.items():
        r = recommend(pr["input"], with_counterfactuals=False)
        if r.get("feasible"):
            assert r["stack"]["hosting"]["runs_here"], pid


def test_runs_here_names_frontend_and_api():
    r = recommend({"team_skills": ["python", "django"], "budget_monthly": 200}, with_counterfactuals=False)
    text = r["stack"]["hosting"]["runs_here"]
    be = r["stack"]["backend"]["pick"]["name"].split(" (")[0]
    if r["stack"]["backend"]["pick"]["id"] not in ("supabase", "firebase"):
        assert be in text


def test_mobile_only_baas_never_names_the_unused_web_host(presets):
    r = recommend(presets["india_social_mobile"]["input"])
    for cf in r["counterfactuals"]:
        for e in cf["effects"]:
            if e["layer"] == "hosting":
                assert e["from"] == "Provided by Firebase" or e["to"] == "Provided by Firebase", cf
    for alt in r["alternative_stacks"]:
        if alt["stack"]["backend"].startswith("Firebase"):
            assert alt["stack"]["hosting"] == "Provided by Firebase", alt


def test_embedded_database_is_not_called_a_managed_service():
    """SQLite is a file the API process opens on its own disk, not a separate managed service."""
    from engine.advice import runs_here
    from engine.kb import load_kb
    kb = load_kb()["index"]
    stack = {"frontend": kb["htmx"], "backend": kb["django"], "database": kb["sqlite"], "hosting": kb["flyio"]}
    p, d = {"compliance": []}, {"web": True, "mobile": False}
    text = runs_here(p, d, stack)
    assert "managed service" not in text
    assert "embedded single-file database" in text and "no separate database server" in text
    stack["database"] = kb["postgres"]
    assert "separate managed service" in runs_here(p, d, stack)


def test_spa_on_container_host_is_served_from_the_clouds_object_storage_and_cdn(presets):
    """A browser SPA on a stack hosted on containers is built to files that the same cloud's object storage +
    CDN serves, said in the hosting text, listed as a service and priced; and a search engine's size basis is
    the estimated document corpus, not the whole data volume."""
    r = recommend(presets["hipaa_telehealth"]["input"], with_counterfactuals=False)
    assert r["stack"]["frontend"]["pick"]["id"] == "react_spa" and r["stack"]["hosting"]["pick"]["id"] == "aws_ecs"
    assert "Amazon S3 + CloudFront" in r["stack"]["hosting"]["runs_here"]
    svc = next(s for s in r["supporting_services"] if s["role"] == "Static frontend")
    assert svc["name"] == "Amazon S3 + CloudFront"
    assert any(x["component"].startswith("Static frontend") for x in r["cost"]["lines"])
    gcp = recommend({"app_type": "saas", "team_skills": ["python", "react", "gcp"], "cloud_preference": "gcp",
                     "dau": 20000, "budget_monthly": 800}, with_counterfactuals=False)
    if gcp["stack"]["frontend"]["pick"]["id"] == "react_spa" and gcp["stack"]["hosting"]["pick"]["id"] == "gcp_cloud_run":
        line = next(x for x in gcp["cost"]["lines"] if x["component"] == "Static frontend")
        assert line["low"] > 0 and "cloud.google.com/cdn/pricing" in line["basis"]
    big = recommend({"app_type": "saas", "data_shapes": ["relational", "document"], "data_volume_gb": 400,
                     "data_growth_gb_month": 20, "dau": 20000, "budget_monthly": 3000}, with_counterfactuals=False)
    search = [s for s in big["supporting_services"] if s["role"] == "Search"]
    assert search and "estimate" in search[0]["why"] and "~213 GB of documents" in search[0]["why"]


CLOUD_SPA = {"aws": (["python", "react", "aws"], "aws_ecs", "Amazon S3 + CloudFront"),
             "gcp": (["python", "react", "gcp"], "gcp_cloud_run", "Cloud Storage bucket + Cloud CDN"),
             "azure": (["csharp", "react", "azure"], "azure_apps", None)}
ATTESTATION_GAP = {"pci_dss": "No PCI-DSS attestation published", "iso27001": "No ISO/IEC 27001 certification published",
                   "soc2": "No SOC 2 report available", "hipaa": "No HIPAA Business Associate Agreement available"}


@pytest.mark.parametrize("rule", sorted(ATTESTATION_GAP))
@pytest.mark.parametrize("cloud", sorted(CLOUD_SPA))
def test_spa_files_go_to_the_clouds_cdn_only_if_it_holds_the_attestation(cloud, rule):
    """The knowledge base records S3 + CloudFront and Cloud Storage + Cloud CDN as holding HIPAA, PCI DSS, SOC 2 and
    ISO 27001, and Blob Storage + Front Door as holding none (no public Microsoft page lists Front Door's audit scope).
    The hosting layer rules a host out for a missing one, so the built files may not go there either: on Azure they
    stay on the app's own instances, and the hosting text says why."""
    skills, host, pairing = CLOUD_SPA[cloud]
    r = recommend({"app_type": "saas", "team_skills": skills, "cloud_preference": cloud, "cloud_required": True,
                   "dau": 20000, "budget_monthly": 2000, "seo": "none", "compliance": [rule]}, with_counterfactuals=False)
    assert (r["stack"]["frontend"]["pick"]["id"], r["stack"]["hosting"]["pick"]["id"]) == ("react_spa", host)
    static = [s["name"] for s in r["supporting_services"] if s["role"] == "Static frontend"]
    text, request = r["stack"]["hosting"]["runs_here"], r["architecture"]["how_parts_fit"][0]["text"]
    if pairing:
        assert static == [pairing] and pairing in text and pairing in request, (static, text, request)
        return
    assert static == [] and not [x for x in r["cost"]["lines"] if x["component"].startswith("Static frontend")], static
    assert text.startswith("Runs here: React SPA (static files), ") and "Front Door" not in request, (text, request)
    assert ("Azure Blob Storage + Front Door would serve the static files from the edge, but it fails your compliance "
            f"rules ({ATTESTATION_GAP[rule]}).") in text, text
