"""Detects contradictory or risky input combinations and states how each is resolved.

Resolution policy (highest priority first):
  1. Compliance and data residency are never relaxed.
  2. Deployment model (on-prem/cloud) is respected.
  3. Physics and team capacity override preferences (latency floors, on-call load).
  4. Budget and preferences (cloud, lock-in, architecture) are soft and may be overridden, with a warning.
"""
from __future__ import annotations

from .profile import _warn


# People needed for a 24x7 on-call rotation without burnout (one week on call in five or six).
SLA_ONCALL_MIN_TEAM = 6
# Three or more client platforms (each with its own build, testing and release) cannot all ship in this many weeks.
MANY_PLATFORMS_MIN_WEEKS = 4


def _n(count, noun: str) -> str:
    return f"{count:g} {noun}" + ("" if count == 1 else "s")


def detect(p: dict, d: dict) -> list[dict]:
    w: list[dict] = []
    team = p["team_size"]
    budget = d["budget_usd"]
    tier = d["compute_tier"]

    if p["architecture"] == "microservices" and team < 6:
        d["architecture"] = "monolith"
        w.append(_warn("MICROSERVICES_SMALL_TEAM", "warning", f"Microservices with {_n(team, 'engineer')}",
                       "Microservices pay off when several teams need independent deploys; with a small team they multiply deploy pipelines, network failure modes and on-call load (Fowler, 'MonolithFirst').",
                       "Recommending a modular monolith with clear module boundaries that can be split later.",
                       ["architecture", "team_size"]))
    if p["deployment"] == "on_prem" and p["architecture"] == "serverless":
        d["architecture"] = "monolith"
        w.append(_warn("ONPREM_SERVERLESS", "warning", "Serverless requested on-premises",
                       "Managed FaaS platforms do not run in your data centre; Knative/OpenFaaS would add a platform to operate.",
                       "Using long-running containers instead.", ["architecture", "deployment"]))
    if p["deployment"] == "on_prem" and p["cloud_preference"] != "none":
        w.append(_warn("ONPREM_CLOUD_PREF", "info", "Cloud preference ignored",
                       f"Deployment is on-premises, so the '{p['cloud_preference']}' preference cannot apply.",
                       "Cloud preference ignored.", ["cloud_preference", "deployment"]))
    if "hipaa" in p["compliance"] and budget < 100:
        w.append(_warn("HIPAA_FREE_TIER", "critical", "HIPAA on a free-tier budget",
                       "HIPAA requires a signed Business Associate Agreement (BAA); vendors offer BAAs only on paid plans or eligible paid services.",
                       "Compliance is kept as a hard filter; the budget is treated as soft and the real minimum cost is shown.",
                       ["compliance", "budget_monthly"]))
    if d["availability"] >= 99.99 and team < SLA_ONCALL_MIN_TEAM:
        w.append(_warn("SLA_SMALL_TEAM", "warning", f"{p['availability']}% availability with {_n(team, 'engineer')}",
                       f"99.99% allows ~4.4 minutes of downtime a month; that needs 24x7 on-call and multi-AZ/multi-region "
                       f"failover. A sustainable on-call rotation needs about {SLA_ONCALL_MIN_TEAM} people; {team} cannot staff it.",
                       "Weighted towards fully managed services; consider 99.9% as a realistic SLO.",
                       ["availability", "team_size"]))
    if budget == 0 and d["availability"] >= 99.9:
        w.append(_warn("FREE_TIER_NO_SLA", "warning", f"{p['availability']}% availability on free tiers only",
                       "Free plans of hosting and database vendors carry no uptime guarantee (no SLA), and many pause or throttle idle projects.",
                       "Treat the availability target as a goal; a paid plan is needed to get a written SLA.",
                       ["availability", "budget_monthly"]))
    if p["app_type"] == "internal_tool" and p["dau"] >= 10000:
        w.append(_warn("INTERNAL_TOOL_SCALE", "info", f"Internal tool with {p['dau']:,} daily users",
                       "Internal tools are used by one company's staff; this many daily users is more typical of a public product.",
                       "Kept as given. Check that daily users counts people, not events.", ["dau", "app_type"]))
    if p["timeline_weeks"] <= 4 and any(c in p["compliance"] for c in ("hipaa", "pci_dss", "soc2")):
        w.append(_warn("COMPLIANCE_TIMELINE", "warning", "Compliance on a very short timeline",
                       "BAAs, risk assessments, audit logging and access reviews typically take longer than a few weeks.",
                       "Recommending managed, pre-certified services to shorten the path.",
                       ["timeline_weeks", "compliance"]))
    if p["latency_target_ms"] < 30 and (len(p["regions"]) > 1 or "global" in p["regions"]):
        w.append(_warn("LATENCY_PHYSICS", "warning", f"{p['latency_target_ms']:.0f} ms target across regions",
                       "Light in fibre needs roughly 70+ ms for an intercontinental round trip; a single origin cannot meet this globally.",
                       "Favouring edge/multi-region platforms; treat the target as per-region latency.",
                       ["latency_target_ms", "regions"]))
    elif p["latency_target_ms"] < 20:
        w.append(_warn("LATENCY_TIGHT", "warning", f"{p['latency_target_ms']:.0f} ms end-to-end target",
                       "Under 20 ms leaves almost no room for network hops: one cross-zone database round trip takes 1-2 ms, "
                       "a TLS handshake from a phone 50+ ms. Such targets are met only server-side, with hot state in memory.",
                       "Treat the target as server processing time; keep hot data in memory or a cache, co-locate services "
                       "in one zone, and measure p99 under load.", ["latency_target_ms"]))
    if p["seo"] != "none" and not d["web"]:
        w.append(_warn("SEO_NO_WEB", "info", "SEO needed but no web platform",
                       "Search engines index web pages, not app binaries.",
                       "A web companion (landing/content site) is suggested alongside the mobile app.",
                       ["seo", "platforms"]))
    if p["offline"] and not d["mobile"]:
        w.append(_warn("OFFLINE_WEB", "info", "Offline support on web only",
                       "Browsers support offline through service workers and IndexedDB (PWA).",
                       "Weighting frameworks with good PWA/offline support.", ["offline", "platforms"]))
    if "data_residency_india" in p["compliance"] and p["regions"] and "india" not in p["regions"] and "global" not in p["regions"]:
        w.append(_warn("RESIDENCY_REGION", "info", "Indian data residency with no Indian users selected",
                       "Data will be stored in India while users are elsewhere, which adds latency.",
                       "Residency kept as a hard filter.", ["compliance", "regions"]))
    if "data_residency_eu" in p["compliance"] and "data_residency_india" in p["compliance"]:
        w.append(_warn("DUAL_RESIDENCY", "warning", "Both EU and India residency",
                       "One deployment cannot keep the same data in both jurisdictions only.",
                       "Recommending providers with both regions; you will need regional data partitioning (separate EU and India deployments).",
                       ["compliance"]))
    if tier >= 4 and team <= 2:
        w.append(_warn("SCALE_SMALL_TEAM", "warning", "Very large scale with a tiny team",
                       f"{d['tier_label']} traffic is usually run by dedicated platform engineers.",
                       "Strongly favouring managed/serverless services with low ops burden.",
                       ["dau", "team_size"]))
    if tier <= 1 and budget > 20000:
        w.append(_warn("BUDGET_OVERSIZED", "info", "Budget far above what this scale needs",
                       "A budget is a ceiling, not a target.", "Cost still weighted; the estimate shows expected spend.",
                       ["budget_monthly"]))
    exp = p.get("team_experience", "intermediate")
    if d["availability"] >= 99.95 and exp == "beginner" and team < SLA_ONCALL_MIN_TEAM:
        w.append(_warn("BEGINNER_HIGH_AVAILABILITY", "critical",
                       f"{p['availability']}% availability from a beginner team of {team}",
                       f"{p['availability']}% allows at most {(100 - d['availability']) * 438:.0f} minutes of downtime a "
                       "month. Meeting it takes multi-zone failover, tested restores and someone on call who can fix "
                       "production at night, which a beginner team of this size cannot staff.",
                       "Relaxed: the stack uses managed services whose providers carry the SLA, and the target is "
                       "treated as a goal until the team can staff on-call; 99.9% is a realistic first commitment.",
                       ["availability", "team_experience", "team_size"]))
    clients = [x for x in p["platforms"] if x != "api_only"]
    if len(clients) >= 3 and p["timeline_weeks"] <= MANY_PLATFORMS_MIN_WEEKS:
        # The relaxation below, made binding: the frontend must be one toolkit that builds every web and phone target.
        d["one_codebase"] = [x for x in ("web", "android", "ios") if x in clients]
        w.append(_warn("MANY_PLATFORMS_SHORT_TIMELINE", "critical",
                       f"{len(clients)} client platforms in {_n(p['timeline_weeks'], 'week')}",
                       f"Each of {', '.join(clients)} needs its own build, testing and store or release work; "
                       f"{_n(p['timeline_weeks'], 'week')} is not enough to ship all of them with {_n(team, 'engineer')}.",
                       "Relaxed: one shared codebase is recommended, and the first release should ship one platform "
                       "(the one most users need), with the others after the MVP.",
                       ["platforms", "timeline_weeks", "team_size"]))
    if p.get("has_devops") is False and (p["deployment"] in ("on_prem", "hybrid") or p.get("self_managed")):
        w.append(_warn("SELF_HOSTED_NO_OPS", "warning", "Self-hosted servers but nobody to operate them",
                       "The deployment model puts servers, patching, backups and monitoring on the team, and the team "
                       "says nobody can operate infrastructure.",
                       "Kept as given: the stack sticks to one deployable and boring, well-documented tools. Budget for "
                       "an operations hire or a managed-services contract before go-live.",
                       ["has_devops", "deployment"]))
    pays = "pay" in (p.get("user_actions") or []) or (
        p["app_type"] in ("ecommerce", "fintech") and "user_actions" in d.get("defaulted", ()))
    # Each outside service the project needs: (what, the answer behind it, how on-premises keeps it, how air-gapped relaxes it)
    needs = [n for n, on in (
        (("taking payments", "user_actions", "a payment gateway's hosted checkout",
          "payments run on a separate connected system and are imported for reconciliation"), pays),
        (("SMS one-time codes", "special_workloads", "an SMS gateway",
          "SMS goes through a GSM modem inside the network or authenticator-app codes replace it"),
         "phone_otp" in (p.get("special_workloads") or [])),
        (("push notifications", "platforms", "the phone push services (FCM and APNs)", "phones get in-app notifications only"),
         d["mobile"])) if on] if p["deployment"] == "on_prem" else []
    outside, fields = [n[0] for n in needs], [n[1] for n in needs]
    if outside and not p.get("air_gapped"):
        w.append(_warn("ONPREM_EXTERNAL", "critical", "On-premises, but the project needs outside services",
                       f"The project needs {', '.join(outside)}, and no payment network, SMS network or phone push service "
                       "can run on your own servers.",
                       "Kept as outside services reached through your firewall's outbound rules: "
                       f"{', '.join(n[2] for n in needs)}. Every other component in the stack is self-hosted, and uploads "
                       "are served by your own reverse proxy instead of a CDN.",
                       ["deployment"] + fields))
    if p.get("air_gapped"):
        if outside:
            w.append(_warn("AIR_GAPPED_EXTERNAL", "critical", "Air-gapped network, but the project needs outside services",
                           f"A network with no internet connection cannot reach a payment gateway, an SMS provider or the "
                           f"phone push services, and the project needs {', '.join(outside)}.",
                           f"Relaxed: {'; '.join(n[3] for n in needs)}. Confirm each with the network's security owner.",
                           ["air_gapped"] + fields))
    if p["team_size"] > 200 and tier <= 1:
        w.append(_warn("TEAM_OVERSIZED", "info", "Very large team for a small user base",
                       "Check the team size counts engineers on this product only.", "Kept as given.", ["team_size"]))
    return w
