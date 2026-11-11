"""Criterion weights (with the inputs that set them), hard constraints and per-technology scoring.

Score of a technology t in layer L:
    base(t)   = sum_c w_c * s_c(t) / sum_c w_c        (s on 1-5, rescaled to 0-100)
    final(t)  = clamp(base(t) + sum of adjustments, 0, 100)
Each weight w_c is a sum of contributions a_{c,i} from inputs i, so base(t) decomposes exactly
into per-input contributions: contrib_i(t) = sum_c a_{c,i} * s'_c(t) / W.
"""
from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache

from .kb import CRITERION_LABELS, LAYER_CRITERIA, load_kb
from .profile import DAU_THRESHOLDS, TIER_LABELS, tier_label

BASELINE = {
    "maturity": 1.0, "velocity": 1.0, "ops": 1.0, "cost": 1.0, "scalability": 1.0,
    "ease": 0.5, "hiring": 0.5, "performance": 0.5, "portability": 0.5, "structure": 0.3,
    "realtime": 0.2, "seo": 0.2, "offline": 0.0, "interactivity": 0.5, "data_fit": 5.0, "consistency_fit": 1.0,
    "region_fit": 1.0, "skill_fit": 0.0, "compliance_maturity": 0.0,
}

# Regulated data whose rules scale with volume. HIPAA: breaches of 500+ records must be reported to
# HHS and the media; PCI DSS: Level 1 merchants (>6M card transactions/year) need an annual on-site
# assessment, so every provider in scope must show its own Level 1 attestation.
REGULATED = ("hipaa", "pci_dss")
REGULATED_SOURCES = [
    "https://www.hhs.gov/hipaa/for-professionals/breach-notification/index.html",
    "https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html",
    "https://www.pcisecuritystandards.org/document_library/",
]

INPUT_LABELS = {
    "baseline": "General quality (baseline weights)",
    "clamp": "Score limit (scores stop at 0 and 100)",
    "budget_monthly": "Monthly budget", "timeline_weeks": "Time to MVP", "team_size": "Team size",
    "dau": "Scale (DAU / peak RPS)", "realtime": "Realtime needs", "latency_target_ms": "Latency target",
    "seo": "SEO need", "offline": "Offline support", "availability": "Availability target",
    "lock_in_tolerance": "Lock-in tolerance", "deployment": "Deployment model", "team_skills": "Team skills",
    "compliance": "Compliance", "app_type": "Application type", "read_write": "Read/write mix",
    "consistency": "Consistency need", "architecture": "Architecture preference",
    "cloud_preference": "Cloud preference", "data_shapes": "Data shape", "regions": "User regions",
    "platforms": "Client platforms", "priorities": "Your priority", "existing_systems": "Existing systems", "stack": "Stack compatibility", "data_volume_gb": "Data volume",
    "team_experience": "Team experience", "has_devops": "Infrastructure skills", "self_managed": "Self-managed VMs",
    "cloud_required": "Required cloud", "ml_features": "Machine-learning features", "air_gapped": "Air-gapped network",
}


# Your top-3 priorities: each adds weight to the criteria below, scaled by rank (first = 1.0, then 0.7, 0.4).
PRIORITY_CRITERIA = {
    "cost": [("cost", 2.0)], "speed": [("velocity", 1.5), ("ease", 0.5)], "scale": [("scalability", 1.5), ("performance", 0.5)],
    "performance": [("performance", 1.5), ("realtime", 0.3)], "low_ops": [("ops", 2.0)], "proven": [("maturity", 1.5), ("hiring", 0.5)],
    # Maintainable: enforced structure and a small surface to operate; secure: the provider's attestations, audit
    # logging and isolation options (the compliance-maturity criterion) and mature, well-patched tools.
    "maintainability": [("structure", 1.0), ("ops", 0.7), ("maturity", 0.3)],
    "security": [("compliance_maturity", 1.5), ("maturity", 0.5)],
}
PRIORITY_RANK_FACTOR = (1.0, 0.7, 0.4)
PRIORITY_LABELS = {"cost": "lowest cost", "speed": "ship fastest", "scale": "scale to many users",
                   "performance": "fast responses", "low_ops": "least maintenance", "proven": "proven, mature tools",
                   "maintainability": "easy to maintain", "security": "security"}
EXISTING_SYSTEM_BONUS = 14.0
# Existing-system answers that are databases in the knowledge base (the rest are flagged as unknown).
KEPT_DATABASES = ("postgres", "mysql", "mongodb", "redis", "sqlserver")


class Weights:
    def __init__(self):
        self.parts: dict[str, list[tuple[str, float, str]]] = defaultdict(list)

    def add(self, crit: str, inp: str, amount: float, reason: str):
        self.parts[crit].append((inp, amount, reason))

    def total(self, crit: str) -> float:
        return max(0.0, sum(a for _, a, _ in self.parts.get(crit, [])))

    def share(self, crit: str) -> dict[str, float]:
        """Contribution of each input to this criterion's weight."""
        out: dict[str, float] = defaultdict(float)
        for inp, a, _ in self.parts.get(crit, []):
            out[inp] += a
        tot = sum(out.values())
        if tot <= 0:
            return {}
        return dict(out)

    def as_list(self) -> list[dict]:
        rows = []
        for crit, parts in self.parts.items():
            rows.append({
                "criterion": crit, "label": CRITERION_LABELS[crit], "weight": round(self.total(crit), 2),
                "drivers": [{"input": i, "input_label": INPUT_LABELS.get(i, i), "amount": round(a, 2), "reason": r}
                            for i, a, r in parts if abs(a) > 1e-9],
            })
        rows.sort(key=lambda r: -r["weight"])
        return rows


