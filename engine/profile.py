"""Turns raw questionnaire answers into a clean, derived project profile.

Every default applied, every value clamped and every implied requirement is recorded
as an *assumption* or *warning* so the user can see exactly what the engine used.
"""
from __future__ import annotations

import math
from copy import deepcopy

from .kb import field_specs, load_kb

INR_PER_USD = 96.0  # fixed planning rate: FBIL reference rate 95.89 on 25 Sep 2026, rounded
USD_PER_INR = 1 / INR_PER_USD
FX_NOTE = "INR converted at a fixed planning rate of 96 INR = 1 USD (FBIL reference rate, Sep 2026)."

# Requests per active user per day and peak-to-average factor, by app archetype.
# Used only when peak RPS is not supplied. Values are planning heuristics. IoT counts devices, at one
# reading a minute (sensor fleets commonly report every 1-15 minutes; state a peak RPS for faster ones).
REQ_PER_USER_DAY = {
    "saas": 150, "ecommerce": 60, "realtime_collab": 300, "content_site": 8,
    "analytics_dashboard": 120, "ml_product": 40, "iot_telemetry": 1440, "fintech": 80,
    "healthcare": 60, "social_network": 200, "internal_tool": 150, "mobile_first": 120,
    "prototype": 50,
}
CACHE_ORIGIN_SHARE = {"auto": 1.0, "little": 1.0, "some": 0.6, "most": 0.2}
PEAK_FACTOR = {"ecommerce": 10, "content_site": 3, "iot_telemetry": 1.5, "social_network": 6}
DEFAULT_PEAK_FACTOR = 5

DAU_THRESHOLDS = [1e3, 1e4, 1e5, 1e6, 1e7]
RPS_THRESHOLDS = [5, 50, 500, 5000, 50000]
DATA_GB_THRESHOLDS = [10, 100, 1000, 10000, 100000]
# A scale tier is the larger of the tier of daily users and the tier of peak requests/s, so its label names the
# measure that set it: "Large (500-5,000 req/s at peak)" for 30k daily users of a chatty realtime app, not a
# daily-user range the project does not have. The database tier names the data size when data sets it.
TIER_NAMES = ["Hobby", "Small", "Medium", "Large", "Very large", "Hyperscale"]
TIER_RANGES = {
    "dau": ["<1k daily users", "1k-10k daily users", "10k-100k daily users", "100k-1M daily users",
            "1M-10M daily users", ">10M daily users"],
    "rps": ["<5 req/s at peak", "5-50 req/s at peak", "50-500 req/s at peak", "500-5,000 req/s at peak",
            "5,000-50,000 req/s at peak", ">50,000 req/s at peak"],
    "conn": ["<50 users online at once", "50-500 users online at once", "500-5,000 users online at once",
             "5,000-50,000 users online at once", "50,000-500,000 users online at once", ">500,000 users online at once"],
    "data": ["<10 GB of data", "10-100 GB of data", "100 GB-1 TB of data", "1-10 TB of data", "10-100 TB of data",
             ">100 TB of data"],
}
# A tier in general (a price band), by both measures that can set it.
TIER_LABELS = [f"{n} ({u} or {r})" for n, u, r in zip(TIER_NAMES, TIER_RANGES["dau"], TIER_RANGES["rps"])]


def tier_label(k: int, by: str) -> str:
    """'Large (100k-1M daily users)', 'Large (500-5,000 req/s at peak)' or 'Large (1-10 TB of data)'."""
    return f"{TIER_NAMES[k]} ({TIER_RANGES[by][k]})"


def tier_labels(compute_tier: int, dau_tier: int, data_tier: int, db_tier: int, conn_tier: int = 0) -> tuple[str, str]:
    """Labels of the scale tier and the database tier, each naming the measure that set it."""
    label = tier_label(compute_tier, "dau" if compute_tier <= dau_tier else "conn" if compute_tier <= conn_tier else "rps")
    if data_tier >= db_tier and data_tier > 0:
        db_label = tier_label(db_tier, "data")
    elif db_tier == compute_tier:
        db_label = label
    else:  # one tier below the traffic: caches and CDNs absorb most reads
        db_label = f"{TIER_NAMES[db_tier]} (one tier below the traffic: read-heavy, caches absorb most reads)"
    return label, db_label


