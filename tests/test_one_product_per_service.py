"""Each supporting choice is one real product, each layer of sign-in, CDN and file storage appears once, and a service
is listed only when the stack has something that uses it."""
import json
from pathlib import Path

import pytest

from engine.advice import supporting_services
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = sorted((ROOT / "scenarios" / "public").glob("P*.json"))


def _doc(name: str) -> dict:
    return json.loads((ROOT / "scenarios" / "public" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def outs() -> dict:
    return {p.stem: run(json.loads(p.read_text(encoding="utf-8"))) for p in PUBLIC}


def _choices(out: dict) -> list[str]:
    return [s["choice"] for s in out["stack"]["supporting"]]


def _sup(out: dict, layer: str) -> list[dict]:
    return [s for s in out["stack"]["supporting"] if s["layer"] == layer]


def test_sign_in_cdn_and_file_storage_appear_once(outs):
    sso = _doc("P4")
    sso["requirements"].update(auth="enterprise_sso", multi_tenant=False)
    for name, out in dict(outs, P4_sso=run(sso)).items():
        for layer in ("auth", "cdn", "storage"):
            assert len(_sup(out, layer)) <= 1, (name, layer, [s["choice"] for s in _sup(out, layer)])
    assert "Keycloak" not in json.dumps(_choices(run(sso)))  # one tenant: a federation, not a broker


def test_no_generic_cdn_and_no_product_lists(outs):
    text = json.dumps({k: [s["choice"] for s in o["stack"]["supporting"]] for k, o in outs.items()})
    for vague in ("CDN in front of the object storage", "Clerk / Auth0", "Razorpay / Cashfree", "Stripe / Adyen",
                  "or Expo Notifications", "Spring Batch", "PowerSync or ElectricSQL", "or Twilio Verify"):
        assert vague not in text, vague
    assert " / " not in outs["P5"]["stack"]["hosting"]["choice"], outs["P5"]["stack"]["hosting"]["choice"]


def test_no_self_hosted_keycloak_without_devops(outs):
    for name in ("P2", "P6"):  # has_devops false, India residency
        assert "Keycloak" not in json.dumps(_choices(outs[name])), name


def test_push_service_follows_the_mobile_framework(outs):
    push = {k: [s["choice"] for s in o["stack"]["supporting"] if "push" in s["choice"].lower() or "Messaging" in s["choice"]]
            for k, o in outs.items()}
    assert push["P6"] and push["P6"][0].startswith("Expo push"), push  # React Native (Expo)
    assert push["P4"] and push["P4"][0].startswith("Firebase Cloud Messaging"), push  # native iOS and Android


def test_india_payments_lead_with_razorpay_and_aws_jvm_jobs_use_sqs(outs):
    pay = _sup(outs["P4"], "payments")
    assert pay and pay[0]["choice"].startswith("Razorpay"), pay
    jobs = [s["choice"] for s in _sup(outs["P4"], "queue")]
    assert any("Amazon SQS" in c for c in jobs), jobs  # Spring Boot on AWS


def test_no_cache_when_no_app_code_runs_on_the_cloud():
    kb = load_kb()
    p, a, w = normalize({"app_type": "ecommerce", "dau": 60_000, "read_write": "read_heavy"})
    d = derive(p, a, w)
    stack = {l: kb["index"][i] for l, i in (("frontend", "nextjs"), ("backend", "supabase"), ("database", "postgres"),
                                             ("hosting", "aws_s3_cloudfront"))}
    roles = [s["role"] for s in supporting_services(p, d, stack, [])]
    assert "Cache" not in roles, roles
    stack["backend"] = kb["index"]["express"]
    stack["hosting"] = kb["index"]["aws_ecs"]
    assert "Cache" in [s["role"] for s in supporting_services(p, d, stack, [])]


def test_azure_caches_are_azure_managed_redis():
    """Azure Cache for Redis retires (Basic, Standard and Premium on 30 Sep 2028, Enterprise on 31 Mar 2027) and
    Microsoft's retirement FAQ points new caches to Azure Managed Redis."""
    from engine.advice import portable_offering
    kb = load_kb()["index"]
    assert portable_offering(kb["redis"], kb["azure_apps"], False, False) == "Azure Managed Redis"
    assert "https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/retirement-faq" in kb["redis"]["sources"]


def test_sign_in_under_india_residency_stays_on_the_required_cloud():
    for cloud in ("gcp", "azure"):
        doc = _doc("P4")  # Spring Boot, data_residency india, has_devops true
        doc["infrastructure"]["cloud_preference"] = cloud
        auth = [s["choice"] for s in _sup(run(doc), "auth")]
        assert auth and not [a for a in auth if "Amazon" in a or "Cognito" in a], (cloud, auth)


def test_gpu_work_beside_azure_app_service_is_named_on_container_apps():
    """The Azure host is named App Service; its GPU work runs on Container Apps serverless GPUs, named on its own line."""
    doc = _doc("P3")
    doc["infrastructure"]["cloud_preference"] = "azure"
    doc["requirements"]["ml_features"] = "training"
    out = run(doc)
    assert out["stack"]["hosting"]["choice"].startswith("Azure App Service"), out["stack"]["hosting"]["choice"]
    assert "Azure Container Apps serverless GPUs" in _choices(out), _choices(out)


@pytest.mark.parametrize("role,name,alt", [
    ("Game servers", "Amazon GameLift Servers (managed dedicated game servers, with FlexMatch matchmaking)", "Agones"),
    ("Game servers", "Agones (dedicated game servers on Kubernetes)", "Amazon GameLift Servers"),
    ("Desktop app", "Electron, packaging the web frontend as a Windows, macOS and Linux app", "Tauri"),
    ("Desktop app", "Qt (C++), a native Windows, macOS and Linux app beside the web frontend", "Electron"),
    ("Background jobs", "Apache Kafka (existing)", "A new message broker"),
    ("Analytics", "Snowflake (existing)", "A new analytics store"),
    ("Payments", "App Store In-App Purchase for digital goods and subscriptions sold in the app", "A card processor"),
])
def test_services_added_by_other_rules_get_an_alternative_and_a_tradeoff(role, name, alt):
    from engine.advice import service_notes
    alts, trade = service_notes({"role": role, "name": name})
    assert any(a.startswith(alt) for a, _ in alts) and all(w for _, w in alts) and trade, (alts, trade)


def test_uploads_on_azure_under_audits_and_india_residency_stay_private():
    out = run(_doc("P5"))  # Azure, data_residency india, ISO 27001, uploads
    store = [s["choice"] for s in _sup(out, "storage")]
    assert store and "private container" in store[0] and "SAS" in store[0] and "Front Door" in store[0], store