def build_weights(p: dict, d: dict) -> Weights:
    """Turn the project's inputs (budget, priorities, scale, compliance) into one weight per scoring criterion."""
    w = Weights()
    for c, v in BASELINE.items():
        if v:
            w.add(c, "baseline", v, "Default importance")

    b = d["budget_usd"]
    if b <= 0:
        w.add("cost", "budget_monthly", 4, "Zero budget: free tiers only")
    elif b < 50:
        w.add("cost", "budget_monthly", 3, f"Tight budget (~${b:,.0f}/month)")
    elif b < 300:
        w.add("cost", "budget_monthly", 1.5, f"Modest budget (~${b:,.0f}/month)")
    elif b < 2000:
        w.add("cost", "budget_monthly", 0.5, f"Moderate budget (~${b:,.0f}/month)")
    elif b >= 20000:
        w.add("cost", "budget_monthly", -0.5, f"Large budget (~${b:,.0f}/month): cost matters less")

    t = p["timeline_weeks"]
    if t <= 4:
        w.add("velocity", "timeline_weeks", 2, f"{t}-week MVP: speed dominates")
        w.add("ease", "timeline_weeks", 1.5, f"{t}-week MVP: no time to learn new tools")
    elif t <= 12:
        w.add("velocity", "timeline_weeks", 1, f"{t}-week MVP")
        w.add("ease", "timeline_weeks", 0.5, f"{t}-week MVP")
    elif t >= 40:
        w.add("maturity", "timeline_weeks", 0.5, "Long programme: favour long-term maturity")

    n = p["team_size"]
    if n == 1:
        w.add("ops", "team_size", 2.5, "Solo developer: every hour on ops is lost on product")
        w.add("ease", "team_size", 1, "Solo developer")
    elif n <= 3:
        w.add("ops", "team_size", 1.5, f"Small team ({n})")
        w.add("ease", "team_size", 0.5, f"Small team ({n})")
    elif n <= 10:
        w.add("ops", "team_size", 0.5, f"Team of {n}")
    if n >= 10:
        w.add("structure", "team_size", 1.5, f"{n} engineers need enforced conventions")
        w.add("hiring", "team_size", 1, f"{n} engineers: hiring pool matters")
    if n >= 30:
        w.add("structure", "team_size", 1, "Large organisation")
        w.add("hiring", "team_size", 0.5, "Large organisation")

    exp = p.get("team_experience", "intermediate")
    if exp == "beginner":
        w.add("ease", "team_experience", 1.5, "Beginner team: tools it can learn while building")
        w.add("ops", "team_experience", 1, "Beginner team: managed services instead of servers to run")
    elif exp == "mixed":
        w.add("ease", "team_experience", 0.5, "Mixed experience: juniors must pick the tools up quickly")
    elif exp == "senior":
        w.add("ease", "team_experience", -0.3, "Senior team: the learning curve matters less")
    if p.get("has_devops") is False:
        w.add("ops", "has_devops", 1, "Nobody on the team operates infrastructure: favour managed services")

    tier = d["compute_tier"]
    if tier == 0:
        w.add("scalability", "dau", -0.5, "Hobby scale: scalability barely matters")
    elif tier == 1:
        w.add("scalability", "dau", -0.3, "Small scale")
    elif tier == 2:
        w.add("scalability", "dau", 0.5, d["tier_label"])
    elif tier == 3:
        w.add("scalability", "dau", 1.5, d["tier_label"])
        w.add("performance", "dau", 0.5, d["tier_label"])
    else:
        w.add("scalability", "dau", 3, d["tier_label"])
        w.add("performance", "dau", 1, d["tier_label"])

    if p["realtime"] == "some":
        w.add("realtime", "realtime", 1, "Some realtime features")
    elif p["realtime"] == "core":
        w.add("realtime", "realtime", 3, "Realtime is core to the product")
        w.add("performance", "realtime", 0.5, "Realtime is core to the product")
        w.add("interactivity", "realtime", 1, "Realtime UIs update without page loads")

    if p["realtime"] != "none" and d.get("peak_concurrent", 0) >= 5000:
        w.add("realtime", "peak_concurrent", 1.5,
              f"{d['peak_concurrent']:,} users connected at once: every one holds an open connection")
    lat = p["latency_target_ms"]
    if lat <= 50:
        w.add("performance", "latency_target_ms", 2.5, f"p95 target {lat:.0f} ms")
    elif lat <= 150:
        w.add("performance", "latency_target_ms", 1.5, f"p95 target {lat:.0f} ms")
    elif lat <= 400:
        w.add("performance", "latency_target_ms", 0.5, f"p95 target {lat:.0f} ms")

    if p["seo"] == "important":
        w.add("seo", "seo", 2, "SEO important")
    elif p["seo"] == "critical":
        w.add("seo", "seo", 4, "SEO critical")

    if p["offline"]:
        w.add("offline", "offline", 3, "Offline support required")

    av = d["availability"]
    if av >= 99.99:
        w.add("maturity", "availability", 1, "99.99% target")
        w.add("scalability", "availability", 1, "99.99% target")
        w.add("ops", "availability", 0.5, "99.99% target")
    elif av >= 99.95:
        w.add("maturity", "availability", 0.5, "99.95% target")
        w.add("scalability", "availability", 0.5, "99.95% target")

    if p.get("tenancy") == "isolated":
        w.add("ops", "tenancy", 1, "A database or schema per customer: every migration and backup runs once per customer")
    if p["lock_in_tolerance"] == "low":
        w.add("portability", "lock_in_tolerance", 2, "Low lock-in tolerance")
    elif p["lock_in_tolerance"] == "high":
        w.add("portability", "lock_in_tolerance", -0.3, "High lock-in tolerance")
    if p["deployment"] == "hybrid":
        w.add("portability", "deployment", 1.5, "Hybrid deployment must stay portable")

    if not d["skills"]:
        # Nobody's skills are known yet, so the team is the people you can hire: the hiring pool takes
        # the weight that team-skill match would have had.
        w.add("hiring", "team_skills", 2.5, "No team skills listed: you will hire for this stack, so the hiring pool counts")
        if n >= 10:
            w.add("hiring", "team_size", 1, f"No team skills listed: {n} engineers to hire")
    if d["skills"]:
        w.add("skill_fit", "team_skills", 2.5, "Team has existing skills")
        if n >= 10:
            w.add("skill_fit", "team_size", 1, f"Retraining {n} engineers is expensive")
        if t <= 8:
            w.add("skill_fit", "timeline_weeks", 1, "Short timeline: familiarity matters more")

    if p["compliance"]:
        w.add("maturity", "compliance", 0.5, "Regulated workload")
    regulated = [c for c in REGULATED if c in p["compliance"]]
    if regulated:
        names = " + ".join({"hipaa": "HIPAA", "pci_dss": "PCI-DSS"}[c] for c in regulated)
        w.add("compliance_maturity", "compliance", 1.0,
              f"{names} data: the provider's audit logging, attestations and isolation options become your evidence")
        if tier >= 3:
            w.add("compliance_maturity", "dau", 1.5,
                  f"{names} at {d['tier_label']}: more records in scope and larger breach impact")
        if tier >= 4:
            w.add("compliance_maturity", "dau", 2.0,
                  f"{names} at {d['tier_label']}: auditors expect dedicated tenancy and immutable audit trails")

    app = p["app_type"]
    app_rules = {
        "content_site": [("seo", 1, "Content sites live on search"), ("performance", 1, "Core Web Vitals affect ranking")],
        "ecommerce": [("performance", 0.5, "Page speed affects conversion"), ("maturity", 0.5, "Payments/catalogue ecosystem"),
                      ("interactivity", 1, "Cart, filters and checkout flows")],
        "fintech": [("maturity", 1, "Financial systems favour proven tech"), ("consistency_fit", 2, "Ledgers need ACID")],
        "healthcare": [("maturity", 1, "Clinical systems favour proven tech"), ("consistency_fit", 1, "Health records need integrity")],
        "internal_tool": [("velocity", 1, "Internal tools are CRUD-heavy"), ("cost", 0.5, "Internal tools rarely justify spend")],
        "iot_telemetry": [("scalability", 1, "Continuous device ingestion"), ("interactivity", 1, "Live device dashboards")],
        "social_network": [("scalability", 0.5, "Viral growth"), ("realtime", 0.5, "Feeds and notifications"), ("interactivity", 1, "Feeds, media, interactions")],
        "ml_product": [("velocity", 0.5, "Fast iteration on models"), ("interactivity", 1, "Interactive AI UX (streaming, chat)"),
                       ("realtime", 0.5, "Streamed model output holds a connection open for each response")],
        "prototype": [("cost", 1.5, "Prototype: free tiers"), ("ease", 1.5, "Prototype: learnability"),
                      ("velocity", 1, "Prototype: ship fast"), ("maturity", -0.5, "Prototype: maturity matters less")],
        "realtime_collab": [("realtime", 1, "Collaboration/multiplayer"), ("interactivity", 1.5, "App-like realtime UI")],
        "saas": [("interactivity", 1, "App-like dashboards and forms")],
        "analytics_dashboard": [("performance", 1, "Interactive queries"), ("interactivity", 1.5, "Charts, filters, drill-downs")],
        "mobile_first": [("offline", 1, "Mobile users lose connectivity")],
    }
    for crit, amt, reason in app_rules.get(app, []):
        w.add(crit, "app_type", amt, reason)

    if p["read_write"] == "read_heavy":
        w.add("performance", "read_write", 0.3, "Read-heavy: fast reads/caching")
    elif p["read_write"] == "write_heavy":
        w.add("data_fit", "read_write", 1, "Write-heavy: the storage engine must match the workload")
    if strong_binds(p, d):
        w.add("consistency_fit", "consistency", 1.5, "Strong consistency required")
    if d["architecture"] == "serverless":
        w.add("ops", "architecture", 0.5, "Serverless preference")
    w.add("data_fit", "data_shapes", 0.0, "Primary data shape")
    w.add("region_fit", "regions", 0.0, "User regions")
    if p["latency_target_ms"] <= 150:
        w.add("region_fit", "latency_target_ms", 1.0, f"{p['latency_target_ms']:.0f} ms target: servers must sit near users")
    if p["realtime"] == "core":
        w.add("region_fit", "regions", 0.5, "Core realtime: every round trip is felt")
    if any(c in p["compliance"] for c in ("data_residency_india", "data_residency_eu")):
        w.add("region_fit", "compliance", 1.0, "Data residency: the region must exist")

    for rank, key in enumerate(p["priorities"][:3]):
        for crit, amt in PRIORITY_CRITERIA[key]:
            w.add(crit, "priorities", round(amt * PRIORITY_RANK_FACTOR[rank], 2),
                  f"Your priority #{rank + 1}: {PRIORITY_LABELS[key]}")
    return w


# --------------------------------------------------------------------------------------
# Computed criteria
# --------------------------------------------------------------------------------------

def static_site(p: dict) -> bool:
    """Users only read published content, so the site can be pre-built static files."""
    actions = set(p.get("user_actions") or [])
    return bool(actions) and actions <= {"read"}


def self_hosted_baas(item: dict, p: dict) -> bool:
    """A BaaS run from its open-source images on your own servers: no subscription, your ops."""
    return item.get("kind") == "baas" and p["deployment"] == "on_prem"


# Ops score of a self-hosted BaaS: Supabase's self-hosting guide runs about ten containers
# (Postgres, auth, REST, realtime, storage, gateway, studio ...) that the team upgrades and backs up.
SELF_HOSTED_BAAS_OPS = 2.0


def entry_plan(item: dict, tier: int, d: dict | None) -> dict | None:
    """The cheapest vendor entry plan (item field `entry_plans`: free and small fixed-price plans) that holds
    this project, or None. A plan holds it when the data expected within 12 months fits the plan's storage
    and the scale tier is one the plan's compute and quotas carry (`max_tier`). Data size is the 12-month
    figure, like every other sizing in the engine: a plan the project outgrows within the year does not count."""
    return min(entry_plans_holding(item, tier, d), key=lambda ep: (plan_price(ep, d), ep["usd"]), default=None)


def entry_plans_holding(item: dict, tier: int, d: dict | None) -> list[dict]:
    """Every entry plan of this item that holds the project (see entry_plan)."""
    if d is None:
        return []
    # A plan whose limit is a monthly compute allowance (`max_compute_tier`: Neon Free's compute-hours, the Azure SQL
    # free offer's vCore-seconds) is sized by daily users, not by the database tier that read-heavy caching lowers.
    return [ep for ep in item.get("entry_plans", ())
            if tier <= ep["max_tier"] and d["data_12mo_gb"] <= ep["max_data_gb"]
            and d["compute_tier"] <= ep.get("max_compute_tier", 5)]


def plan_price(ep: dict, d: dict) -> float:
    """Monthly price of an entry plan for this project: the plan's price plus storage beyond what it includes
    (optional fields `included_gb` and `usd_per_gb`, for plans that bill disk per GB), at the 12-month data size."""
    extra = max(0.0, d["data_12mo_gb"] - ep.get("included_gb", ep["max_data_gb"]))
    return float(round(ep["usd"] + extra * ep.get("usd_per_gb", 0.0), 2))


def tier_cost(item: dict, tier: int, p: dict, d: dict | None = None) -> tuple[float, float]:
    """Price band [low, high] in USD/month at a scale tier. With the derived profile `d`, the floor of an
    item with entry plans is the cheapest plan that holds the project (entry_plan) when the band's floor is $0 (a
    free plan) or dearer than that plan, and the top is then the dearest plan that holds it; when none does, a $0
    floor becomes the next tier's floor."""
    if self_hosted_baas(item, p):
        return 0.0, 0.0  # the servers are billed under hosting
    bands = item.get("cost_usd", [[0, 0]] * 6)
    lo, hi = bands[tier]
    if d is not None and "entry_plans" in item:  # an empty list: plans exist, but none is usable here (estimate_cost)
        ep = entry_plan(item, tier, d)
        if ep:
            # A $0 floor stands for a free plan: a free plan that holds the project keeps it, a paid one replaces
            # it unless the next tier's floor (a small managed instance) is cheaper. A paid floor stays when it is
            # cheaper than the plan.
            price = plan_price(ep, d)
            if lo == 0 and price > 0 and tier + 1 < len(bands):
                lo = min(price, bands[tier + 1][0])
            else:
                lo = price if lo == 0 else min(lo, price)
            if lo > 0:
                # The project is on a paid plan: the band's top is the dearest vendor plan that still holds
                # it, not the tier's generic top (sized for the largest data and traffic of the tier).
                hi = min(hi, max(plan_price(x, d) for x in entry_plans_holding(item, tier, d)))
        elif lo == 0 and tier + 1 < len(bands):
            lo = bands[tier + 1][0]
        hi = max(hi, lo)
    if item.get("static_cost_usd") and static_site(p):
        lo, hi = item["static_cost_usd"][tier]  # serves pre-built files only: the free static plan
    comp = item.get("compliance", {})
    if "hipaa" in p["compliance"] and comp.get("hipaa_min_usd"):
        lo, hi = max(lo, comp["hipaa_min_usd"]), max(hi, comp["hipaa_min_usd"])
    sso = item.get("sso")
    if p.get("enterprise_sso") and sso and sso.get("min_usd"):
        lo, hi = max(lo, sso["min_usd"]), max(hi, sso["min_usd"])  # SSO is sold only on this paid plan and above
    if "soc2" in p["compliance"] and comp.get("soc2_min_usd"):
        lo, hi = max(lo, comp["soc2_min_usd"]), max(hi, comp["soc2_min_usd"])
    if item.get("commercial_min_usd") and p["app_type"] != "prototype":
        lo, hi = max(lo, item["commercial_min_usd"]), max(hi, item["commercial_min_usd"])
    return lo, hi