# Stored data when the user gives none: database rows (accounts, sessions, posts, orders, events; media go to
# object storage) per daily user a month, by app type. Planning figures: a user who makes ~150 requests a day
# and writes ~20 rows of ~500 bytes with their indexes stores ~0.3-0.5 MB a month; social feeds, collaboration
# documents and event-heavy dashboards store more; a device that reports once a minute stores ~43,200 readings
# of ~100 bytes (~4 MB) a month. The user count is the one stated (raised to the users connected at once when that is
# larger); with no user count it is the typical one of the scale tier the traffic sets (the geometric middle of its
# range, or fewer where fewer users reach the tier through peak requests). Users connected at once raise the compute
# tier, never the invented data: they are people already counted, not extra rows.
DATA_MB_PER_USER_MONTH = {"saas": 0.5, "ecommerce": 0.5, "realtime_collab": 1.0, "analytics_dashboard": 2.0,
                          "ml_product": 1.0, "iot_telemetry": 4.0, "fintech": 0.5, "healthcare": 0.5,
                          "social_network": 1.5, "internal_tool": 0.5, "mobile_first": 0.5, "prototype": 0.2}
DEFAULT_DATA_MB = 0.5
TIER_TYPICAL_DAU = [300, 3_000, 30_000, 300_000, 3_000_000, 30_000_000]


# The middle (geometric) of each tier's range of peak requests/s.
TIER_TYPICAL_RPS = [1.6, 16, 160, 1_600, 16_000, 160_000]


def traffic_factors(p: dict) -> tuple[float, float, float]:
    """(requests per user a day, peak factor, share of requests that reach the servers) for these answers."""
    app = p["app_type"]
    rpd = REQ_PER_USER_DAY.get(app, 100)
    pf = PEAK_FACTOR.get(app, DEFAULT_PEAK_FACTOR)
    if p["traffic_pattern"] == "steady":
        pf = min(pf, 3)
    elif p["traffic_pattern"] == "spiky":
        pf = max(pf * 2, 15)
    return rpd, pf, CACHE_ORIGIN_SHARE[p["cacheable_share"]]


def typical_users(p: dict, tier: int) -> float:
    """Daily users typical of a scale tier for these answers: the middle of the tier's user range, or, where fewer
    users already reach the tier through their peak requests (a chatty realtime app), that smaller number."""
    rpd, pf, origin = traffic_factors(p)
    return min(TIER_TYPICAL_DAU[tier], TIER_TYPICAL_RPS[tier] * 86400 / (rpd * pf * origin))


def _gb(x: float) -> str:
    return f"{x:,.2f} GB" if x < 10 else f"{x:,.0f} GB"


def estimated_data_fields(p: dict, assumptions: list[dict]) -> list[str]:
    """Data-volume answers left at the generic default (an app-type default, e.g. a content site's, is kept)."""
    rules = APP_DEFAULTS.get(p["app_type"], {})
    return [a["field"] for a in assumptions if a.get("kind") == "default"
            and a["field"] in ("data_volume_gb", "data_growth_gb_month") and a["field"] not in rules]


# Ceiling on an estimated 12-month data size (launch + 12 months of growth), by app type. Past a few TB the size
# depends on retention (how long rows are kept), which no per-user figure can know, so the estimate stops here and the
# assumption asks for the real figure. Telemetry and event dashboards keep raw readings and events, so they go higher.
DATA_ESTIMATE_CAP_GB = {"iot_telemetry": 10_000, "analytics_dashboard": 10_000, "social_network": 5_000}
DEFAULT_DATA_ESTIMATE_CAP_GB = 2_000


def data_users(p: dict, tier: int, anchor: tuple[int, float]) -> float:
    """Daily users the data estimate assumes at scale tier `tier`. `anchor` is (the answers' own tier, the users
    there); other tiers of the growth path take their typical users, kept on the anchor's side of it so the estimate
    never shrinks as the tier grows."""
    own, users = anchor
    t = typical_users(p, tier)
    return users if tier == own else min(t, users) if tier < own else max(t, users)


def estimated_data(p: dict, tier: int, estimated: list[str], anchor: tuple[int, float]) -> tuple[float, float]:
    """(data at launch, growth a month) in GB at this scale tier; given answers are kept."""
    growth = data_users(p, tier, anchor) * DATA_MB_PER_USER_MONTH.get(p["app_type"], DEFAULT_DATA_MB) / 1024
    growth = min(growth, DATA_ESTIMATE_CAP_GB.get(p["app_type"], DEFAULT_DATA_ESTIMATE_CAP_GB) / 13)
    growth = round(growth, 3) if "data_growth_gb_month" in estimated else p["data_growth_gb_month"]
    vol = round(growth, 3) if "data_volume_gb" in estimated else p["data_volume_gb"]
    return vol, growth


