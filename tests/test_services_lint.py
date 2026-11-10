"""Supporting services must not contradict the hard inputs: no cloud-only service on-premises, no
service without an Indian (or EU) region under a residency rule, no service without a BAA under
HIPAA. Facts behind the name lists (checked on the vendors' pages):
  - Clerk hosts data on US infrastructure only; Auth0 public cloud has no Indian region.
  - Cloudflare R2 and Workers KV jurisdictions: EU and FedRAMP (+ US for KV) only.
  - Backblaze B2 regions: US West, US East, EU Central, CA East. Sentry SaaS: US or EU.
  - Upstash signs a BAA only on Enterprise; Cloudflare only under Enterprise agreements.
Also checks the ops budget: compliance services are never deferred, and every deferred service
names the trigger for adding it."""
import json
import random
from pathlib import Path

import pytest

from engine import recommend
from engine.kb import load_presets
from tools.profiles import random_input

CLOUD_ONLY = ["Cloudflare R2", "Backblaze", "Grafana Cloud", "Sentry", "SQS", "hosted model API", "Clerk", "Auth0",
              "Upstash", "MongoDB Atlas", "ClickHouse Cloud", "AuraDB", "Timescale Cloud", "Workers KV", "Turso"]
NOT_IN_INDIA = ["Clerk", "Auth0", "Cloudflare R2", "Backblaze", "Workers KV", "Sentry"]
NOT_IN_EU = ["Clerk"]
HIPAA_NO_BAA_STATED = ["Cloudflare R2", "Upstash", "Clerk", "Grafana Cloud", "Sentry", "Pusher"]
AUDIT_DIR = Path(__file__).resolve().parent / "scenarios_extra"


def lint(r: dict) -> list[str]:
    p = r["profile"]
    texts = [(s["role"], s["name"]) for s in r["supporting_services"] + r.get("deferred_services", [])]
    offer = r["stack"]["database"].get("managed_offering")
    if offer:
        texts.append(("database offering", offer))
    if p["deployment"] == "on_prem":
        texts.append(("database", r["stack"]["database"]["pick"]["name"]))
    hits = []
    for role, t in texts:
        if p["deployment"] == "on_prem":
            hits += [f"on-prem: {role} -> {k}" for k in CLOUD_ONLY if k in t]
        if "data_residency_india" in p["compliance"]:
            hits += [f"India residency: {role} -> {k}" for k in NOT_IN_INDIA if k in t]
        if "data_residency_eu" in p["compliance"]:
            hits += [f"EU residency: {role} -> {k}" for k in NOT_IN_EU if k in t]
        if "hipaa" in p["compliance"]:
            hits += [f"HIPAA: {role} -> {k}" for k in HIPAA_NO_BAA_STATED if k in t and "BAA" not in t]
    if p["deployment"] == "on_prem":
        if "AZ" in r["architecture"]["redundancy"]:
            hits.append("on-prem: availability text mentions availability zones")
        hits += [f"on-prem: paid BaaS line {x['component']}" for x in r["cost"]["lines"]
                 if x["component"].startswith("Backend:") and x["high"] > 0]
    if r["stack"]["backend"]["pick"]["id"] not in ("supabase", "firebase") and \
            any("load balancer" in s for s in [r["architecture"]["redundancy"]]) is False:
        pass
    deferred_roles = {s["role"] for s in r.get("deferred_services", [])}
    if deferred_roles & {"Audit & security", "Authentication", "Observability", "Payments"}:
        hits.append(f"must-have service deferred: {deferred_roles}")
    hits += [f"deferred without trigger: {s['role']}" for s in r.get("deferred_services", []) if not s.get("trigger")]
    return hits


def _inputs():
    out = [(p["id"], p["input"]) for p in load_presets()]
    for f in sorted(AUDIT_DIR.glob("*.json")):
        out += [(s["name"], s["input"]) for s in json.loads(f.read_text(encoding="utf-8"))]
    rng = random.Random(2026)
    out += [(f"random {i}", random_input(rng)) for i in range(500)]
    return out


def test_services_never_contradict_constraints():
    bad = {}
    for name, inp in _inputs():
        r = recommend(inp, with_counterfactuals=False)
        if r.get("feasible"):
            hits = lint(r)
            if hits:
                bad[name] = hits
    assert not bad, f"{len(bad)} outputs contradict a constraint, e.g. {list(bad.items())[:5]}"


def test_on_prem_default_has_no_paid_supabase():
    r = recommend({"deployment": "on_prem"}, with_counterfactuals=False)
    assert not [x for x in r["cost"]["lines"] if "Supabase" in x["component"] and x["high"] > 0]


def test_self_hosted_baas_is_scored_as_self_operated():
    from engine.kb import load_kb
    from engine.profile import derive, normalize
    from engine.scoring import SELF_HOSTED_BAAS_OPS, adjustments, raw_scores, tier_cost
    p, a, w = normalize({"deployment": "on_prem"})
    d = derive(p, a, w)
    supa = load_kb()["index"]["supabase"]
    assert raw_scores("backend", supa, p, d, {})["ops"] == SELF_HOSTED_BAAS_OPS
    assert tier_cost(supa, 3, p) == (0.0, 0.0)
    assert any("containers" in x["reason"] for x in adjustments("backend", supa, p, d))


def test_small_team_defers_extra_systems_with_triggers(presets):
    r = recommend(presets["india_social_mobile"]["input"], with_counterfactuals=False)
    later = {s["role"]: s for s in r.get("deferred_services", [])}
    assert "Secondary store (graph)" in later and "Neo4j" in later["Secondary store (graph)"]["name"]
    assert "Analytics" in later and "ClickHouse" in later["Analytics"]["name"]
    assert all(s["trigger"] for s in later.values())
    assert not any("Neo4j" in x["component"] or "ClickHouse" in x["component"] for x in r["cost"]["lines"])
    assert len(r["ops_budget"]["extra_systems"]) <= r["ops_budget"]["cap"]


@pytest.mark.parametrize("pid", ["india_ecommerce_scale", "hipaa_telehealth", "contradictory"])
def test_regulated_presets_never_defer_audit(presets, pid):
    for team in (1, 3, 8):
        r = recommend(dict(presets[pid]["input"], team_size=team), with_counterfactuals=False)
        if r.get("feasible"):
            assert any(s["role"] == "Audit & security" for s in r["supporting_services"])
            assert not any(s["role"] == "Audit & security" for s in r.get("deferred_services", []))