def seat_cost(item: dict, lo: float, p: dict) -> float:
    """Paid plans that bill each deploying team member; the price band's floor covers one seat."""
    if item.get("seat_usd") and lo > 0 and p["team_size"] > 1:
        return (p["team_size"] - 1) * item["seat_usd"]
    return 0.0


# Share of requests that write, for per-operation pricing (Firestore bills reads and writes separately).
WRITE_SHARE = {"read_heavy": 0.1, "balanced": 0.3, "write_heavy": 0.7}


def usage_cost(item: dict, tier: int, p: dict, d: dict, per_op: bool = True) -> tuple[float, float]:
    """Price band plus usage terms for usage-billed services (a BaaS or Firestore): the plan is
    sized by the larger of traffic and stored data, disk beyond the plan's allowance is billed per
    GB, and per-operation pricing is estimated from requests a month (high = twice that, for
    fan-out reads). per_op=False leaves out the per-operation term, the only one that follows the
    exact user count rather than the scale and data tiers."""
    u = item.get("usage")
    if not u or self_hosted_baas(item, p):
        return tier_cost(item, tier, p, d)
    lo, hi = tier_cost(item, max(tier, d["data_tier"]), p, d)
    storage = max(0.0, d["data_12mo_gb"] - u.get("storage_included_gb", 0)) * u.get("storage_usd_per_gb", 0)
    ops = 0.0
    if per_op and u.get("doc_write_usd_per_100k"):
        w = WRITE_SHARE.get(p["read_write"], 0.3)
        per_100k = (1 - w) * u["doc_read_usd_per_100k"] + w * u["doc_write_usd_per_100k"]
        free = u.get("free_ops_per_day", 0) * 30  # daily free quota, counted once per month
        ops = max(0.0, p["dau"] * d["req_per_user_day"] * 30 - free) / 1e5 * per_100k
    return float(round(max(lo, ops) + storage)), float(round(max(hi, 2 * ops) + storage))


def net_cost(item: dict, tier: int, p: dict, d: dict) -> tuple[float, float]:
    """A BaaS replaces the database bill, so compare it net of the bundled database's cost. Scoring
    uses the price bands only: the usage terms of usage_cost() grow smoothly with users while the
    bands step, and mixing the two made picks flip back and forth as users grew. A usage-billed plan
    is still sized by stored data (the data tier does not move with users)."""
    if item.get("usage"):
        tier = max(tier, d["data_tier"])
    lo, hi = tier_cost(item, tier, p, d)
    bundled = item.get("bundled_database")
    if bundled:
        blo, bhi = tier_cost(load_kb()["index"][bundled], d["db_tier"], p, d)
        lo, hi = max(0.0, lo - blo), max(0.0, hi - bhi)
    return lo, hi


def skill_fit(item: dict, skills: set) -> float:
    """How well the team's listed skills cover this technology, 1 to 5 (3 when no skills were listed)."""
    if not skills:
        return 3.0
    own = _own_skill_fit(item, skills)
    if item.get("rendered_by_backend"):
        return max(own, view_layer_fit(frozenset(skills)))
    return own


# Skill fit of backend-rendered pages for a team that writes a backend framework with an interactive view layer:
# the fit of one skill the team lists directly. The HTMX attributes themselves are new, hence not the 5.0 of two.
VIEW_LAYER_SKILL_FIT = 4.5


@lru_cache(maxsize=256)
def view_layer_fit(skills: frozenset) -> float:
    """Pages rendered by the backend are written in the backend framework's own view layer (KB field view_layer).
    Where that layer has its own interactive components (Rails Hotwire, Laravel Livewire, Phoenix LiveView,
    ASP.NET Core Blazor: view_layer.interactive), it covers the client state a JavaScript frontend framework
    would, so a team that writes such a framework already knows how to build these pages. Plain templates
    (Django, Thymeleaf) still leave the interactive parts to JavaScript the team would learn, so they earn
    nothing here. It counts only when every server language the team lists has such a framework (a Ruby + Go
    team may write its backend in Go) and the team lists no web frontend framework (that team keeps it)."""
    kb = load_kb()
    if any(skills & set(fe.get("skills", [])) for fe in kb["frontend"]
           if fe.get("kind") == "web" and not fe.get("rendered_by_backend")):
        return 1.0
    servers = [b for b in kb["backend"] if b.get("kind") == "server"]
    known = [b for b in servers if skills & (set(b.get("skills", [])) - FRONTEND_LANGUAGES)]
    if not known or not all((b.get("view_layer") or {}).get("interactive") for b in known):
        return 1.0
    return min(VIEW_LAYER_SKILL_FIT, max(_own_skill_fit(b, set(skills)) for b in known))


def _own_skill_fit(item: dict, skills: set) -> float:
    hits = skills & set(item.get("skills", []))
    if len(hits) >= 2:
        return 5.0
    if hits:
        return 4.5
    related = skills & set(item.get("related_skills", []))
    if len(related) >= 2:
        return 4.0  # several adjacent skills transfer (e.g. JS + React for Astro, which hosts React components)
    if related:
        return 3.5
    return 1.5


HYPERSCALERS = ("aws", "gcp", "azure")


def cloud_skill_fit(item: dict, skills: set, base: float) -> float:
    """Hosting on a hyperscaler: the team's cloud skill (IAM, networking, billing, managed services)
    matters more than generic tool skills such as Docker. A team that lists a different hyperscaler
    and not this one is capped at 2.5 even if a generic skill matched."""
    prov = item.get("provider")
    team_clouds = skills & set(HYPERSCALERS)
    if prov in HYPERSCALERS and team_clouds:
        return max(base, 4.5) if prov in team_clouds else min(base, 2.5)
    return base


# Region fit when the user did not say where users are: the same middle score for every option, so no region is favoured.
REGION_FIT_UNKNOWN = 3.0


def region_fit(item: dict, regions: list) -> float:
    """How well the technology's hosting regions cover the regions the users are in, 1 to 5."""
    if not regions:
        return REGION_FIT_UNKNOWN
    have = set(item.get("regions", []))
    if "global" in regions:
        return 5.0 if "global" in have else 2.0
    got = 0.0
    for r in regions:
        if r in have:
            got += 1
        elif r == "india" and "southeast_asia" in have:
            got += 0.5  # Singapore is ~60 ms from Mumbai
    return 1 + 4 * got / max(1, len(regions))


def _without_shape(item: dict, d: dict) -> dict | None:
    """A store whose strengths come from one data shape (item field `without_shape`), when the project has
    none of that shape: the fit scores it has without it."""
    w = item.get("without_shape")
    if w and w["shape"] not in (d["primary_shape"], *d["secondary_shapes"]):
        return w
    return None


def shape_models(item: dict, d: dict) -> dict:
    """Fit (1-5) per data shape for this project: TimescaleDB is plain PostgreSQL for data that is not a time series."""
    w = _without_shape(item, d)
    return {**item["models"], **w["models"]} if w else item["models"]


def write_scale(item: dict, d: dict) -> float:
    """How well the database handles heavy writes, 1 to 5, ignoring any data shape served by a second store."""
    w = _without_shape(item, d)
    return w.get("write_scale", item.get("write_scale", 3)) if w else item.get("write_scale", 3)


# Fit counted for a shape that a specialist store beside the primary serves (served_beside): a good fit (GOOD_FIT),
# not a perfect one, since the data then lives in a second system the team runs and keeps in sync.
SERVED_BESIDE_FIT = 4


@lru_cache(maxsize=1024)
def _served_beside(shapes: tuple, compliance: tuple) -> frozenset:
    p, d = {"compliance": list(compliance)}, {"primary_shape": shapes[0], "secondary_shapes": list(shapes[1:])}
    out = set()
    for it in load_kb()["database"]:
        sor = it.get("system_of_record")
        if sor and specialist_reason(it, p, d):
            out |= {s for s in shapes if shape_models(it, d)[s] == 5}
    return frozenset(out)


def served_beside(p: dict, d: dict) -> frozenset:
    """Data shapes a specialist store kept out of the primary role (specialist_reason) still serves beside the
    primary (engine/advice.py supporting_services lists it): its specialty, the shape it fits 5/5 (the key-value
    data of an in-memory store, the graph of a graph store, the index of a search engine). The primary is chosen for the records, so its own fit for
    these shapes counts as SERVED_BESIDE_FIT at least."""
    return _served_beside((d["primary_shape"], *d["secondary_shapes"]), tuple(sorted(p.get("compliance") or ())))


def primary_models(item: dict, p: dict, d: dict) -> dict:
    """Fit per data shape of a store as the primary database: shape_models, with shapes served beside it raised."""
    m = shape_models(item, d)
    beside = served_beside(p, d)
    if not beside or item.get("system_of_record"):
        return m
    return {**m, **{s: max(m[s], SERVED_BESIDE_FIT) for s in beside}}


def data_fit(item: dict, p: dict, d: dict) -> float:
    """How well a database fits the project's data shapes, 1 to 5; the primary shape counts double."""
    m = primary_models(item, p, d)
    prim = m[d["primary_shape"]]
    sec = [m[s] for s in d["secondary_shapes"]]
    fit = (2 * prim + sum(sec)) / (2 + len(sec))
    if p["read_write"] == "write_heavy":
        fit = 0.7 * fit + 0.3 * write_scale(item, d)
    return fit


def compliance_maturity(layer: str, item: dict) -> float:
    """1-5: breadth of published attestations, native audit logging and dedicated-tenancy options.
    A self-hosted backend framework adds no data processor of its own (it inherits the host's controls),
    so it scores 5; a BaaS adds a second vendor in the regulated data path and carries its own score."""
    if layer == "backend" and item.get("kind") != "baas":
        return 5.0
    return float(item.get("compliance", {}).get("maturity", 3))


def consistency_fit(item: dict, p: dict) -> float:
    """How well the database's consistency model (strong, tunable, eventual) matches what was asked, 1 to 5."""
    c = item.get("consistency", "strong")
    if p["consistency"] == "strong":
        return {"strong": 5.0, "tunable": 3.5, "eventual": 1.0}[c]
    return {"strong": 4.0, "tunable": 4.5, "eventual": 4.5}[c]


# --------------------------------------------------------------------------------------
# Hard constraints
# --------------------------------------------------------------------------------------
# Each exclusion: (reason, constraint_key, relax_level). relax_level 0 = never relaxed,
# 1 = preference (relaxed first), 2 = capacity heuristic (relaxed last).

# Above this, an in-memory primary store means large-RAM nodes (plus replicas) holding data that a
# disk-based store keeps for a fraction of the price: excluded as a capacity heuristic, and the
# store is suggested as a cache instead.
MEMORY_PRIMARY_MAX_GB = 10
# ...unless the budget pays for that RAM: a managed in-memory node costs about $12 per GB of RAM a
# month (ElastiCache / Memorystore list prices), twice that with the replica a primary store needs.
# Inside the database's share of the budget, holding the data in RAM is a cost the project can carry.
RAM_USD_PER_GB_MONTH = 12.0
RAM_PRICE_SOURCE = "https://aws.amazon.com/elasticache/pricing/"