def user_steps(p: dict) -> list[tuple[int, float, float, float]]:
    """(scale tier, lowest users, highest users, users the estimate takes) of each half of each scale tier's range
    of daily users, smallest first. The halves split at the tier's typical users; the tiers meet half-way (geometric)
    between two typical counts."""
    n = len(TIER_NAMES)
    typ = [typical_users(p, k) for k in range(n)]
    edges = [0.0] + [math.sqrt(typ[k] * typ[k + 1]) for k in range(n - 1)] + [math.inf]
    out = []
    for k in range(n):
        lo, hi = edges[k], edges[k + 1]
        out.append((k, lo, typ[k], math.sqrt(lo * typ[k]) if lo else typ[k] / 10 ** 0.25))
        out.append((k, typ[k], hi, math.sqrt(typ[k] * hi) if hi < math.inf else typ[k] * 10 ** 0.25))
    return out


def step_users(p: dict, users: float) -> float:
    """Daily users an estimated data size takes for this many stated users: the middle (geometric) of their half of
    the scale tier, so every user count in one half gets the same estimate and the growth path (one step per half)
    agrees with every run, while the estimate stays within ~1.8x of the stated count."""
    return next(r for _, lo, hi, r in user_steps(p) if lo <= users < hi)


def growth_steps(p: dict, d: dict) -> list[tuple[int, float | None]]:
    """(scale tier, daily users of the data estimate) at each step of the growth path, smallest first. Users None:
    the tier's own estimate (data_users). With stated users the path takes one step per half of each tier
    (step_users); the answers' own step has their own scale tier, the steps below and above it are kept on their side.
    No step sits below the tier of the users online at once: that count is stated, so it does not shrink with the users
    (else a run's own step would be the only one it lifts, and runs at nearby user counts would walk different paths)."""
    if not d["data_estimated"] or not d["data_stated_users"]:
        return [(k, None) for k in range(len(TIER_NAMES))]
    own, users = d["data_anchor"]
    return [(own if r == users else min(max(k, d["conn_tier"]), own) if r < users else max(k, own), r)
            for k, _, _, r in user_steps(p)]


def own_step(p: dict, d: dict) -> int:
    """Index of the answers' own step on the growth path."""
    return growth_steps(p, d).index((d["compute_tier"], d["data_anchor"][1] if d["data_estimated"]
                                     and d["data_stated_users"] else None))


# Users connected at the same moment that start each scale tier. Peak concurrency is commonly a few percent to
# a tenth of daily users, so these sit at a tenth of the daily-user thresholds above (10k online ~ 100k DAU).
CONCURRENT_THRESHOLDS = [50, 500, 5000, 50000, 500000]


def _burst_shift(peak_rps: float, dau: float) -> int:
    """Whole scale tiers by which the peak request rate sits above the daily users' tier, from the ratio of the two
    thresholds lists (RPS_THRESHOLDS / DAU_THRESHOLDS = 5 req/s per 1,000 users)."""
    base = max(dau, 1) * RPS_THRESHOLDS[0] / DAU_THRESHOLDS[0]
    return max(0, math.floor(math.log10(max(peak_rps, 1e-9) / base) + 1e-9))


def _tier(value: float, thresholds: list[float]) -> int:
    return sum(1 for t in thresholds if value >= t)


def _warn(code, severity, title, detail, resolution, fields):
    return {"code": code, "severity": severity, "title": title, "detail": detail,
            "resolution": resolution, "fields": fields}