def ram_affordable(p: dict, d: dict) -> bool:
    """The 12-month data set fits in RAM (primary plus one replica) within the database's budget share."""
    return 2 * RAM_USD_PER_GB_MONTH * d["data_12mo_gb"] <= BUDGET_SHARE["database"] * d["budget_usd"]


# A single-writer store (SQLite: one write transaction at a time for the whole file) under core realtime,
# write-heavy traffic from 1k+ daily users: every message is a write and they queue on one lock. Sized
# between a 3/5 and a 2/5 data-shape fit (-6 and -10): the store fits the data but not the write load.
SINGLE_WRITER_REALTIME_PENALTY = 8
# SQLite's own guidance: "any site that gets fewer than 100K hits/day should work fine with SQLite ... SQLite has
# been demonstrated to work with 10 times that amount of traffic", and many writers at the same instant call for a
# client/server engine. A single-writer store loses up to SINGLE_WRITER_REALTIME_PENALTY points as the requests
# reaching the servers each day grow from 100k to 1M (log scale), and is excluded past 1M (a capacity heuristic,
# relaxed last like the scale ceiling). The count is taken at the floor of the scale tier
# (its smallest daily-user count), so every user count of one tier, and the growth path, sees the same penalty.
SINGLE_WRITER_HITS_OK = 100_000
SINGLE_WRITER_HITS_MAX = 1_000_000


def daily_hits_at_tier_floor(d: dict) -> float:
    """Requests a day that reach the servers at the smallest daily-user count of the scale tier."""
    users = DAU_THRESHOLDS[d["compute_tier"] - 1] if d["compute_tier"] > 0 else 0
    return users * d["req_per_user_day"] * d["origin_share"]
# Content kept as files in a git repository (pages, posts, small images): above this, clones and
# builds get slow and media belongs in object storage with a real content store.
STATIC_CONTENT_MAX_GB = 5


# Shapes that are read through an index or in bulk rather than updated in transactions: analytical data and
# a search index (full-text or log search).
DERIVED_SHAPES = ("analytical", "search")


# Lowest availability target a single-host option (KB flag single_host) cannot meet: from 99.95% the app is
# spread over two failure domains with automatic failover (engine/advice.py architecture()).
SINGLE_HOST_MAX_AVAILABILITY_EXCL = 99.95


def record_shapes(d: dict) -> list[str]:
    """The data shapes that make up a system of record. Strong consistency binds the store holding them;
    analytical data and a search index are read in bulk or through an index and are not updated in
    transactions, so a project whose only shapes are these has no record to protect (a mix with relational
    data keeps it, and these parts go to a supporting store, see advice.analytics_only_excluded)."""
    return [s for s in (d["primary_shape"], *d["secondary_shapes"]) if s not in DERIVED_SHAPES]


def specialist_reason(item: dict, p: dict, d: dict) -> str | None:
    """A specialist store (KB field system_of_record: an in-memory store, a graph store, a search index) is the
    system of record only for the data shapes listed there. When the project has a record shape outside that list
    (record_shapes: every shape but analytical and search), those records need a durable general-purpose store,
    which is then the primary, and the specialist serves its own shape beside it (engine/advice.py
    supporting_services). A store marked regulated: false (in-memory, losing the last writes on a crash) is not the
    system of record for HIPAA or PCI DSS data at all. Returns the exclusion reason, or None."""
    sor = item.get("system_of_record")
    if not sor:
        return None
    if sor.get("regulated") is False:
        reg = [{"hipaa": "HIPAA", "pci_dss": "PCI DSS"}[c] for c in REGULATED if c in p["compliance"]]
        if reg:
            return f"{sor['why']}: not the system of record for {' + '.join(reg)} data (use it beside a durable store)"
    other = [s for s in record_shapes(d) if s not in sor["shapes"]]
    if other:
        return (f"{sor['why']}: your {', '.join(s.replace('_', ' ') for s in other)} data needs a durable general-purpose "
                f"primary store, with {item['name']} beside it as a supporting store")
    return None


def strong_binds(p: dict, d: dict) -> bool:
    """Strong consistency binds the primary store. A project whose main data is analytical (or a search index) and
    that does not answer the consistency question may keep that data in a store built for it, the record shapes
    going to a secondary store (engine/advice.py supporting_services): the default 'strong' is then a planning
    assumption and does not exclude or outweigh such a store. The main data shape counts when the user stated it
    or when the app type sets it (an analytics dashboard aggregates event tables, profile.APP_DEFAULTS): a generic
    default shape is only a blank answer and does not lift the requirement."""
    shape_known = "data_shapes" not in d["defaulted"] or "data_shapes" in d.get("app_defaulted", ())
    return p["consistency"] == "strong" and not (
        "consistency" in d["defaulted"] and shape_known and d["primary_shape"] in DERIVED_SHAPES)


def hard_constraints(layer: str, item: dict, p: dict, d: dict) -> list[tuple[str, str, int]]:
    """List the reasons this technology is ruled out for the project: (reason, input, severity) tuples."""
    out = []
    comp = item.get("compliance", {})
    kind = item.get("kind")
    if layer == "frontend":
        if d.get("api_only") or kind == "none":
            if d.get("api_only") != (kind == "none"):
                out.append(("API only: there is no user interface to build" if d.get("api_only") else
                            "You target a user interface, so a frontend is needed", "platforms", 0))
            return out
        if bool(d.get("desktop_only")) != (kind == "desktop"):
            out.append(("Not a desktop toolkit; you target desktop only" if d.get("desktop_only") else
                        "Desktop toolkit; desktop is not your only client, so one is suggested beside the main frontend"
                        if "desktop" in p["platforms"] else "Desktop toolkit; you do not target desktop", "platforms", 0))
            return out
        if d.get("desktop_only"):
            return out
        if d.get("one_codebase"):
            missing = [x for x in d["one_codebase"] if x not in item.get("platforms", [])]
            if missing:
                out.append((f"Does not build {', '.join(missing)}: the timeline leaves room for one codebase that "
                            "builds every platform", "platforms", 0))
            return out
        if not d["web"] and kind != "mobile":
            out.append(("Web-only framework; you target iOS/Android only", "platforms", 0))
        # A mobile-first app is built around the store app, so a mobile toolkit may be its primary frontend
        # even when web is also a target (the web app is then the companion); otherwise the web framework leads.
        if d["web"] and kind == "mobile" and p["app_type"] != "mobile_first":
            out.append(("Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)", "platforms", 0))
        return out

    if item.get("static_only"):
        if not d["read_only"]:
            out.append(("Only for read-only sites; your users sign in, post or pay", "user_actions", 0))
        elif p["realtime"] == "core":
            out.append(("Static files cannot hold live connections; realtime is core", "realtime", 0))
        elif layer == "database" and d["data_12mo_gb"] > STATIC_CONTENT_MAX_GB:
            out.append((f"~{d['data_12mo_gb']:,.0f} GB within 12 months is too much to keep as files in git "
                        f"(over ~{STATIC_CONTENT_MAX_GB} GB)", "data_volume_gb", 0))
    required = p.get("cloud_required") or p["cloud_preference"] == "no_hyperscaler"  # ruling clouds out is always a rule
    if required and p["cloud_preference"] != "none" and p["deployment"] != "on_prem":
        pref = p["cloud_preference"]
        where = item.get("provider") if layer == "hosting" else item.get("cloud")
        if layer == "backend" and kind == "baas":
            where = item.get("cloud") or item["id"]
        if (layer == "hosting" or where) and (where in HYPERSCALERS if pref == "no_hyperscaler" else where != pref):
            out.append(("Runs on AWS, Google Cloud or Azure, which you ruled out" if pref == "no_hyperscaler" else
                        f"Not on {CLOUD_NAMES[pref]}, the cloud you require", "cloud_preference", 0))
    if p.get("self_managed") and p["deployment"] == "cloud":
        if layer == "hosting" and kind != "vps":
            out.append(("A managed platform; you run your own VMs", "self_managed", 0))
        if layer == "backend" and kind in ("baas", "faas") and not item.get("self_hostable"):
            out.append(("Managed-only platform; it cannot run on VMs you operate", "self_managed", 0))
        if layer == "database" and item.get("managed_only"):
            out.append(("Managed-only cloud database; it cannot run on VMs you operate", "self_managed", 0))
    elif layer == "hosting" and item.get("vm"):
        out.append(("Plain VMs your team patches and operates; offered when you choose self-managed VMs", "self_managed", 0))
    if p["deployment"] == "on_prem":
        if layer == "hosting" and not item.get("on_prem"):
            out.append(("Public-cloud service; deployment must be on-premises", "deployment", 0))
        if layer == "backend" and kind == "baas" and not item.get("self_hostable"):
            out.append(("Managed-only BaaS cannot run on-premises", "deployment", 0))
        if layer == "backend" and kind == "faas":
            out.append(("Needs a managed function platform, unavailable on-premises", "deployment", 0))
        if layer == "database" and item.get("managed_only"):
            out.append(("Managed-only cloud database cannot run on-premises", "deployment", 0))
    elif p["deployment"] == "cloud" and layer == "hosting" and kind == "onprem":
        out.append(("On-premises option; you chose public cloud", "deployment", 0))
    if layer == "hosting" and item.get("single_host") and d["availability"] >= SINGLE_HOST_MAX_AVAILABILITY_EXCL:
        # 99.95% spreads the app over two failure domains with automatic failover between them (architecture()
        # in engine/advice.py); a tool that runs and restarts containers on one host cannot move them to another
        # when that host fails. 99.9% can still be met by hand (two hosts behind a load balancer).
        out.append((f"{item['single_host_note']}: no automatic failover to a second host, so it cannot meet "
                    f"{d['availability']:g}% availability", "availability", 0))

    if layer == "hosting" and d.get("workers") and not item.get("runs", {}).get("long_running"):
        # Request-scoped functions stop when the response is sent (or at a fixed timeout) and static files run
        # no code, so long-running workers need a host with always-on processes or containers.
        field, why = d["workers"][0]
        out.append((f"Runs code only as short request-scoped functions or static files; {why}", field, 0))
    if layer == "hosting" and d.get("gpu") and not item.get("runs", {}).get("gpu"):
        out.append(("No GPU machines on this host; GPU work needs one", "background_work", 0))
    sla = item.get("sla") if layer == "hosting" else None
    stated_avail = "availability" not in d["defaulted"]
    if stated_avail and sla and sla["percent"] < d["availability"]:
        # The provider's own service-level agreement is the uptime it commits to: a target above it rests on the
        # app alone (the same reason the single-host rule above excludes hosts without failover).
        out.append((f"The provider's SLA is {sla['percent']:g}% ({sla['scope']}), below your {d['availability']:g}% "
                    "availability target", "availability", 2))

    applies_comp = layer == "hosting" or (layer == "backend" and kind == "baas") or \
        (layer == "database" and item.get("managed_only"))
    if applies_comp:
        if "hipaa" in p["compliance"] and not comp.get("hipaa"):
            out.append(("No HIPAA Business Associate Agreement available", "compliance", 0))
        if "pci_dss" in p["compliance"] and layer == "hosting" and not comp.get("pci"):
            out.append(("No PCI-DSS attestation published", "compliance", 0))
        if "soc2" in p["compliance"] and not comp.get("soc2", True):
            out.append(("No SOC 2 report available", "compliance", 0))
        if "iso27001" in p["compliance"] and not comp.get("iso27001"):
            out.append(("No ISO/IEC 27001 certification published", "compliance", 0))
        regions = item.get("residency_regions", item.get("regions"))
        note = item.get("residency_note")
        if layer == "hosting" and "static_regions" in item and static_site(p) and d["data_12mo_gb"] <= STATIC_CONTENT_MAX_GB:
            # A static site's data is its files and their logs: where the host stores those, not where functions run.
            regions, note = item["static_regions"], item.get("static_residency_note")
        if regions is not None:
            for rule, region in RESIDENCY_RULES.items():
                if rule in p["compliance"] and region not in regions:
                    out.append((note or RESIDENCY_TEXT[rule], "compliance", 0))
    if (stated_avail and layer == "hosting" and kind != "onprem" and not sla and d["availability"] > 99.9
            and d["budget_usd"] > 0):
        # No published SLA commits to nothing, so a target above 99.9% fails it as surely as a lower SLA does.
        # Own hardware has no provider to publish one, and a zero budget keeps the target a goal (FREE_TIER_NO_SLA).
        # Listed after the rules that are never relaxed, so those are named first.
        out.append((f"No published SLA, so nothing backs your {d['availability']:g}% availability target",
                    "availability", 2))

    if layer == "database":
        if strong_binds(p, d) and item.get("consistency") == "eventual" and record_shapes(d):
            out.append(("Eventually consistent; cannot be the system of record for ACID data", "consistency", 0))
        prim = primary_models(item, p, d)[d["primary_shape"]]
        if (data_fit(item, p, d) < 2.0 or prim <= 1) and "data_shapes" not in d["defaulted"]:
            # A shape the user stated binds. A defaulted one (generic or app-type default) is a planning
            # assumption: it only lowers the score (the primary-shape and fit-gap adjustments below), so an
            # unanswered question does not remove the store a stated skill or budget points to.
            out.append((f"Poor fit for '{d['primary_shape']}' data as the primary store ({prim}/5)", "data_shapes", 0))
        elif p["read_write"] == "write_heavy" and d["db_tier"] >= 3 and (prim <= 2 or write_scale(item, d) <= 2):
            out.append((f"Write-heavy load at {d['db_tier_label']} on a store that fits '{d['primary_shape']}' data "
                        f"{prim}/5 with write scaling {write_scale(item, d):g}/5", "read_write", 2))
        if item.get("single_node") and (d["availability"] >= 99.95 or (
                d["availability"] >= 99.9 and "availability" not in d["defaulted"])):
            # A stated 99.9% target needs a second app instance or a standby (the cost model prices one, see
            # engine/advice.py AVAILABILITY_MULT), at any user count; a local file cannot be shared with a second
            # instance and has no failover, wherever it runs. The default 99.9% is a planning assumption and only
            # lowers the score.
            out.append((f"Single-node file database: no failover, so it cannot meet {d['availability']:g}% availability",
                        "availability", 0))
        if item.get("single_writer") and p["offline"]:
            # Offline clients queue their changes and upload them together when they reconnect, many devices at
            # once, into the one server copy they all sync with. SQLite's own guide: many clients sending SQL to
            # the same database over a network, or many concurrent writers, call for a client/server engine. The
            # file database belongs on the device (the offline sync service puts it there), not on the server.
            out.append(("One writer at a time for the whole file: offline devices upload their queued changes "
                        "together when they reconnect, so the server copy they all sync with needs a client/server "
                        "database (SQLite stays on the device as the local copy)", "offline", 0))
        if item.get("single_writer") and daily_hits_at_tier_floor(d) > SINGLE_WRITER_HITS_MAX:
            out.append((f"One writer at a time for the whole file: {daily_hits_at_tier_floor(d) / 1e6:,.1f}M+ requests a day at "
                        f"{d['tier_label']} is past the 1M a day SQLite's own guide says it has been shown to handle",
                        "dau", 2))
        if item.get("memory_bound") and d["data_12mo_gb"] > MEMORY_PRIMARY_MAX_GB and not ram_affordable(p, d):
            out.append((f"In-memory store: ~{d['data_12mo_gb']:,.0f} GB within 12 months cannot sensibly live in RAM "
                        "as the system of record (use it as a cache)", "data_volume_gb", 2))
        why = specialist_reason(item, p, d)
        if why:
            out.append((why, "data_shapes", 0))

    need = d["db_tier"] if layer == "database" else d["compute_tier"]
    if need - item.get("scale_ceiling", 5) >= 2:
        out.append((f"Scale ceiling far below {d['tier_label' if layer != 'database' else 'db_tier_label']}", "dau", 2))

    if p["lock_in_tolerance"] == "low" and item.get("lock_in", 1) >= 5:
        out.append(("Proprietary API with the highest lock-in; you asked for low lock-in", "lock_in_tolerance", 1))
    return out


# --------------------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------------------

def known_skills(item: dict, d: dict) -> set:
    """Skills the team listed that are direct skills of this technology (it already ships with it)."""
    return d["skills"] & set(item.get("skills", []))


# Skill fit of a layer that needs no code or system of its own (static_only: no server code, content files
# instead of a database), equal to a skill the team lists directly (engine/stack.py KNOWN_SKILL_FIT).
STATIC_SKILL_FIT = 4.5
# A BaaS is its own programming model (row-level security, client SDKs, vendor auth): knowing SQL or
# React transfers only partly, so adjacent skills alone give at most a neutral fit.
BAAS_RELATED_SKILL_CAP = 3.0
# A team that already writes server code in a language (PHP, Python, Java ...) would put that skill
# aside to adopt a BaaS it does not know: the fit is below neutral, between neutral (3) and unknown (1.5).
BAAS_SERVER_TEAM_SKILL_CAP = 2.0


def server_skills(d: dict) -> set:
    """Skills the team listed that belong to a server framework in the knowledge base (JavaScript and
    TypeScript alone do not count: almost every web team lists them for its frontend)."""
    own = set()
    for it in load_kb()["backend"]:
        if it.get("kind") == "server":
            own |= set(it.get("skills", []))
    return (d["skills"] & own) - FRONTEND_LANGUAGES - mobile_app_languages(frozenset(d["skills"]))


@lru_cache(maxsize=256)
def mobile_app_languages(skills: frozenset) -> frozenset:
    """Server-capable languages the team lists as part of a native mobile toolkit it lists in full (Kotlin with
    Swift: the Android and iOS apps, https://developer.android.com/kotlin). They show the team builds the mobile
    apps, not that it already ships a server framework written in them (Spring Boot for Kotlin): a team that
    lists another server language writes its server code in that one, and a team that lists none is a mobile
    team with no server code yet. A server framework skill the team lists by name (Spring) still counts."""
    kb = load_kb()
    own = set()
    for it in kb["backend"]:
        if it.get("kind") == "server":
            own |= set(it.get("skills", []))
    langs = set()
    for fe in kb["frontend"]:
        tool = set(fe.get("skills", []))
        if fe.get("kind") == "mobile" and tool <= skills:
            langs |= (tool & own) - FRONTEND_LANGUAGES
    return frozenset(langs)


@lru_cache(maxsize=256)
def no_server_language(skills: frozenset) -> bool:
    """The listed skills match no server framework, not even through an adjacent skill (TypeScript counts
    for Node.js): every server backend would be a new language for the team."""
    return all(skill_fit(it, set(skills)) <= UNFAMILIAR_SKILL_FIT for it in load_kb()["backend"] if it.get("kind") == "server")


@lru_cache(maxsize=256)
def no_frontend_skill(skills: frozenset) -> bool:
    """The team lists no web frontend framework: none by name, none through an adjacent framework skill (Django for
    server-rendered pages), and no backend framework with an interactive view layer (view_layer_fit). JavaScript or
    TypeScript alone do not count: they carry over to every JavaScript framework alike, so they do not say which
    one the team knows. Every web frontend is then new to the team, which will hire or learn for it, and the
    frontend's hiring pool counts (a Python team, a TypeScript backend team)."""
    if view_layer_fit(skills) > 1.0:
        return False
    for it in load_kb()["frontend"]:
        if it.get("kind") == "web" and (skills & set(it.get("skills", []))
                                         or skills & (set(it.get("related_skills", [])) - FRONTEND_LANGUAGES)):
            return False
    return True


def raw_scores(layer: str, item: dict, p: dict, d: dict, cost_scores: dict) -> dict[str, float]:
    """Score one technology 1 to 5 on every criterion its layer uses, before weighting."""
    s = {}
    known = known_skills(item, d)
    for c in LAYER_CRITERIA[layer]:
        if c == "cost":
            s[c] = cost_scores.get(item["id"], 3.0)
        elif c == "ease" and known:
            s[c] = 5.0  # no learning curve for a tool the team already uses
        elif c == "skill_fit":
            s[c] = skill_fit(item, d["skills"])
            if item.get("static_only") and layer in ("backend", "database") and d["skills"]:
                # No server code and no database to run (content files built into pages): nothing on this
                # layer for the team to learn, whatever it lists. The frontend framework that builds the
                # pages is scored on its own layer.
                s[c] = max(s[c], STATIC_SKILL_FIT)
            if item.get("kind") == "baas" and d["skills"] and not known:
                cap = BAAS_SERVER_TEAM_SKILL_CAP if server_skills(d) else BAAS_RELATED_SKILL_CAP
                s[c] = min(s[c], cap)
            if layer == "hosting":
                s[c] = cloud_skill_fit(item, d["skills"], s[c])
        elif c == "ops" and self_hosted_baas(item, p):
            s[c] = SELF_HOSTED_BAAS_OPS
        elif c == "portability":
            s[c] = 6 - item.get("lock_in", 1)
        elif c == "region_fit":
            s[c] = region_fit(item, p["regions"])
        elif c == "data_fit":
            s[c] = data_fit(item, p, d)
        elif c == "consistency_fit":
            s[c] = consistency_fit(item, p)
        elif c == "compliance_maturity":
            s[c] = compliance_maturity(layer, item)
        else:
            s[c] = float(item["scores"][c])
    return s