def normalize(raw: dict | None) -> tuple[dict, list[dict], list[dict]]:
    """Apply defaults, coerce types, clamp extremes. Returns (profile, assumptions, warnings)."""
    raw = dict(raw or {})
    specs = field_specs()
    profile: dict = {}
    assumptions: list[dict] = []
    warnings: list[dict] = []

    unknown = sorted(str(k) for k in raw if k not in specs)
    if unknown:
        warnings.append(_warn("UNKNOWN_FIELD", "info", "Ignored unknown input fields",
                              f"Not questions StackSense asks: {', '.join(unknown[:8])}.",
                              "They were ignored. Check the spelling against the question keys.", unknown[:8]))

    for key, spec in specs.items():
        val = raw.get(key)
        default = deepcopy(spec.get("default"))
        missing = val is None or val == "" or (isinstance(val, list) and not val and spec["type"] == "multiselect" and default)
        if missing:
            profile[key] = default
            if key == "regions" and not default:
                assumptions.append({"field": key, "label": spec.get("label", key), "value": default, "kind": "default",
                                    "reason": "Not provided: no region is favoured when hosts are scored."})
            elif key not in ("project_name", "peak_rps", "peak_concurrent", "background_work", "tenancy", "enterprise_sso", "team_skills", "compliance", "priorities", "existing_systems", "traffic_pattern", "cacheable_share",
                             "ml_features", "team_experience", "has_devops", "self_managed", "air_gapped", "cloud_required"):
                assumptions.append({"field": key, "label": spec.get("label", key), "value": default, "kind": "default",
                                    "reason": f"Not provided; using default '{_fmt(default)}'."})
            continue
        t = spec["type"]
        if t == "number":
            try:
                num = float(val)
                if math.isnan(num) or math.isinf(num):
                    raise ValueError
            except (TypeError, ValueError, OverflowError):  # OverflowError: integers beyond float range
                profile[key] = default
                warnings.append(_warn("INVALID_NUMBER", "warning", f"Invalid value for {spec['label']}",
                                      f"'{val}' is not a number.", f"Used default {_fmt(default)}.", [key]))
                continue
            if isinstance(val, str):
                warnings.append(_warn("TYPE_COERCED", "info", f"{spec['label']} given as text",
                                      f"'{val}' was read as the number {_fmt(num)}.", "Used the number.", [key]))
            lo, hi = spec.get("min"), spec.get("max")
            if lo is not None and num < lo:
                warnings.append(_warn("VALUE_CLAMPED", "warning", f"{spec['label']} below minimum",
                                      f"{_fmt(num)} is below the minimum {_fmt(lo)}.", f"Clamped to {_fmt(lo)}.", [key]))
                num = lo
            if hi is not None and num > hi:
                warnings.append(_warn("VALUE_CLAMPED", "warning", f"{spec['label']} above maximum",
                                      f"{_fmt(num)} exceeds the supported maximum {_fmt(hi)}.", f"Clamped to {_fmt(hi)}.", [key]))
                num = hi
            profile[key] = num
        elif t == "select":
            allowed = [o["value"] for o in spec["options"]]
            sval = str(val)
            if sval not in allowed:
                profile[key] = default
                warnings.append(_warn("UNKNOWN_OPTION", "warning", f"Unknown option for {spec['label']}",
                                      f"'{val}' is not one of {allowed}.", f"Used default '{default}'.", [key]))
            else:
                profile[key] = sval
        elif t == "multiselect":
            vals = val if isinstance(val, list) else [v.strip() for v in str(val).split(",") if v.strip()]
            vals = [str(v).strip().lower() for v in vals]
            if spec.get("free"):
                profile[key] = list(dict.fromkeys(vals))
            else:
                allowed = [o["value"] for o in spec["options"]]
                bad = [v for v in vals if v not in allowed]
                good = list(dict.fromkeys(v for v in vals if v in allowed))
                if bad:
                    warnings.append(_warn("UNKNOWN_OPTION", "info", f"Ignored unknown values in {spec['label']}",
                                          f"Unrecognised: {bad}.", "They were dropped.", [key]))
                profile[key] = good or default
        elif t == "bool":
            profile[key] = val if isinstance(val, bool) else str(val).lower() in ("1", "true", "yes", "on")
        else:
            profile[key] = str(val)[:120]

    if profile.get("air_gapped") and profile["deployment"] != "on_prem":
        assumptions.append({"field": "deployment", "label": "Deployment model", "value": "on_prem", "kind": "derived",
                            "reason": "Air-gapped servers have no internet connection, so they run on your own premises."})
        profile["deployment"] = "on_prem"
    profile["dau"] = int(profile["dau"])
    profile["team_size"] = max(1, int(round(profile["team_size"])))
    profile["timeline_weeks"] = max(1, int(round(profile["timeline_weeks"])))
    return profile, assumptions, warnings