# What the people using the product see and touch: search visibility, how app-like the screens are, and
# offline use. Only these criteria, scored on the frontend (the layer that delivers them), count in the
# "most important inputs" tie-break of engine/stack.py: the other criteria (cost, scale, ops, maturity ...)
# are already weighed by every layer's score and by the earlier tie-breakers, and counting them again would
# let a near-tie move the backend, hosting or the database.
CAPABILITY_CRITERIA = ("seo", "interactivity", "offline")


def input_importance(w: Weights) -> list[str]:
    """The answers that put the most weight on CAPABILITY_CRITERIA (baseline excluded), heaviest first,
    ties by name. Cached on w."""
    order = getattr(w, "_importance", None)
    if order is None:
        total: dict[str, float] = defaultdict(float)
        for crit in CAPABILITY_CRITERIA:
            for inp, amt, _ in w.parts.get(crit, []):
                if inp != "baseline" and amt > 0:
                    total[inp] += amt
        order = w._importance = sorted(total, key=lambda i: (-total[i], i))
    return order


def input_points(scored: dict) -> dict[str, float]:
    """Layer points each answer gives this option through the CAPABILITY_CRITERIA weights (the same split
    as `contributions`), worked out from the raw scores so it exists for the light scoring the growth
    path uses too. Cached on the scored option."""
    pts = scored.get("_ip")
    if pts is None:
        w, totals, W, layer = scored["_ctx"]
        pts = defaultdict(float)
        for crit, wc in totals:
            if layer == "frontend" and crit in CAPABILITY_CRITERIA:
                norm = (scored["raw"][crit] - 1) / 4 * 100
                for inp, amt in w.share(crit).items():
                    pts[inp] += amt * norm / W
        scored["_ip"] = pts
    return pts


def layer_cost_scores(layer: str, items: list[dict], p: dict, d: dict) -> dict[str, float]:
    """Cost criterion on an absolute scale anchored to this layer's share of the budget:

        score = 5 - 4 * x / (1 + x),   x = ln(1 + mid_monthly_cost / (layer_share * budget))

    $0 scores 5; a bill equal to the layer's budget share scores ~3.4; 10x that share ~2.2; the
    score keeps falling smoothly and never reaches 1. An option's score depends only on its own
    bill, not on which other options happen to be feasible at this scale, so it moves smoothly and
    monotonically as users grow (a min-max scale would stretch a $0-vs-$25 gap to the full 1-5 range
    at one tier and shrink it at the next, which made picks flip back and forth)."""
    if layer == "frontend":
        return {}
    tier = d["db_tier"] if layer == "database" else d["compute_tier"]
    ref = BUDGET_SHARE[layer] * max(d["budget_usd"], MIN_BUDGET_REF_USD)
    out = {}
    for it in items:
        x = math.log1p(sum(net_cost(it, tier, p, d)) / 2 / ref)
        out[it["id"]] = 5 - 4 * min(1.0, x / math.log1p(COST_FLOOR_MULTIPLE))
    return out


# Share of the monthly budget one layer may reasonably take (cost criterion and budget adjustment).
BUDGET_SHARE = {"backend": 0.6, "hosting": 0.6, "database": 0.4}
ZERO_BUDGET_PAID_HOST = 6.0  # layer points: a host with no free plan at all, against a usable free plan, on a $0 budget
MIN_BUDGET_REF_USD = 10.0  # reference for a zero budget: ~$10/month already counts as expensive
OVER_BUDGET_SLOPE = 6.0    # points lost per e-fold of spend above the layer's budget share
COST_FLOOR_MULTIPLE = 30.0  # cost score reaches 1 at 30x the layer budget share
# Backend in the team's own language/framework: no rewrite of existing code, hiring or review
# habits. Large enough to beat a stack-level bundle bonus (+8 layer points = +2 stack points).
TEAM_SHIPS_BONUS = 6
# A server language that matches none of the listed skills (skill_fit() of 1.5, not even an adjacent
# skill): 8 layer points, the same size as missing platform skills (one team-week of ramp-up). It
# only decides when a stack on a language or BaaS the team knows is within 2 stack points.
UNFAMILIAR_SKILL_FIT = 1.5
UNFAMILIAR_BACKEND_PENALTY = 8
# A team whose skills match no server language, not even adjacently (a Flutter + Firebase team, say), learns or hires for
# whichever backend it picks, so the backend's hiring pool counts, as it does when no skills are listed at all
# (build_weights gives hiring 2.5 weight then, about 5 layer points between a 1/5 and a 5/5 pool): HIRING_LEVEL_POINTS
# per level of the 1-5 hiring score away from the middle (3).
HIRING_LEVEL_POINTS = 2.5
# Almost every web team lists these for its frontend; on their own they do not show the team runs a
# Node backend (it would list node, express or nestjs), so they do not earn the bonus above.
FRONTEND_LANGUAGES = {"javascript", "typescript"}
# App types whose UI is mostly client-side state (live collaboration, drill-down charts, feeds).
RICH_UI_APPS = ("realtime_collab", "analytics_dashboard", "social_network")
# A stated cloud preference is a strong preference, not a hard filter (data/questions.json): +12
# layer points to hosting on that cloud, enough to beat a bundle bonus but not a hard constraint
# or a large cost gap. Below a $50 budget it shrinks (to a quarter at $0), since a hyperscaler's
# paid minimums would push a free-tier project over budget.
CLOUD_PREF_BONUS = 12.0
CLOUD_PREF_FULL_BUDGET_USD = 50.0


# A latency target this strict (the tightest band of build_weights) leaves no room for a cold start.
STRICT_LATENCY_MS = 50
# From this compute tier up (Large, 100k-1M DAU) traffic is steady enough that per-request functions
# cost more than always-on instances (engine/advice.py API_HOST_MIN_TIER uses the same tier).
STEADY_TRAFFIC_TIER = 3
# Data-residency answers and the region each one needs.
RESIDENCY_RULES = {"data_residency_india": "india", "data_residency_eu": "europe", "data_residency_us": "north_america"}
RESIDENCY_TEXT = {"data_residency_india": "No India region; data must stay in India",
                  "data_residency_eu": "No EU region; data must stay in the EU",
                  "data_residency_us": "No US region; data must stay in the US"}
CLOUD_NAMES = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure"}
# A service that can keep the data in the region but needs extra work to do so (for example a part
# that runs only in the US and must be kept free of personal data): one team-week of work and a
# design constraint, the same size as missing platform skills.
RESIDENCY_CAVEAT_PENALTY = 8
# Points lost in `adjustments` (the final per-technology bonuses and penalties); each is a judgement call, not measured.
SCALE_CEILING_PENALTY = 12  # one tier past its practical ceiling: it works, but needs sharding or a rewrite soon
PLATFORM_SKILLS_PENALTY = 8  # Kubernetes or a bare VM with nobody on the team who has operated one
NO_PERSISTENT_CONNECTION_PENALTY = 8  # core realtime on a host that cannot hold open sockets
BAAS_REALTIME_LATENCY_PENALTY = 8  # core realtime under 100 ms: the BaaS adds a database round trip per message
KUBERNETES_PROTOTYPE_PENALTY = 8  # a cluster's setup cost outweighs any benefit for a throwaway prototype


def cloud_pref_bonus(budget_usd: float) -> float:
    """Points for matching the preferred cloud; smaller for tiny budgets, which can use any cloud's free tier."""
    if budget_usd >= CLOUD_PREF_FULL_BUDGET_USD:
        return CLOUD_PREF_BONUS
    return round(CLOUD_PREF_BONUS * max(0.25, budget_usd / CLOUD_PREF_FULL_BUDGET_USD), 1)


# Data-shape gate: how a database fits the project's data shapes (primary shape counted double, see
# data_fit) is compared with the best fit among the databases that pass the hard constraints. When one
# of them fits well (GOOD_FIT, 4/5) and this store does not, it loses FIT_GAP_MAX points once the gap
# is FIT_GAP_TOLERANCE + FIT_GAP_RAMP fit points (a linear ramp in between, so no cliff). That is more
# than the other criteria usually separate two stores by (scale, skills and price together), so a store
# that fits the data clearly worse than another option (a document store for a time-series +
# analytical workload) loses to it. Stores that fit well too (4/5 against 5/5) are not separated by it.
GOOD_FIT = 4.0
FIT_GAP_TOLERANCE = 0.75
FIT_GAP_RAMP = 0.25
FIT_GAP_MAX = 14
# A store that fits a stated secondary record shape 2/5 or worse when another option holds every record shape at 3/5 or
# better: those records need a second database. The same size as a 2/5 fit for the primary shape (adjustments()).
SECOND_STORE_PENALTY = 10
# A server-rendering framework (KB field server_rendering) when the user needs no search visibility: its rendering
# server and server/client component split buy crawlable HTML nobody asked for, while its client-rendered
# counterpart ships the same components as static files (https://web.dev/articles/rendering-on-the-web). One
# team-week of setup and operation, the engine's usual size for work with no product benefit (8 layer points =
# 2 stack points), so the choice follows the SEO answer rather than a lock-in or hiring-pool tie-break.
SSR_WITHOUT_SEO_PENALTY = 8


# Layer points for a database that does (or does not) enforce tenant isolation itself when customers share one database:
# about one team-week of writing and testing the tenant filter in every query, the engine's usual size for work with no
# product benefit (see SSR_WITHOUT_SEO_PENALTY).
TENANT_ISOLATION_POINTS = 4
# Layer points against a backend that needs a separately run identity broker for enterprise SSO: one more system to
# operate, smaller than a tenant-isolation gap because the broker is off-the-shelf.
SSO_BROKER_POINTS = 3


def adjustments(layer: str, item: dict, p: dict, d: dict, best_fit: tuple | None = None,
                free_host: str | None = None) -> list[dict]:
    """Score adjustments that do not fit a weighted criterion. `best_fit` (database layer only) is
    (data_fit, name) of the best-fitting database that passes the hard constraints, then the name of the
    best-fitting one that fits every record shape at least 3/5 (None if none does)."""
    adj = []

    def a(delta, inp, reason):
        adj.append({"delta": delta, "input": inp, "reason": reason})

    kind = item.get("kind")
    sc = item.get("scores", {})
    need = d["db_tier"] if layer == "database" else d["compute_tier"]
    if layer != "frontend" and need - item.get("scale_ceiling", 5) == 1:
        a(-SCALE_CEILING_PENALTY, "dau",
          "Near its practical scale ceiling at your traffic/data size (needs sharding or re-architecture)")
    tm = item.get("team_min", 1)
    if p["team_size"] < tm:
        a(-min(18, 6 * (tm - p["team_size"])), "team_size", f"Usually needs a team of {tm}+ to operate")
    # A platform the team must operate (a Kubernetes cluster, a bare VM) needs the operating skill itself: an
    # account on the cloud that sells it (AWS for EKS, GCP for GKE) does not teach node upgrades, add-ons or networking.
    if item.get("needs_platform_skills") and not (d["skills"] & (set(item.get("skills", [])) - set(HYPERSCALERS))):
        a(-PLATFORM_SKILLS_PENALTY, "team_skills", "Requires platform/DevOps skills your team did not list")
    shipped = known_skills(item, d) - FRONTEND_LANGUAGES - mobile_app_languages(frozenset(d["skills"]))
    if layer == "backend" and shipped:
        a(TEAM_SHIPS_BONUS, "team_skills",
          f"Your team already ships {item['name']} ({', '.join(sorted(shipped))} listed in team skills)")

    resid = [r for c, r in RESIDENCY_RULES.items() if c in p["compliance"]]
    if resid and item.get("residency_caveat") and all(r in item.get("residency_regions", item.get("regions", [])) for r in resid):
        a(-RESIDENCY_CAVEAT_PENALTY, "compliance", item["residency_caveat"])

    if layer == "backend" and kind == "server" and d["skills"] and skill_fit(item, d["skills"]) <= UNFAMILIAR_SKILL_FIT:
        # The team listed what it knows and neither this language nor anything adjacent to it is on the
        # list: every engineer learns a new server language (and its libraries) while building the product.
        a(-UNFAMILIAR_BACKEND_PENALTY, "team_skills",
          f"Nobody on the team listed {item['name'].split(' + ')[0]} or a closely related skill: a new server language to learn")
    if layer == "frontend" and kind == "desktop" and d["skills"] and skill_fit(item, d["skills"]) <= UNFAMILIAR_SKILL_FIT:
        # A desktop app is the whole client in the toolkit's language, so an unknown one costs like a backend's.
        a(-UNFAMILIAR_BACKEND_PENALTY, "team_skills",
          f"Nobody on the team listed {item['name'].split(' (')[-1].rstrip(')')} or a closely related skill: the "
          "whole desktop app is in a new language")

    if (
        layer == "backend"
        and kind == "server"
        and d["skills"]
        and no_server_language(frozenset(d["skills"]))
        and item["scores"]["hiring"] != 3
    ):
        a(HIRING_LEVEL_POINTS * (item["scores"]["hiring"] - 3), "team_skills",
          f"Your team lists no server language, so it will hire or learn for this backend: hiring pool "
          f"{item['scores']['hiring']}/5")

    langs = item.get("platform_languages")
    if layer == "frontend" and langs and d["skills"]:
        # Native apps are one codebase per platform, each in its own language; a cross-platform toolkit is one. A team
        # that lists neither platform language learns two languages for native against one for a cross-platform
        # toolkit: the second is a new language like an unfamiliar backend's.
        new = sorted({langs[pl] for pl in ("ios", "android") if pl in p["platforms"]} - d["skills"])
        if len(new) >= 2:
            a(-UNFAMILIAR_BACKEND_PENALTY * (len(new) - 1), "team_skills",
              f"{langs['why']}: nobody on the team listed {' or '.join(n.capitalize() for n in new)}, so it learns "
              f"{len(new)} new languages where a cross-platform toolkit needs one")

    if (
        layer == "frontend"
        and kind == "web"
        and d["skills"]
        and no_frontend_skill(frozenset(d["skills"]))
        and sc.get("hiring", 3) != 3
    ):
        # The frontend mirror of the rule above: a team whose skills match no web frontend hires or learns for one.
        a(HIRING_LEVEL_POINTS * (sc["hiring"] - 3), "team_skills",
          f"Your team lists no frontend skill, so it will hire or learn for this frontend: hiring pool {sc['hiring']}/5")

    if layer == "backend" and kind == "baas" and not known_skills(item, d) and server_skills(d):
        # The mirror image of the bonus above: the team would set aside the server language it ships.
        a(-TEAM_SHIPS_BONUS, "team_skills",
          f"Your team writes server code ({', '.join(sorted(server_skills(d)))}); {item['name'].split(' (')[0]} replaces it "
          "with a programming model nobody on the team has used")

    iso = item.get("tenant_isolation")
    if layer == "database" and p.get("tenancy") == "shared" and iso:
        # One query that forgets the customer filter leaks another customer's rows; a policy the database enforces
        # applies to every query from every part of the code.
        if iso["in_database"]:
            a(TENANT_ISOLATION_POINTS, "tenancy", f"Customers share one database and {item['name']} keeps them apart: {iso['how']}")
        else:
            a(-TENANT_ISOLATION_POINTS, "tenancy", f"Customers share one database and in {item['name']} {iso['how']}")

    if layer == "backend" and p.get("enterprise_sso") and kind in ("server", "faas"):
        # A BaaS that sells SAML/OIDC sign-in (item field `sso`) handles it; a backend of your own needs an identity
        # broker (Keycloak) to run, patch and back up beside it (engine/advice.py, "Enterprise SSO").
        a(-SSO_BROKER_POINTS, "enterprise_sso", "Company-account sign-in (SSO) needs an identity broker such as Keycloak "
          "that you run beside this backend")

    if layer == "database" and item["id"] in p["existing_systems"]:
        a(EXISTING_SYSTEM_BONUS, "existing_systems", f"Your team already runs {item['name']}: no migration needed")

    dbs_kept = [x for x in p["existing_systems"] if x in KEPT_DATABASES]
    if layer == "backend" and dbs_kept and item.get("bundled_database") and item["bundled_database"] not in dbs_kept:
        a(-EXISTING_SYSTEM_BONUS, "existing_systems", f"{item['name']} brings its own database; you must keep {', '.join(dbs_kept)}")

    pref = p["cloud_preference"]
    if pref != "none" and p["deployment"] != "on_prem":
        if layer == "hosting" and item.get("provider") == pref:
            bonus = cloud_pref_bonus(d["budget_usd"])
            why = f"Runs on your preferred cloud ({pref.upper()})"
            if bonus < CLOUD_PREF_BONUS:
                why += f"; bonus reduced because a budget under ${CLOUD_PREF_FULL_BUDGET_USD:.0f}/month favours free tiers"
            a(bonus, "cloud_preference", why)
        if layer == "database" and item.get("cloud"):
            if item["cloud"] == pref:
                a(3, "cloud_preference", f"Native to your preferred cloud ({pref.upper()})")
            else:
                a(-3, "cloud_preference", f"Lives on {item['cloud'].upper()}, not your preferred {pref.upper()}")

    # No stated cloud preference, but the team lists exactly the cloud(s) it already operates:
    # treat that as an implied, weaker preference.
    team_clouds = d["skills"] & set(HYPERSCALERS)
    if (
        pref == "none"
        and team_clouds
        and p["deployment"] != "on_prem"
        and layer == "hosting"
        and item.get("provider") in team_clouds
    ):
        a(3.5, "team_skills", f"Your team already operates {item['provider'].upper()} (listed in team skills)")

    arch = d["architecture"]
    if arch == "serverless":
        if layer == "backend" and kind == "faas":
            a(5, "architecture", "Matches serverless preference")
        if layer == "hosting" and (kind == "faas" or item["id"] == "gcp_cloud_run"):
            a(4, "architecture", "Matches serverless preference")
    elif arch == "microservices":
        if layer == "hosting" and kind in ("kubernetes", "containers"):
            a(3, "architecture", "Container orchestration suits microservices")
    elif arch == "monolith":
        if layer == "hosting" and kind in ("paas", "containers", "vps", "onprem"):
            a(2, "architecture", "Simple long-running deploy suits a monolith")
        if layer == "backend" and kind in ("baas", "faas") and p["architecture"] == "monolith":
            a(-6, "architecture", "You asked for a monolith; a BaaS or separate functions split the backend")

    if layer in ("hosting", "database") or (layer == "backend" and kind == "baas"):
        # Smooth penalty: grows with how far the minimum bill overshoots this layer's budget share
        # (log scale), so an option 4x over budget is not penalised as hard as one 40x over. A flat
        # penalty would hit cheap and expensive options equally once both exceed the budget and
        # erase the cheaper one's advantage at exactly the scale where cost matters most.
        lo, _ = net_cost(item, need, p, d)
        budget = d["budget_usd"]
        share = BUDGET_SHARE.get(layer, 0.6)
        if lo > 0 and budget <= 0:
            # Log curve from $0: a $1 bill costs ~1.4 points, $10 costs 10, then 6 more per e-fold,
            # so a nearly-free option is not penalised like a $10 one.
            if lo <= MIN_BUDGET_REF_USD:
                pen = 10 * math.log1p(lo / MIN_BUDGET_REF_USD) / math.log(2)
            else:
                pen = 10 + OVER_BUDGET_SLOPE * math.log(lo / MIN_BUDGET_REF_USD)
            a(-round(pen, 1), "budget_monthly", f"No free option at your scale (from ~${lo:,.0f}/month)")
            if layer == "hosting" and free_host and tier_cost(item, 0, p, d)[0] > 0:
                # A $0 budget means free plans: a host that has none at any scale loses to one whose free plan
                # passes every hard constraint, by a step on top of the price curve.
                a(-ZERO_BUDGET_PAID_HOST, "budget_monthly", f"No free plan at all, and {free_host} has one that fits your scale")
        elif lo > share * budget:
            pen = OVER_BUDGET_SLOPE * math.log(lo / (share * budget))
            if pen >= 0.5:
                if lo > budget:
                    why = f"Minimum ~${lo:,.0f}/month is {lo / budget:,.1f}x the whole budget"
                else:
                    why = f"Minimum ~${lo:,.0f}/month uses most of the budget"
                a(-round(pen, 1), "budget_monthly", why)

    if layer == "frontend":
        if item["id"] == "htmx" and (p["team_size"] >= 10 or p["realtime"] == "core" or p["app_type"] in RICH_UI_APPS):
            a(-6, "team_size" if p["team_size"] >= 10 else "app_type",
              "Server-rendered fragments get hard to coordinate across a large team or a rich, stateful UI")
        if p["seo"] == "critical" and sc.get("seo", 3) <= 2:
            a(-10, "seo", "Client-side rendering is a liability when organic search is the business")
        if p["offline"] and sc.get("offline", 3) <= 2:
            a(-6, "offline", "Weak offline story")
        sr = item.get("server_rendering")
        if sr and p["seo"] == "none" and not (d["skills"] & set(sr["own_skills"])):
            # Server rendering exists to hand crawlers and first-time visitors finished HTML. With no search
            # visibility asked for, the screens are the app itself (behind sign-in, or reached by link), and
            # the same components render in the browser from static files: the server runtime is cost without
            # that benefit. A team that already builds with the framework keeps it (no new tool to learn).
            alt = load_kb()["index"][sr["client_alternative"]]["name"]
            a(-SSR_WITHOUT_SEO_PENALTY, "seo",
              f"No search visibility needed: server rendering adds a Node.js server for pages that {alt} serves "
              "as static files")
            adj[-1]["preference"] = True
    if p["realtime"] == "core" and layer in ("backend", "hosting") and sc.get("realtime", 3) <= 1:
        a(-NO_PERSISTENT_CONNECTION_PENALTY, "realtime", "Cannot hold persistent realtime connections")
    if p["latency_target_ms"] <= 100 and (kind == "faas"):
        a(-6, "latency_target_ms", "Cold starts threaten a tight latency target")
    elif layer == "hosting" and item.get("scale_to_zero") and p["latency_target_ms"] <= STRICT_LATENCY_MS:
        # A request-billed host that scales to zero meets a strict target only with instances kept warm, which are
        # then billed while idle: the cold-start penalty of functions, for the same reason.
        a(-6, "latency_target_ms", f"{item['scale_to_zero']['why']}: a {p['latency_target_ms']:.0f} ms target needs "
                                   "them kept warm")
    if layer == "backend" and self_hosted_baas(item, p):
        a(-2, "deployment", f"Self-hosted on your servers: you operate ~10 {item['name'].split(' (')[0]} containers "
                            "(database, auth, API, realtime, storage, gateway) and their upgrades and backups")
    if layer == "backend" and kind == "baas" and p["team_size"] >= 15:
        a(-6, "team_size", "Large teams outgrow BaaS for complex domain logic")
    if layer == "backend" and kind == "baas" and p["read_write"] == "write_heavy" and d["compute_tier"] >= 2:
        a(-4 * (d["compute_tier"] - 1), "read_write",
          "High-rate writes through a BaaS API/row-level-security layer; use a dedicated ingestion service")
    sustained = d["compute_tier"] - d.get("burst_tiers", 0)
    if layer == "backend" and kind == "faas" and sustained >= STEADY_TRAFFIC_TIER:
        # The same reason the split-hosting rule gives an API its own host at this scale. Priced on the traffic
        # the daily users sustain: a tier reached only by a short peak (near-idle days, then a burst when sales
        # open) is the load per-request billing suits, as functions bill nothing between bursts
        # (https://aws.amazon.com/lambda/pricing/).
        a(-4 * (sustained - STEADY_TRAFFIC_TIER + 1), "dau",
          f"At {tier_label(sustained, 'dau')} traffic is steady: always-on instances with pooled database connections cost less "
          "than per-request functions")
    if layer == "backend" and kind == "baas" and p["realtime"] == "core" and p["latency_target_ms"] <= 100:
        a(-BAAS_REALTIME_LATENCY_PENALTY, "latency_target_ms", "Core realtime under 100 ms: BaaS change feeds add a database round trip "
                                   "to every message; a socket server relays directly")
    if layer == "backend" and kind == "baas" and "pci_dss" in p["compliance"] and not item.get("compliance", {}).get("pci"):
        a(-5, "compliance", "No PCI attestation; keep card data in a payment gateway")
    if layer == "database":
        fit = primary_models(item, p, d)[d["primary_shape"]]
        if fit <= 3:
            a(-6 if fit == 3 else -10, "data_shapes",
              f"Only {fit}/5 fit for your primary '{d['primary_shape'].replace('_', ' ')}' data")
        if best_fit:
            mine = data_fit(item, p, d)
            gap = best_fit[0] - mine
            if mine < GOOD_FIT <= best_fit[0] and gap > FIT_GAP_TOLERANCE:
                # The primary-shape penalty above is part of the same fit problem: raise the total, not add to it.
                gate = round(FIT_GAP_MAX * min(1.0, (gap - FIT_GAP_TOLERANCE) / FIT_GAP_RAMP), 1)
                extra = gate + sum(x["delta"] for x in adj if x["input"] == "data_shapes")
                if extra > 0:
                    a(-extra, "data_shapes",
                      f"Fits your data shapes {mine:.1f}/5 against {best_fit[0]:.1f}/5 for {best_fit[1]}")
        if best_fit and best_fit[2] and best_fit[2] != item["name"] and d["primary_shape"] not in DERIVED_SHAPES \
                and "data_shapes" not in d["defaulted"]:
            weak = [x for x in d["secondary_shapes"] if x not in DERIVED_SHAPES and primary_models(item, p, d)[x] <= 2]
            if weak:
                # The records of that shape still need a home: a second database to run and keep in step with this one,
                # while another option holds every record shape itself. Sized like a 2/5 fit for the primary shape.
                a(-SECOND_STORE_PENALTY, "data_shapes",
                  f"Fits your {', '.join(x.replace('_', ' ') for x in weak)} records "
                  f"{min(primary_models(item, p, d)[x] for x in weak)}/5, so they would need a second database; "
                  f"{best_fit[2]} holds all your record shapes")
    if layer == "database" and item.get("single_node") and d["availability"] >= 99.9:
        a(-6, "availability", "Single-node file database: no automatic failover for a 99.9%+ target")
        # The stack is then priced as one instance (engine/advice.py prices no redundancy for it), so it
        # looks cheaper only because it drops the target: it counts as missing it even when 99.9% is
        # the default rather than a stated answer (engine/stack.py target_misses).
        adj[-1]["binding"] = True
    if layer == "database" and item.get("single_writer") and p["realtime"] == "core" \
            and p["read_write"] == "write_heavy" and d["compute_tier"] >= 1:
        # Every message from every connected user is a write, and one writer at a time holds the lock.
        a(-SINGLE_WRITER_REALTIME_PENALTY, "realtime",
          "One writer at a time for the whole file: with realtime core and write-heavy traffic from "
          f"{p['dau']:,} daily users ({d['tier_label']}), every message queues on the database lock")
    elif layer == "database" and item.get("single_writer") and daily_hits_at_tier_floor(d) > SINGLE_WRITER_HITS_OK:
        hits = daily_hits_at_tier_floor(d)
        share = min(1.0, math.log(hits / SINGLE_WRITER_HITS_OK) / math.log(SINGLE_WRITER_HITS_MAX / SINGLE_WRITER_HITS_OK))
        a(-round(SINGLE_WRITER_REALTIME_PENALTY * share, 1), "dau",
          f"One writer at a time for the whole file: {d['tier_label']} scale means {hits / 1e3:,.0f}k+ requests a day, past "
          "SQLite's own guide of 100k hits a day for a website; concurrent writes (orders, posts, sessions) queue on one lock")
    if layer == "database" and item.get("memory_bound"):
        gb = d["data_12mo_gb"]
        if gb > 25 and not ram_affordable(p, d):
            a(-10, "data_volume_gb", f"In-memory store: ~{gb:,.0f} GB would have to fit in RAM; use it as a cache, not the system of record")
        else:
            a(-3, "data_volume_gb", "In-memory store as primary: durability depends on AOF/RDB persistence")
    if layer == "backend" and item.get("admin_scaffolding") and p["app_type"] in ("internal_tool", "prototype"):
        a(4, "app_type", "Generated admin/CRUD scaffolding fits internal tools")
    if p["app_type"] == "prototype" and kind == "kubernetes":
        a(-KUBERNETES_PROTOTYPE_PENALTY, "app_type", "Kubernetes is overkill for a prototype")
    return adj