def _fmt(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return f"{int(v):,}"
    if isinstance(v, (int, float)):
        return f"{v:,}"
    if isinstance(v, list):
        return ", ".join(map(str, v)) or "none"
    return str(v)


# Defaults that depend on the app type, used only for questions the user did not answer. The
# generic defaults (relational data, no SEO, balanced reads/writes) describe a CRUD app and would
# silently mis-describe these archetypes.
APP_DEFAULTS = {
    "iot_telemetry": {"data_shapes": (["time_series", "relational"], "device readings are timestamped series"),
                      "read_write": ("write_heavy", "devices write continuously; people read dashboards")},
    "analytics_dashboard": {"data_shapes": (["analytical", "relational"], "dashboards aggregate large tables"),
                            "read_write": ("read_heavy", "dashboards mostly read and aggregate")},
    "content_site": {"seo": ("important", "content sites are found through search"),
                     "user_actions": (["read"], "visitors read what the team publishes"),
                     # Read-only: pages and posts are content files (see CONTENT_SITE_RECORDS for a site users write to).
                     "data_shapes": (["document"], "pages and posts are documents"),
                     "data_volume_gb": (1, "text and images of a content site"),
                     "data_growth_gb_month": (0.1, "a few posts and images a month")},
    "ml_product": {"data_shapes": (["relational", "vector"], "retrieval and semantic search need embeddings")},
    # Product and category pages are how shoppers arrive from search; pages rendered only in the browser
    # are indexed later and less reliably
    # (https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics).
    "ecommerce": {"seo": ("important", "shoppers find product pages through search")},
}


# A content site whose users sign in, post or pay keeps accounts, comments and orders: mainstream content systems keep
# those, with pages, posts, authors and tags, in relational tables (WordPress: https://wordpress.org/about/requirements/,
# Ghost: https://ghost.org/docs/install/ubuntu/), so the app type's default data shape is then relational.
CONTENT_SITE_RECORDS = (["relational"], "users sign in or post, and content systems such as WordPress and Ghost keep "
                                        "accounts, comments, pages and posts in relational tables")


def _apply_app_defaults(p: dict, assumptions: list[dict]) -> None:
    rules = APP_DEFAULTS.get(p["app_type"], {})
    for a in assumptions:
        if a.get("kind") == "default" and a["field"] in rules:
            value, why = rules[a["field"]]
            p[a["field"]] = deepcopy(value)
            a["value"] = deepcopy(value)
            a["reason"] = (f"Not provided; using the default for this app type, '{_fmt(value)}' "
                           f"({why}).")
            a["app_type"] = p["app_type"]  # an app-type default: what this kind of app is, not a blank answer
    # The generic default for what users do (read, sign in, post) stores accounts and posts. A project that
    # states no data at launch and no growth stores nothing users write, so the default becomes read-only.
    defaulted = {a["field"] for a in assumptions if a.get("kind") == "default"}
    no_data = p["data_volume_gb"] == 0 and p["data_growth_gb_month"] == 0
    if "user_actions" in defaulted and not {"data_volume_gb", "data_growth_gb_month"} & defaulted and no_data:
        p["user_actions"] = ["read"]
        for a in assumptions:
            if a.get("kind") == "default" and a["field"] == "user_actions":
                a["value"] = ["read"]
                a["reason"] = ("Not provided; you stated no data at launch and no data growth, so nothing users write is "
                               "stored: visitors only read ('read').")
    if p["app_type"] == "content_site" and not set(p["user_actions"]) <= {"read"}:
        for a in assumptions:
            if a.get("kind") == "default" and a["field"] == "data_shapes" and a.get("app_type"):
                value, why = CONTENT_SITE_RECORDS
                p["data_shapes"] = deepcopy(value)
                a["value"] = deepcopy(value)
                a["reason"] = f"Not provided; using the default for this app type, '{_fmt(value)}' ({why})."


def derive(profile: dict, assumptions: list[dict], warnings: list[dict]) -> dict:
    """Compute derived quantities and apply implied requirements. Mutates profile in place."""
    p = profile
    app = p["app_type"]
    _apply_app_defaults(p, assumptions)

    # ---- implied requirements from the archetype -------------------------------------
    if app == "mobile_first" and p["platforms"] == ["web"]:
        p["platforms"] = ["android", "ios"]
        assumptions.append({"field": "platforms", "value": p["platforms"],
                            "reason": "App type is mobile-first, so iOS and Android were added as target platforms."})
    if app == "realtime_collab" and p["realtime"] != "core":
        warnings.append(_warn("IMPLIED_REALTIME", "warning", "Realtime app without realtime requirement",
                              f"App type is realtime collaboration but realtime was '{p['realtime']}'.",
                              "Treated realtime as 'core' (persistent connections).", ["realtime", "app_type"]))
        p["realtime"] = "core"
    work = set(p.get("special_workloads") or [])
    if "live_location" in work and p["realtime"] == "none":
        # Positions are pushed to the map every few seconds over an open connection, not polled
        # (engine/advice.py, "Maps & live location").
        p["realtime"] = "some"
        assumptions.append({"field": "realtime", "value": "some",
                            "reason": "Live location sends position updates every few seconds over an open connection "
                                      "(WebSockets), so realtime was raised from 'none' to 'some'."})
    if app == "fintech" and p["consistency"] != "strong":
        warnings.append(_warn("IMPLIED_CONSISTENCY", "warning", "Fintech with eventual consistency",
                              "Ledgers and balances cannot tolerate lost or reordered writes.",
                              "Forced consistency to 'strong' (ACID).", ["consistency", "app_type"]))
        p["consistency"] = "strong"
    if app == "fintech" and "india" in p["regions"] and "pay" in (p.get("user_actions") or []) \
            and "data_residency_india" not in p["compliance"]:
        # RBI's 2018 circular binds payment system providers, not every fintech (lending or wealth apps fall under
        # other rules), so it is assumed only when users pay through the app.
        p["compliance"] = p["compliance"] + ["data_residency_india"]
        assumptions.append({"field": "compliance", "value": "data_residency_india",
                            "reason": "Payments in India: RBI's 2018 circular requires payment system providers to store "
                                      "payment data only in India. Assumed because users pay through the app; remove "
                                      "'Data must stay in India' if a licensed payment provider holds the payment data."})
    if app == "healthcare" and "north_america" in p["regions"] and "hipaa" not in p["compliance"]:
        warnings.append(_warn("HIPAA_HINT", "info", "US healthcare without HIPAA",
                              "If you store PHI for a US covered entity, HIPAA applies and every vendor must sign a BAA.",
                              "Not added automatically; tick HIPAA if it applies.", ["compliance"]))
    if app == "content_site" and p["seo"] == "none":
        warnings.append(_warn("SEO_HINT", "info", "Content site with SEO marked unnecessary",
                              "Content sites usually depend on organic search.", "Kept your answer.", ["seo"]))
    if app == "ml_product" and "vector" not in p["data_shapes"]:
        warnings.append(_warn("VECTOR_HINT", "info", "ML product without vector data",
                              "Retrieval/semantic features usually need embeddings.",
                              "Kept your answer; add 'vector' if you do retrieval.", ["data_shapes"]))
    if "dpdp" in p["compliance"]:
        assumptions.append({"field": "compliance", "value": "dpdp",
                            "reason": "DPDP Act 2023 (in force through the DPDP Rules 2025, notified November 2025 and phased in over 18 months) allows cross-border transfer except to notified countries, so it adds consent/breach-notice duties but not an India-region filter. Add 'Data must stay in India' if a sector rule (e.g. RBI) applies."})

    if len(p["priorities"]) > 3:
        warnings.append(_warn("PRIORITIES_TRIMMED", "info", "More than 3 priorities",
                              f"You ranked {len(p['priorities'])} priorities.", "Only the first three are used.", ["priorities"]))
        p["priorities"] = p["priorities"][:3]
    for sysname in p["existing_systems"]:
        if sysname not in load_kb()["index"]:
            label = {"oracle": "Oracle Database"}.get(sysname, sysname)
            warnings.append(_warn("EXISTING_SYSTEM_UNKNOWN", "info", f"{label} is not in the knowledge base",
                                  f"StackSense scores {len(load_kb()['database'])} databases and {label} is not one of them, so it cannot be kept as the pick.",
                                  "Recommending the closest open database; plan a migration or keep a sync from your existing one.",
                                  ["existing_systems"]))

    # ---- users online at once ------------------------------------------------------------
    conc = int(p["peak_concurrent"]) if p.get("peak_concurrent") else 0
    if conc > p["dau"]:
        warnings.append(_warn("CONCURRENT_ABOVE_DAU", "info", "More users online at once than daily users",
                              f"{conc:,} users connected at the same moment cannot be fewer than {p['dau']:,} daily users.",
                              f"Planned for {conc:,} daily users (every connected user is active that day).",
                              ["peak_concurrent", "dau"]))
        p["dau"] = conc

    # ---- money -------------------------------------------------------------------------
    budget_usd = p["budget_monthly"] * (USD_PER_INR if p["currency"] == "INR" else 1.0)

    # ---- traffic -----------------------------------------------------------------------
    rpd, pf, origin = traffic_factors(p)
    implied_rps = p["dau"] * rpd / 86400 * pf * origin
    rps_source = "derived"
    peak_rps = implied_rps
    if p.get("peak_rps") is not None:
        stated = float(p["peak_rps"])
        if stated > max(100, 2 * p["dau"]) and app != "iot_telemetry":
            warnings.append(_warn("PEAK_RPS_IMPLAUSIBLE", "warning", "Peak RPS is implausible for this many daily users",
                                  f"{stated:,.0f} req/s with {p['dau']:,} daily users means every user would make more than "
                                  f"{stated / max(p['dau'], 1):.0f} requests each second at the same moment.",
                                  "Check the unit (requests per second, not per day) or the user count.", ["peak_rps", "dau"]))
        given = stated * origin  # cached responses are served by the CDN and never reach the servers
        rps_source = "provided"
        peak_rps = given
        if implied_rps > 0 and given > 0:
            ratio = max(given, implied_rps) / max(min(given, implied_rps), 1e-9)
            if ratio > 30 and app == "iot_telemetry":
                # Device fleets report anywhere from every second to once a day, so a stated rate is
                # better evidence than the per-device default: trust it and say so.
                warnings.append(_warn("RPS_DAU_MISMATCH", "info", "Peak RPS differs from the device-count estimate",
                                      f"You entered {given:,.0f} req/s; {p['dau']:,} devices at the default of one reading a minute "
                                      f"(peak x{pf}) would give about {implied_rps:,.0f} req/s.",
                                      f"Used your figure ({given:,.0f} req/s): device reporting rates vary widely, so a stated rate wins.",
                                      ["peak_rps", "dau"]))
            elif ratio > 30:
                peak_rps = max(given, implied_rps)
                rps_source = "max(provided, derived)"
                warnings.append(_warn("RPS_DAU_MISMATCH", "warning", "Peak RPS inconsistent with DAU",
                                      f"You entered {given:,.0f} req/s but {p['dau']:,} DAU of a '{app}' app implies about {implied_rps:,.0f} req/s ({rpd} req/user/day, peak x{pf}).",
                                      f"Planned for the larger figure ({peak_rps:,.0f} req/s), the safer choice for capacity.",
                                      ["peak_rps", "dau"]))
    dau_tier = _tier(p["dau"], DAU_THRESHOLDS)
    rps_tier = _tier(peak_rps, RPS_THRESHOLDS)
    compute_tier = max(dau_tier, rps_tier)
    if app == "iot_telemetry" and rps_source == "provided":
        compute_tier = rps_tier  # devices are not people loading pages: the stated message rate sizes compute
        dau_tier = min(dau_tier, rps_tier - 1)  # so the label names the message rate
    conn_tier = _tier(conc, CONCURRENT_THRESHOLDS) if conc else 0
    traffic_tier = compute_tier
    compute_tier = max(compute_tier, conn_tier)
    estimated = estimated_data_fields(p, assumptions)
    stated_users = "dau" not in {a["field"] for a in assumptions if a.get("kind") == "default"} or conc >= p["dau"]
    anchor = (compute_tier, step_users(p, p["dau"]) if stated_users else typical_users(p, traffic_tier))
    if estimated:
        vol, growth = estimated_data(p, compute_tier, estimated, anchor)
        capped = anchor[1] * DATA_MB_PER_USER_MONTH.get(app, DEFAULT_DATA_MB) / 1024 * 13 >             DATA_ESTIMATE_CAP_GB.get(app, DEFAULT_DATA_ESTIMATE_CAP_GB)
        who = (f"~{anchor[1]:,.0f} daily users (the {p['dau']:,} {'you stated' if conc < p['dau'] else 'connected at once'}, "
               "taken at the middle of their half of the scale tier so that every user count there gets the same estimate)"
               if stated_users else f"the ~{anchor[1]:,.0f} daily users typical of the {TIER_NAMES[traffic_tier]} scale tier")
        for a in assumptions:
            if a.get("kind") == "default" and a["field"] in estimated:
                a["value"] = vol if a["field"] == "data_volume_gb" else growth
                a["reason"] = (f"Not provided; estimated as {_gb(a['value'])}{'' if a['field'] == 'data_volume_gb' else '/month'} "
                               f"from {DATA_MB_PER_USER_MONTH.get(app, DEFAULT_DATA_MB):g} MB of database rows per daily user a "
                               f"month for this app type, at {who}"
                               + (f", capped at {_gb(DATA_ESTIMATE_CAP_GB.get(app, DEFAULT_DATA_ESTIMATE_CAP_GB))} in 12 months "
                                  "(beyond that the size depends on how long you keep data: state it)" if capped else "")
                               + (" (data at launch: one month's growth)." if a["field"] == "data_volume_gb" else "."))
        p["data_volume_gb"], p["data_growth_gb_month"] = vol, growth
    data_12mo = p["data_volume_gb"] + 12 * p["data_growth_gb_month"]
    data_tier = _tier(data_12mo, DATA_GB_THRESHOLDS)
    # Database load tracks traffic, but read-heavy traffic is largely absorbed by caches/CDN.
    db_tier = max(data_tier, compute_tier - (1 if p["read_write"] == "read_heavy" else 0))

    availability = float(p["availability"])
    skills = set(p["team_skills"])
    mobile = any(x in p["platforms"] for x in ("ios", "android"))
    # A desktop app is the web frontend in a desktop shell (engine/advice.py adds the shell); API only has no frontend.
    web = bool({"web", "desktop"} & set(p["platforms"]))
    api_only = p["platforms"] == ["api_only"]

    arch = p["architecture"]
    actions = set(p.get("user_actions") or [])
    # Work that needs a process which stays up between requests: (answer, why). The hosting pick must run it
    # (engine/scoring.py hard_constraints), so hosts that run code only as short request-scoped functions or
    # serve static files are excluded.
    workers = []
    if "user_code" in work:
        workers.append(("special_workloads", "code that users submit runs in a separate pool of long-running sandbox "
                        "workers (gVisor or Firecracker), never in a request-scoped function whose environment is "
                        "reused for the next request"))
    if p["background_work"] in ("long", "gpu"):
        workers.append(("background_work", "a background job that runs longer than 15 minutes outlives every function "
                        "platform's time limit (AWS Lambda 15 minutes, Vercel at most 800 s on Pro)"
                        if p["background_work"] == "long" else
                        "GPU work runs as long-running workers on GPU machines"))
    if p["background_work"] == "gpu":
        assumptions.append({"field": "background_work", "value": "gpu",
                            "reason": "Only hosts that rent GPUs were kept. GPU hours are billed by the hour on top of the "
                                      "estimate shown, which does not include them."})
    return {
        "gpu": p["background_work"] == "gpu",
        "workers": workers,
        "peak_concurrent": conc,
        "conn_tier": conn_tier,
        "user_actions": actions,
        "read_only": bool(actions) and actions <= {"read"},
        "budget_usd": round(budget_usd, 2),
        "fx_note": FX_NOTE if p["currency"] == "INR" else None,
        "req_per_user_day": rpd,
        "peak_factor": pf,
        "origin_share": origin,
        "peak_rps": round(peak_rps, 1),
        "implied_rps": round(implied_rps, 1),
        "rps_source": rps_source,
        "compute_tier": compute_tier,
        # Scale tiers that only the peak request rate reaches (bursts above what the daily users sustain). Device
        # fleets report at a steady rate, and a stated steady pattern has no bursts.
        # Measured as the ratio of the peak rate to the rate the daily users would give at the tier thresholds' own
        # ratio (5 req/s per 1,000 users), whole tiers only: a fixed property of the traffic shape, so it does not
        # flicker between 0 and 1 as users grow inside one tier (which made a pick leave and come back).
        "burst_tiers": 0 if app == "iot_telemetry" or p["traffic_pattern"] == "steady" else
        max(0, min(compute_tier - dau_tier, _burst_shift(peak_rps, p["dau"]))),
        "data_tier": data_tier,
        "db_tier": db_tier,
        "dau_tier": dau_tier,
        "tier_label": tier_labels(compute_tier, dau_tier, data_tier, db_tier, conn_tier)[0],
        "db_tier_label": tier_labels(compute_tier, dau_tier, data_tier, db_tier, conn_tier)[1],
        "data_12mo_gb": round(data_12mo, 1),
        "availability": availability,
        "skills": skills,
        "mobile": mobile,
        "web": web,
        "api_only": api_only,
        "primary_shape": p["data_shapes"][0],
        "secondary_shapes": p["data_shapes"][1:],
        "architecture": arch,
        # Inputs left at their default: a planning assumption, not a requirement the user stated.
        "defaulted": {a["field"] for a in assumptions if a.get("kind") == "default"},
        # Data fields estimated from the scale tier (not given): they follow the tier on the growth path too.
        "data_estimated": estimated,
        "data_anchor": anchor,
        "data_stated_users": stated_users,
        # Of these, the ones set by the app type's own default (APP_DEFAULTS) rather than the generic default.
        "app_defaulted": {a["field"] for a in assumptions if a.get("kind") == "default" and a.get("app_type")},
    }