def score_layer(layer: str, items: list[dict], p: dict, d: dict, w: Weights, relax: int = 0, force: tuple = (),
                light: bool = False):
    """Score the items that pass the hard constraints. Ids in `force` are scored even when excluded
    (used only by the 'Why not X?' comparison, which labels such scores approximate).
    `light` leaves out the per-criterion breakdown and per-input contributions (used for the scale
    tiers the growth path only compares); the scores themselves are computed identically."""
    feasible, excluded = [], []
    for it in items:
        reasons = [r for r in hard_constraints(layer, it, p, d) if not (r[2] and r[2] <= relax)]
        if reasons and it["id"] not in force:
            excluded.append({"id": it["id"], "name": it["name"],
                             "reasons": [r[0] for r in reasons], "constraints": sorted({r[1] for r in reasons})})
        else:
            feasible.append(it)
    costs = layer_cost_scores(layer, feasible, p, d) if feasible else {}
    best_fit = None
    if layer == "database" and feasible:
        top = max(feasible, key=lambda it: data_fit(it, p, d))
        # The best-fitting option that fits every record shape at least 3/5 (one database for all records), if any.
        cover = next((it["name"] for it in sorted(feasible, key=lambda it: -data_fit(it, p, d))
                      if all(primary_models(it, p, d)[x] >= 3 for x in record_shapes(d))), None)
        best_fit = (data_fit(top, p, d), top["name"], cover)
    free_host = next((it["name"] for it in feasible if net_cost(it, d["compute_tier"], p, d)[0] <= 0), None)         if layer == "hosting" and d["budget_usd"] <= 0 else None
    crits = LAYER_CRITERIA[layer]
    totals = [(c, w.total(c)) for c in crits]
    W = sum(wc for _, wc in totals) or 1.0
    scored = []
    for it in feasible:
        s = raw_scores(layer, it, p, d, costs)
        breakdown, contrib = [], defaultdict(float)
        base = 0.0
        for c, wc in totals:
            norm = (s[c] - 1) / 4 * 100
            pts = wc * norm / W
            base += pts
            if light:
                continue
            breakdown.append({"criterion": c, "label": CRITERION_LABELS[c], "score": round(s[c], 2),
                              "weight": round(wc, 2), "points": round(pts, 2)})
            for inp, amt in w.share(c).items():
                contrib[inp] += amt * norm / W
        adj = adjustments(layer, it, p, d, best_fit, free_host)
        raw_total = base + sum(x["delta"] for x in adj)
        final = max(0.0, min(100.0, raw_total))
        if not light:
            for x in adj:
                contrib[x["input"]] += x["delta"]
            if final != raw_total:
                contrib["clamp"] += final - raw_total  # so the listed contributions still add up to the shown score
        scored.append({"id": it["id"], "name": it["name"], "item": it, "raw": s, "base": round(base, 2),
                       "score": round(final, 2), "breakdown": breakdown, "adjustments": adj,
                       "contributions": dict(contrib), "_unclamped": raw_total, "_ctx": (w, totals, W, layer)})
    # Options clamped to the same score (several at 0 far over a tiny budget) keep the order of their
    # unclamped totals, not the knowledge base's file order: otherwise which of them make the top-K pool
    # changes from one scale tier to the next, and the pick cycles between them as users grow.
    scored.sort(key=lambda x: (-x["score"], -x["_unclamped"]))
    return scored, excluded
