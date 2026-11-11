"""The Synergy '26 scenario format: read a scenario file (problem statement section 3), run the engine, and
return the section 4 output.

This module is the boundary between that format and the engine. It checks every field, maps each one to the
engine's own answers (data/questions.json), records every default and interpretation in `assumptions`, and
turns the engine's result into the output schema. It never calls a language model, so the stack is the same
with every language-model feature switched off.

    run(doc) -> output dict        validate(doc) -> (fields, errors, missing, unknown)
"""
from __future__ import annotations

import json
import re

from . import __version__
from .advice import SSO_DAU_PER_MAU
from .kb import LAYERS, field_specs, load_kb
from .recommender import recommend

PROJECT_TYPES = ("content_site", "web_app", "saas_b2b", "ecommerce", "marketplace", "social", "realtime_collab",
                 "fintech", "healthtech", "data_analytics", "iot", "ai_ml_product", "internal_tool", "gaming",
                 "api_platform", "other")
PLATFORMS = ("web", "android", "ios", "desktop", "api_only")
COMPLIANCE = ("gdpr", "dpdp", "hipaa", "pci_dss", "rbi_localisation", "soc2", "iso27001")
PRIORITY_KEYS = ("cost", "time_to_market", "scalability", "performance", "maintainability", "security")
SECTIONS = ("project", "scale", "team", "budget", "timeline", "infrastructure", "requirements")

# (path, kind, required, default, allowed values). Kinds: text, enum, enums (list of enum), texts (list of text),
# int0 (integer >= 0), int1 (integer >= 1), num0 (number >= 0), bool, latency (integer > 0 or null).
# A required field's default is used only when the field is missing and the rest of the file is valid.
FIELDS = [
    ("project.name", "text", False, None, None),
    ("project.type", "enum", True, "web_app", PROJECT_TYPES),
    ("project.description", "text", False, "", None),
    ("project.platforms", "enums", True, ["web"], PLATFORMS),
    ("scale.users_at_launch", "int0", True, None, None),
    ("scale.users_12_months", "int0", True, None, None),
    ("scale.peak_concurrent_users", "int0", False, None, None),
    ("scale.traffic_pattern", "enum", False, "steady", ("steady", "spiky", "seasonal")),
    ("scale.workload", "enum", False, "balanced", ("read_heavy", "balanced", "write_heavy")),
    ("scale.data_volume_gb_12_months", "num0", False, None, None),
    ("team.size", "int1", True, 3, None),
    ("team.experience", "enum", True, "intermediate", ("beginner", "intermediate", "senior", "mixed")),
    ("team.languages", "texts", True, [], None),
    ("team.has_devops", "bool", False, False, None),
    ("budget.monthly_infra_usd", "num0", True, 100, None),
    ("timeline.mvp_weeks", "int1", True, 12, None),
    ("infrastructure.cloud_preference", "enum", False, "any", ("any", "aws", "gcp", "azure", "none")),
    ("infrastructure.deployment_model", "enum", False, "managed_cloud",
     ("managed_cloud", "self_hosted_cloud_vm", "on_premise", "air_gapped")),
    ("infrastructure.data_residency", "enum", False, "none", ("none", "india", "eu", "us", "other")),
    ("infrastructure.existing_systems", "texts", False, [], None),
    ("requirements.realtime", "bool", False, False, None),
    ("requirements.offline_support", "bool", False, False, None),
    ("requirements.full_text_search", "bool", False, False, None),
    ("requirements.file_media_storage", "bool", False, False, None),
    ("requirements.payments", "bool", False, False, None),
    ("requirements.auth", "enum", False, "none", ("none", "email_password", "social", "phone_otp", "enterprise_sso")),
    ("requirements.multi_tenant", "bool", False, False, None),
    ("requirements.ml_features", "enum", False, "none", ("none", "inference_api", "llm_rag", "training")),
    ("requirements.seo_critical", "bool", False, False, None),
    ("requirements.availability", "enum", False, "99.9", ("99", "99.9", "99.95", "99.99")),
    ("requirements.p95_latency_ms", "latency", False, None, None),
    ("compliance", "enums", False, [], COMPLIANCE),
]
FIELD_PATHS = tuple(f[0] for f in FIELDS) + tuple(f"priorities.{k}" for k in PRIORITY_KEYS)
# What each field means (problem statement table 3.1), for the scenario form in the app.
FIELD_HELP = {
    "project.name": "Free text", "project.type": "The kind of product",
    "project.description": "Free text; read by people, not used to choose the stack",
    "project.platforms": "Client platforms; api_only means no user interface",
    "scale.users_at_launch": "Registered or monthly active users at launch",
    "scale.users_12_months": "Expected users after 12 months; the stack is sized for this",
    "scale.peak_concurrent_users": "Simultaneous users at peak", "scale.traffic_pattern": "How traffic varies",
    "scale.workload": "Mostly reads, balanced, or mostly writes",
    "scale.data_volume_gb_12_months": "Total stored data after 12 months, GB",
    "team.size": "Number of engineers", "team.experience": "The team's experience level",
    "team.languages": "Lower-case names, one per line (python, typescript, java, csharp, go ...)",
    "team.has_devops": "Someone can operate infrastructure",
    "budget.monthly_infra_usd": "Monthly infrastructure and third-party service budget, USD",
    "timeline.mvp_weeks": "Weeks until the first usable release",
    "infrastructure.cloud_preference": "A named cloud is a hard constraint; none rules out AWS, Google Cloud and Azure",
    "infrastructure.deployment_model": "Where the system runs (hard constraint)",
    "infrastructure.data_residency": "Where the data must stay (hard constraint)",
    "infrastructure.existing_systems": "Systems to integrate with or reuse, one per line",
    "requirements.realtime": "Live updates, chat, collaboration, presence",
    "requirements.offline_support": "Must work without connectivity", "requirements.full_text_search": "Search over text content",
    "requirements.file_media_storage": "User uploads: images, video, documents", "requirements.payments": "Takes money from users",
    "requirements.auth": "How users sign in",
    "requirements.multi_tenant": "Several customer organisations share the system",
    "requirements.ml_features": "Machine-learning features", "requirements.seo_critical": "Public pages must rank in search engines",
    "requirements.availability": "Availability target, percent", "requirements.p95_latency_ms": "Target 95th-percentile response time; empty means no target",
    "compliance": "Regulations that apply (hard constraints)",
}
KNOWN_KEYS = {sec: {f[0].split(".", 1)[1] for f in FIELDS if f[0].startswith(sec + ".")} for sec in SECTIONS}
TOP_LEVEL = set(SECTIONS) | {"scenario_id", "compliance", "priorities"}

APP_TYPE = {"content_site": "content_site", "web_app": "saas", "saas_b2b": "saas", "ecommerce": "ecommerce",
            "marketplace": "ecommerce", "social": "social_network", "realtime_collab": "realtime_collab",
            "fintech": "fintech", "healthtech": "healthcare", "data_analytics": "analytics_dashboard",
            "iot": "iot_telemetry", "ai_ml_product": "ml_product", "internal_tool": "internal_tool",
            "gaming": "realtime_collab", "api_platform": "saas", "other": "saas"}
APP_TYPE_NOTES = {
    "marketplace": "a two-sided marketplace (listings, bookings, payouts) is scored like e-commerce",
    "web_app": "a general web application is scored like a SaaS product",
    "api_platform": "an API platform is scored like a SaaS product whose clients call the API",
    "gaming": "a game backend is scored like a realtime collaboration product: shared state over live connections",
    "other": "a project of type 'other' is scored like a SaaS product",
}
# The engine's priorities are a ranked list of at most three; the standard's 1-5 levels are read in this order.
PRIORITY_ENGINE = {"cost": "cost", "time_to_market": "speed", "scalability": "scale", "performance": "performance",
                   "maintainability": "maintainability", "security": "security"}
LANGUAGE_ALIASES = {"js": "javascript", "ts": "typescript", "c#": "csharp", "cs": "csharp", ".net": "csharp",
                    "dotnet": "csharp", "golang": "go", "nodejs": "node", "node.js": "node", "py": "python",
                    "postgresql": "postgres", "html5": "html"}
TOP_PRIORITIES = 3
# Engine notes that name a control of the web app's form, restated for a scenario file.
FORM_WORDS = [("Add 'Data must stay in India' if", "Set infrastructure.data_residency to india if"),
              ("remove 'Data must stay in India' if", "set infrastructure.data_residency to none if"),
              ("tick HIPAA if it applies", "add hipaa to compliance if it applies"),
              ("add 'vector' if you do retrieval", "set requirements.ml_features to llm_rag if you do retrieval")]
# Engine warnings that point at a panel of the web app; the exported output stands alone.
UI_POINTER = re.compile(r"; see the '[^']+' scenario under 'What would change'\.")
# driven_by lists the answers that moved a pick's score by at least this many points (most first, at most
# DRIVERS_SCORED), then at most DRIVERS_RULED fields whose hard constraints ruled rival options out.
DRIVER_MIN_POINTS = 1.0
MAX_NUMBER = 1e12  # larger counts, gigabytes or dollars are typing mistakes, and overflow float arithmetic
MAX_SCENARIOS_PER_FILE = 100  # an array file runs each element; this bounds the work one request can ask for
DRIVERS_SCORED = 4
DRIVERS_RULED = 3
# What happens when an optional field with no fixed default is absent (the others use the default in FIELDS).
ABSENT_NOTE = {"project.name": "the project is called 'Unnamed project'", "project.description": "no description",
               "scale.peak_concurrent_users": "the engine estimates it from the users",
               "scale.data_volume_gb_12_months": "the engine estimates it from the project type and the users",
               "requirements.p95_latency_ms": "no latency target"}

# Free-text existing systems: databases the engine keeps, identity providers it signs in through, and products past
# their vendor's end of support. Each end-of-life row: (pattern, product, end date, source).
EXISTING_DATABASES = [(r"postgres", "postgres"), (r"\bmysql\b|mariadb", "mysql"), (r"mongo", "mongodb"),
                      (r"\bredis\b|valkey", "redis"), (r"sql ?server|mssql|azure sql", "sqlserver"),
                      (r"\boracle\b(?! cloud)", "oracle")]
IDENTITY = [(r"\bentra\b|\bazure ad\b|azure active directory", "Microsoft Entra ID"), (r"\bokta\b", "Okta"),
            (r"google workspace|\bg ?suite\b", "Google Workspace"), (r"\bkeycloak\b", "Keycloak"), (r"\bauth0\b", "Auth0"),
            (r"\bcognito\b", "Amazon Cognito"), (r"active directory|\badfs\b", "Active Directory"),
            (r"\bldap\b", "LDAP directory")]
# How sign-in reaches each one: cloud identity providers speak OpenID Connect; a directory needs a broker.
IDENTITY_HOW = {"Active Directory": "AD FS or Keycloak user federation (LDAP/Kerberos), with OpenID Connect to the app",
                "LDAP directory": "Keycloak user federation over LDAP, with OpenID Connect to the app"}
IDENTITY_DOCS = {"Microsoft Entra ID": "https://learn.microsoft.com/entra/identity-platform/v2-protocols-oidc",
                 "Okta": "https://developer.okta.com/docs/concepts/oauth-openid/",
                 "Google Workspace": "https://developers.google.com/identity/openid-connect/openid-connect"}
# Identity providers reached over the internet, which an air-gapped network cannot reach.
CLOUD_IDENTITY = ("Microsoft Entra ID", "Okta", "Google Workspace", "Auth0", "Amazon Cognito")
# Well-known business systems and the interface the stack integrates through; True marks a cloud-only service.
INTEGRATIONS = [(r"microsoft 365|office 365|\bo365\b|\bteams\b|sharepoint online|exchange online|outlook\.com",
                 "Microsoft Graph API (mail, calendar and Teams notifications, files)", True),
                # Exchange only as the mail server: "NSE stock exchange feed" or "exchange rates API" is not it; Outlook
                # only as the mail program: "weather outlook feed" is not it.
                (r"sharepoint|\b(?:microsoft|ms) outlook\b|\boutlook 20\d\d\b|^\s*outlook\b(?!.*\b(?:weather|forecasts?|markets?)\b)"
                 r"|\b(?:microsoft|ms|on-?prem\w*|hybrid) exchange\b|(?<!stock )\bexchange (?:server|20\d\d)\b"
                 r"|^\s*exchange\b(?!.*\b(?:rates?|market|feed|trading|fix|prices?)\b)",
                 "the SharePoint or Exchange server's REST API", False),
                (r"google workspace|gmail|google drive", "Google Workspace APIs (Gmail, Calendar, Drive)", True),
                (r"salesforce", "Salesforce REST API", True), (r"\bsap\b", "SAP OData services", False),
                (r"slack", "Slack Web API and incoming webhooks", True), (r"tally", "Tally's XML over HTTP interface", False),
                (r"zoho", "Zoho REST APIs", True), (r"jira", "Jira REST API", False)]
END_OF_LIFE = [  # the source page gives each product's end date
    (r"sql ?server ?(2008|2012|2014|2016)\b", "SQL Server {0}", "extended support has ended",
     "https://learn.microsoft.com/lifecycle/products/?terms=sql%20server"),
    (r"windows server ?(2008|2012)\b", "Windows Server {0}", "extended support has ended",
     "https://learn.microsoft.com/lifecycle/products/?terms=windows%20server"),
    (r"centos(?! ?stream) ?(6|7|8)?\b", "CentOS Linux {0}", "it has reached end of life", "https://endoflife.date/centos"),
    (r"python ?(2(\.\d+)?|3\.[0-8])\b", "Python {0}", "it has reached end of life", "https://endoflife.date/python"),
    (r"php ?([5-7](\.\d+)?|8\.[01])\b", "PHP {0}", "it has reached end of life", "https://endoflife.date/php"),
    (r"node(?:\.?js)? ?(1\d|2[013]|[4-9])\b", "Node.js {0}", "it has reached end of life", "https://endoflife.date/nodejs"),
    (r"angularjs|angular ?1\.\d", "AngularJS", "it has reached end of life", "https://endoflife.date/angularjs"),
    (r"mysql ?(5\.\d|8\.0)\b", "MySQL {0}", "it has reached end of life", "https://endoflife.date/mysql"),
    (r"postgres(?:ql)? ?(9\.\d|1[0-3])\b", "PostgreSQL {0}", "it has reached end of life", "https://endoflife.date/postgresql"),
    (r"\.net framework ?(4\.[0-5](?:\.\d)?|4\.6(?:\.1)?|[1-3]\.\d)(?!\.?\d)", ".NET Framework {0}", "support has ended",
     "https://endoflife.date/dotnetfx"),
    (r"\.net (?:core )?([1-3]\.\d|[5-7])(?:\.\d)?\b", ".NET {0}", "support has ended", "https://endoflife.date/dotnet"),
    (r"ubuntu ?(1[0-8]|20)\.04", "Ubuntu {0}.04", "standard support has ended", "https://endoflife.date/ubuntu"),
    (r"internet explorer|\bie ?11\b", "Internet Explorer", "it has been retired", "https://endoflife.date/internet-explorer"),
    (r"adobe flash|flash player", "Adobe Flash", "it has reached end of life", "https://www.adobe.com/products/flashplayer/end-of-life.html"),
    (r"mongodb ?([1-5]\.\d|6\.0)\b", "MongoDB {0}", "it has reached end of life", "https://endoflife.date/mongodb"),
    (r"heroku free", "Heroku free plans", "they have been retired", "https://blog.heroku.com/next-chapter"),
]
# Still supported, but only with security fixes: fine to keep and integrate with; plan the upgrade.
EXTENDED_SUPPORT = [
    (r"sql ?server ?2019\b", "SQL Server 2019", "is in extended support: security updates only, until 8 Jan 2030",
     "https://learn.microsoft.com/lifecycle/products/sql-server-2019"),
    (r"sql ?server ?2017\b", "SQL Server 2017", "is in extended support: security updates only, until 12 Oct 2027",
     "https://learn.microsoft.com/lifecycle/products/sql-server-2017"),
]

REGION = {  # where the data stays under a residency rule, per cloud
    ("aws", "india"): "ap-south-1 (Mumbai)", ("gcp", "india"): "asia-south1 (Mumbai)",
    ("azure", "india"): "Central India (Pune)", ("aws", "eu"): "eu-central-1 (Frankfurt)",
    ("gcp", "eu"): "europe-west3 (Frankfurt)", ("azure", "eu"): "Germany West Central (Frankfurt)",
    ("aws", "us"): "us-east-1 (N. Virginia)", ("gcp", "us"): "us-central1 (Iowa)", ("azure", "us"): "East US",
    ("vercel", "india"): "bom1 (Mumbai) for functions", ("digitalocean", "india"): "BLR1 (Bangalore)",
    ("cloudflare", "india"): "Data Localization Suite with an India region",
    ("digitalocean", "eu"): "FRA1 (Frankfurt) or AMS3 (Amsterdam)", ("digitalocean", "us"): "NYC3 (New York) or SFO3 (San Francisco)",
    ("vercel", "eu"): "fra1 (Frankfurt) for functions", ("vercel", "us"): "iad1 (Washington, D.C.) for functions",
    ("flyio", "eu"): "fra (Frankfurt)", ("flyio", "us"): "iad (Ashburn, Virginia)",
    ("render", "eu"): "Frankfurt", ("render", "us"): "Oregon or Ohio",
    ("railway", "eu"): "EU West (Amsterdam)", ("railway", "us"): "US East (Virginia)",
    ("hetzner", "eu"): "Falkenstein, Nuremberg or Helsinki", ("hetzner", "us"): "Ashburn or Hillsboro",
    ("cloudflare", "eu"): "Data Localization Suite with the EU region",
    ("netlify", "us"): "US (deploys, storage and logs stay with Netlify's US providers)",
}
STYLE = [("Static site", "static"), ("BaaS-first, self-hosted", "other"), ("BaaS-first", "serverless"),
         ("Serverless", "serverless"), ("Service-oriented", "service_oriented"), ("Modular monolith", "modular_monolith"),
         ("Microservices", "microservices"), ("Monolith", "monolith")]
SERVICE_LAYER = {"Cache": "cache", "Realtime": "realtime", "Background jobs": "queue", "Ingestion buffer": "queue",
                 "Search": "search", "Payments": "payments", "Static frontend": "cdn", "CDN": "cdn",
                 "Media delivery": "cdn", "Object storage": "storage", "Authentication": "auth",
                 "Enterprise SSO": "auth", "Phone login (SMS OTP)": "auth", "Model serving": "ml",
                 "Vector search": "ml", "Observability": "observability"}
SERVICE_FIELDS = {
    "cache": ["scale.workload", "requirements.p95_latency_ms", "scale.users_12_months"],
    "realtime": ["requirements.realtime", "scale.peak_concurrent_users"],
    "queue": ["requirements.file_media_storage", "scale.workload"],
    "search": ["requirements.full_text_search", "scale.data_volume_gb_12_months"],
    "payments": ["requirements.payments", "compliance"],
    "cdn": ["project.platforms", "scale.users_12_months"],
    "storage": ["requirements.file_media_storage"],
    "auth": ["requirements.auth"],
    "ml": ["requirements.ml_features"],
    "observability": ["requirements.availability"],
    "other": ["project.type"],
}
OTHER_FIELDS = {"Offline sync": ["requirements.offline_support"], "Push notifications": ["project.platforms"],
                "Audit & security": ["compliance"], "Hybrid split": ["infrastructure.deployment_model"],
                "Analytics": ["scale.workload", "project.type"],
                "Collaboration sync": ["project.type", "requirements.realtime"], "Desktop app": ["project.platforms"],
                "Notifications": ["project.platforms", "infrastructure.deployment_model"]}
# Engine answers and the standard fields that stand behind them when no mapping recorded a more specific one.
ENGINE_FIELDS = {"dau": ["scale.users_12_months"], "peak_rps": ["scale.users_12_months", "scale.traffic_pattern"],
                 "data_volume_gb": ["scale.data_volume_gb_12_months"], "data_growth_gb_month": ["scale.data_volume_gb_12_months"],
                 "data_shapes": ["project.type"], "consistency": ["project.type"], "architecture": ["team.size"],
                 "regions": ["infrastructure.data_residency"], "cacheable_share": ["scale.workload"]}


def _get(doc: dict, path: str):
    node = doc
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) or isinstance(v, float) and v.is_integer()


def _check(kind: str, value, allowed) -> tuple[object, str | None]:
    """The value converted to its plain Python form, or an error message."""
    if kind == "text":
        return (value, None) if isinstance(value, str) else (None, "must be a string")
    if kind == "bool":
        return (value, None) if isinstance(value, bool) else (None, "must be true or false")
    if kind == "enum":
        if not isinstance(value, str):
            return None, f"must be a string, one of: {', '.join(allowed)}"
        return (value, None) if value in allowed else (None, f"'{value}' is not one of: {', '.join(allowed)}")
    if kind in ("enums", "texts"):
        if not isinstance(value, list):
            return None, "must be a list"
        if any(not isinstance(v, str) for v in value):
            return None, "every item must be a string"
        if kind == "enums":
            bad = [v for v in value if v not in allowed]
            if bad:
                return None, f"unknown value(s) {', '.join(repr(b) for b in bad)}; allowed: {', '.join(allowed)}"
        return list(dict.fromkeys(value)), None
    if kind == "latency":
        if not _is_int(value):
            return None, "must be a whole number of milliseconds greater than 0, or null"
        return (int(value), None) if value > 0 else (None, "must be greater than 0 (or null for no target)")
    lo = {"int0": 0, "int1": 1, "num0": 0}[kind]
    number_ok = _is_int(value) if kind != "num0" else isinstance(value, (int, float)) and not isinstance(value, bool)
    if not number_ok:
        return None, "must be a whole number" if kind != "num0" else "must be a number"
    if value != value or value in (float("inf"), float("-inf")):
        return None, "must be a finite number"
    if value < lo:
        return None, f"must be {lo} or more"
    if value > MAX_NUMBER:
        return None, f"must be at most {MAX_NUMBER:,.0f}"
    return (int(value) if kind != "num0" else value), None


def validate(doc) -> tuple[dict, list[dict], list[str], list[str]]:
    """Every standard field read and checked: (fields by path, validation errors, missing required paths,
    unknown keys). Fields missing from the file get their default, so `fields` is complete."""
    if not isinstance(doc, dict):
        return {}, [{"field": "(file)", "message": "The scenario must be a JSON object"}], [], []
    errors, missing, unknown, fields = [], [], [], {}
    for sec in SECTIONS + ("priorities",):
        if sec in doc and not isinstance(doc[sec], dict):
            errors.append({"field": sec, "message": "must be an object"})
        elif isinstance(doc.get(sec), dict):
            known = KNOWN_KEYS.get(sec, set(PRIORITY_KEYS))
            unknown += [f"{sec}.{k}" for k in doc[sec] if k not in known]
    unknown += [k for k in doc if k not in TOP_LEVEL]
    sid = doc.get("scenario_id")
    if sid is not None and (isinstance(sid, bool) or not isinstance(sid, (str, int))):
        errors.append({"field": "scenario_id", "message": "must be a string"})
    for path, kind, required, default, allowed in FIELDS:
        present, value = _get(doc, path)
        if not present or value is None:
            if required:
                missing.append(path)
            fields[path] = default
            continue
        value, err = _check(kind, value, allowed)
        if err:
            errors.append({"field": path, "message": err})
        elif path == "project.platforms" and not value:
            errors.append({"field": path, "message": "must list at least one platform"})
        else:
            fields[path] = value
    prio = doc.get("priorities") if isinstance(doc.get("priorities"), dict) else {}
    for key in PRIORITY_KEYS:
        value = prio.get(key)
        if value is None:
            fields[f"priorities.{key}"] = 3
        elif not _is_int(value) or not 1 <= value <= 5:
            errors.append({"field": f"priorities.{key}", "message": "must be a whole number from 1 to 5"})
        else:
            fields[f"priorities.{key}"] = int(value)
    for key in unknown:
        if key.startswith("priorities."):
            errors.append({"field": key, "message": f"unknown priority; allowed keys: {', '.join(PRIORITY_KEYS)}"})
    unknown = [k for k in unknown if not k.startswith("priorities.")]
    if not errors:
        if fields["scale.users_at_launch"] is None and fields["scale.users_12_months"] is None:
            fields["scale.users_at_launch"] = fields["scale.users_12_months"] = 1000
        fields["scale.users_at_launch"] = _first(fields["scale.users_at_launch"], fields["scale.users_12_months"])
        fields["scale.users_12_months"] = _first(fields["scale.users_12_months"], fields["scale.users_at_launch"])
    return fields, errors, missing, unknown


def _first(*values):
    return next(v for v in values if v is not None)


def _systems(texts: list[str]) -> tuple[list[str], list[str], list[tuple[str, str, str]], list[str]]:
    """Free-text existing systems: (engine database ids, identity providers, end-of-life items, the rest)."""
    dbs, idps, eol, other = [], [], [], []
    for text in texts:
        low = text.lower()
        hit = False
        for pattern, dbid in EXISTING_DATABASES:
            if re.search(pattern, low) and dbid not in dbs:
                dbs.append(dbid)
                hit = True
        for pattern, name in IDENTITY:
            if re.search(pattern, low) and name not in idps:
                idps.append(name)
                hit = True
        for pattern, product, status, source in END_OF_LIFE:  # one text can name several products
            m = re.search(pattern, low)
            if m:
                name = product.format(*[g or "" for g in m.groups()]).strip()
                if not any(e[1] == name for e in eol):
                    eol.append((text, name, f"{status} ({source})"))
        if not hit:
            other.append(text)
    return dbs, idps, eol, other


def to_answers(f: dict) -> tuple[dict, dict, list[str], list[dict]]:
    """Map checked standard fields to engine answers: (answers, standard paths behind each answer,
    interpretation notes, extra warnings)."""
    a, origin, notes, warns = {}, {}, [], []

    def put(key, value, *paths):
        a[key] = value
        origin[key] = list(dict.fromkeys(origin.get(key, []) + list(paths)))

    ptype, platforms = f["project.type"], f["project.platforms"]
    app = APP_TYPE[ptype]
    if ptype == "other" and "web" not in platforms and {"android", "ios"} & set(platforms):
        app = "mobile_first"
        notes.append("project.type 'other' with only phone platforms is scored as a mobile-first app")
    elif ptype in APP_TYPE_NOTES:
        notes.append(f"project.type '{ptype}': {APP_TYPE_NOTES[ptype]}")
    put("app_type", app, "project.type")
    put("project_name", (f["project.name"] or "Unnamed project")[:120], "project.name")
    if f["project.description"]:
        notes.append("project.description is not parsed for a scenario file: every choice comes from the structured "
                     "fields, so wording cannot move the stack (in the app, the description reader only suggests "
                     "fields for you to confirm)")
    put("platforms", list(platforms), "project.platforms")

    auth = f["requirements.auth"]
    # Each engine answer records only the standard fields that set its values, so driven_by and warning fields stay
    # specific (no answer set: the fields that kept it empty).
    actions = [(a, path) for a, path, on in (
        ("read", None, True), ("sign_in", "requirements.auth", auth != "none"),
        ("post", "requirements.auth" if auth != "none" else "requirements.file_media_storage"
         if f["requirements.file_media_storage"] else "requirements.offline_support"
         if f["requirements.offline_support"] else "scale.workload",
         auth != "none" or f["scale.workload"] != "read_heavy" or f["requirements.file_media_storage"]
         or f["requirements.offline_support"]),
        ("pay", "requirements.payments", f["requirements.payments"])) if on]
    put("user_actions", [a for a, _ in actions],
        *([p for _, p in actions if p] or ["requirements.auth", "scale.workload"]))
    if "post" not in [a for a, _ in actions]:
        notes.append("No sign-in and a read-heavy workload: visitors only read, so pre-built static pages are allowed")

    workloads = [(w, path) for w, path, on in (
        ("text_search", "requirements.full_text_search", f["requirements.full_text_search"]),
        ("media_uploads", "requirements.file_media_storage", f["requirements.file_media_storage"]),
        ("phone_otp", "requirements.auth", auth == "phone_otp")) if on]
    put("special_workloads", [w for w, _ in workloads],
        *([p for _, p in workloads] or ["requirements.full_text_search", "requirements.file_media_storage"]))
    ml = f["requirements.ml_features"]
    put("ml_features", ml, "requirements.ml_features")
    if ml == "training":
        put("background_work", "gpu", "requirements.ml_features")
    if ml == "llm_rag":
        put("data_shapes", ["relational", "vector"], "requirements.ml_features", "project.type")
    put("tenancy", "shared" if f["requirements.multi_tenant"] else "single", "requirements.multi_tenant")

    users12, launch = f["scale.users_12_months"], f["scale.users_at_launch"]
    sized, sized_path = (users12, "scale.users_12_months") if users12 >= launch else (launch, "scale.users_at_launch")
    dau = int(round(sized * SSO_DAU_PER_MAU))
    put("dau", dau, sized_path)
    notes.append(f"Sized for {sized_path}: {sized:,} users, about {dau:,} active on a day ({SSO_DAU_PER_MAU:.0%} "
                 "daily-to-monthly ratio); " + (f"scale.users_at_launch ({launch:,}) is the starting point" if sized_path ==
                 "scale.users_12_months" else f"it is larger than scale.users_12_months ({users12:,}), so the stack is "
                 "sized for the launch"))
    if f["scale.peak_concurrent_users"] is not None:
        put("peak_concurrent", f["scale.peak_concurrent_users"], "scale.peak_concurrent_users")
    pattern = f["scale.traffic_pattern"]
    put("traffic_pattern", "spiky" if pattern == "seasonal" else pattern, "scale.traffic_pattern")
    if pattern == "seasonal":
        notes.append("Seasonal traffic is planned like spiky traffic: capacity must stretch to the season's peak")
    put("read_write", f["scale.workload"], "scale.workload")
    if f["scale.data_volume_gb_12_months"] is not None:
        put("data_volume_gb", f["scale.data_volume_gb_12_months"], "scale.data_volume_gb_12_months")
        put("data_growth_gb_month", 0, "scale.data_volume_gb_12_months")

    put("realtime", ("core" if ptype in ("realtime_collab", "gaming") else "some") if f["requirements.realtime"] else "none",
        "requirements.realtime", "project.type")
    if f["requirements.p95_latency_ms"] is not None:
        put("latency_target_ms", f["requirements.p95_latency_ms"], "requirements.p95_latency_ms")
    else:
        notes.append("requirements.p95_latency_ms is null: no latency target, so the engine plans for its 300 ms default")
    put("seo", "critical" if f["requirements.seo_critical"] else "none", "requirements.seo_critical")
    put("offline", f["requirements.offline_support"], "requirements.offline_support")
    put("availability", {"99": "99.0"}.get(f["requirements.availability"], f["requirements.availability"]),
        "requirements.availability")

    specs = field_specs()
    known_skills = {o["value"] for o in specs["team_skills"]["options"]}
    skills, ignored = [], []
    for lang in f["team.languages"]:
        name = LANGUAGE_ALIASES.get(lang.strip().lower(), lang.strip().lower())
        (skills if name in known_skills else ignored).append(name)
    put("team_skills", list(dict.fromkeys(skills)), "team.languages")
    if ignored:
        notes.append(f"team.languages not in the knowledge base, so they move no score: {', '.join(ignored)}")
    put("team_size", f["team.size"], "team.size")
    put("team_experience", f["team.experience"], "team.experience")
    put("has_devops", f["team.has_devops"], "team.has_devops")
    put("timeline_weeks", f["timeline.mvp_weeks"], "timeline.mvp_weeks")
    put("budget_monthly", f["budget.monthly_infra_usd"], "budget.monthly_infra_usd")
    put("currency", "USD", "budget.monthly_infra_usd")

    deploy, cloud = f["infrastructure.deployment_model"], f["infrastructure.cloud_preference"]
    put("deployment", {"managed_cloud": "cloud", "self_hosted_cloud_vm": "cloud", "on_premise": "on_prem",
                       "air_gapped": "on_prem"}[deploy], "infrastructure.deployment_model")
    if deploy == "self_hosted_cloud_vm":
        put("self_managed", True, "infrastructure.deployment_model")
        notes.append("self_hosted_cloud_vm: the team runs every server on cloud VMs, so managed-only platforms "
                     "(serverless functions, managed backends, cloud-only databases) are ruled out")
    if deploy == "air_gapped":
        put("air_gapped", True, "infrastructure.deployment_model")
    onprem = deploy in ("on_premise", "air_gapped")
    if cloud in ("aws", "gcp", "azure") and onprem:
        warns.append(_std_warn("CLOUD_VS_DEPLOYMENT", "critical",
                               f"cloud_preference '{cloud}' and deployment_model '{deploy}' cannot both hold: a public cloud "
                               "is not your own data centre. The deployment model is kept and the cloud preference is "
                               "relaxed; AWS Outposts, Google Distributed Cloud or Azure Stack would be the way to keep both.",
                               ["infrastructure.cloud_preference", "infrastructure.deployment_model"]))
        notes.append(f"Relaxed: infrastructure.cloud_preference '{cloud}' (conflicts with deployment_model '{deploy}')")
        cloud = "any"
    if cloud in ("aws", "gcp", "azure"):
        put("cloud_preference", cloud, "infrastructure.cloud_preference")
        put("cloud_required", True, "infrastructure.cloud_preference")
    elif cloud == "any" or onprem:
        put("cloud_preference", "none", "infrastructure.cloud_preference")  # the engine's word for no preference
    elif cloud == "none":
        put("cloud_preference", "no_hyperscaler", "infrastructure.cloud_preference")
        put("cloud_required", True, "infrastructure.cloud_preference")
        notes.append("cloud_preference 'none' is read as: no AWS, Google Cloud or Azure account; independent "
                     "hosts and your own servers stay allowed")

    residency, compliance = f["infrastructure.data_residency"], list(f["compliance"])
    comp = [c for c in compliance if c in ("gdpr", "dpdp", "hipaa", "pci_dss", "soc2", "iso27001")]
    rules = {"india": "data_residency_india", "eu": "data_residency_eu", "us": "data_residency_us"}
    if residency in rules:
        comp.append(rules[residency])
        put("regions", [{"india": "india", "eu": "europe", "us": "north_america"}[residency]],
            "infrastructure.data_residency")
    if "rbi_localisation" in compliance:
        comp.append("data_residency_india")
        notes.append("rbi_localisation: RBI's 2018 directive on storage of payment system data requires payment data "
                     "to be stored only in India, so every store must have an Indian region")
        if residency in ("eu", "us"):
            notes.append(f"Relaxed: infrastructure.data_residency '{residency}' for payment data (rbi_localisation keeps "
                         "it in India)")
            warns.append(_std_warn("RESIDENCY_CONFLICT", "critical",
                                   f"rbi_localisation keeps payment data in India, but data_residency is '{residency}'. "
                                   "One copy of the data cannot sit only in both places. Only providers with both regions "
                                   f"remain, and the stack is placed in India for RBI; data_residency '{residency}' is "
                                   f"relaxed for the payment data, so keep any other data that must stay in the "
                                   f"{residency.upper()} in a separate deployment there.",
                                   ["compliance", "infrastructure.data_residency"]))
    if "gdpr" in compliance:
        notes.append("gdpr: sign a data processing agreement (DPA) with every vendor that stores or processes personal "
                     "data (host, database, sign-in, payments, monitoring); "
                     + ("infrastructure.data_residency eu keeps the data in EU regions" if residency == "eu" else
                        "with no EU residency stated, personal data may leave the EU only under an adequacy decision or "
                        "the vendor's Standard Contractual Clauses (GDPR Chapter V); set infrastructure.data_residency "
                        "to eu to keep it in EU regions"))
    if "iso27001" in compliance:
        notes.append("iso27001: only hosts and managed services (backend-as-a-service, managed-only databases) that "
                     "publish ISO/IEC 27001 certification are kept")
    if residency == "other":
        warns.append(_std_warn("RESIDENCY_UNVERIFIED", "warning",
                               "data_residency 'other' names no country, so the engine cannot check provider regions. "
                               "Pick a region inside the required country before you deploy; AWS, Google Cloud and Azure "
                               "cover the most countries.", ["infrastructure.data_residency"]))
    put("compliance", list(dict.fromkeys(comp)), "compliance", "infrastructure.data_residency")
    put("enterprise_sso", auth == "enterprise_sso", "requirements.auth")

    levels = [(f[f"priorities.{k}"], -i, k) for i, k in enumerate(PRIORITY_KEYS)]
    ranked = [k for lvl, _, k in sorted(levels, reverse=True) if lvl >= 4]
    put("priorities", [PRIORITY_ENGINE[k] for k in ranked[:TOP_PRIORITIES]],
        *[f"priorities.{k}" for k in ranked[:TOP_PRIORITIES]])
    if ranked:
        kept = ", ".join(f"{k} ({f[f'priorities.{k}']})" for k in ranked[:TOP_PRIORITIES])
        notes.append(f"Priorities rated 4 or 5 raise their criteria's weights, strongest first: {kept}"
                     + (f"; also rated high but past the top {TOP_PRIORITIES}: {', '.join(ranked[TOP_PRIORITIES:])}"
                        if ranked[TOP_PRIORITIES:] else ""))
    low = [k for k in PRIORITY_KEYS if f[f"priorities.{k}"] <= 2]
    if low:
        notes.append(f"Priorities rated 1 or 2 ({', '.join(low)}) keep their criteria at the baseline weight")

    dbs, idps, eol, other = _systems(f["infrastructure.existing_systems"])
    kept = {o["value"] for o in specs["existing_systems"]["options"]}
    put("existing_systems", [d for d in dbs if d in kept], "infrastructure.existing_systems")
    for text, product, status in eol:
        warns.append(_std_warn("EOL_EXISTING_SYSTEM", "warning",
                               f"'{text}': {product} is past its vendor's support: {status}. Integrate with it through an "
                               "API or a migration, never build new parts on it; plan the upgrade before go-live.",
                               ["infrastructure.existing_systems"]))
    for text in f["infrastructure.existing_systems"]:
        for pattern, product, status, source in EXTENDED_SUPPORT:
            if re.search(pattern, text.lower()):
                warns.append(_std_warn("EXISTING_SYSTEM_EXTENDED_SUPPORT", "info",
                                       f"'{text}': {product} {status} ({source}). Keeping it is fine; schedule the "
                                       "upgrade before that date.", ["infrastructure.existing_systems"]))
    unreachable = "an air-gapped network cannot reach it"
    for name in idps:
        if name in _cloud_only_identity(idps, f):
            warns.append(_std_warn("EXISTING_SYSTEM_UNREACHABLE", "warning",
                                   f"{name} is a cloud identity provider, and {unreachable}. Sign-in uses a directory "
                                   f"inside the network instead; if {name} is synchronised from an on-premises Active "
                                   "Directory, federate that directory.",
                                   ["infrastructure.existing_systems", "infrastructure.deployment_model"]))
            continue
        notes.append(f"Existing identity provider {name}: sign-in reuses it through "
                     f"{IDENTITY_HOW.get(name, 'OpenID Connect or SAML')} instead of a new user store")
    names = {it["id"]: it["name"] for it in load_kb()["database"]}
    for text in f["infrastructure.existing_systems"]:
        dbid = next((d for pattern, d in EXISTING_DATABASES if re.search(pattern, text.lower())), None)
        if dbid in names:
            notes.append(f"Existing database '{text}': {names[dbid]} is weighed with a bonus for keeping it; if it stays "
                         "the pick, move its data to the recommended offering with the vendor's migration tool, or reach "
                         "it over a private link (site-to-site VPN) while it stays where it is")
    for text in other:
        how, cloud_only = next(((api, c) for pattern, api, c in INTEGRATIONS if re.search(pattern, text.lower())),
                               ("its API", False))
        if cloud_only and deploy == "air_gapped":
            warns.append(_std_warn("EXISTING_SYSTEM_UNREACHABLE", "warning",
                                   f"'{text}' is a cloud service, and {unreachable} through {how}. Move its data across "
                                   "the air gap with the site's approved transfer process, or keep that integration on a "
                                   "connected system outside the network.",
                                   ["infrastructure.existing_systems", "infrastructure.deployment_model"]))
            continue
        notes.append(f"Existing system '{text}': integrated through {how}; it stays the system of record for its own data")
    return a, origin, notes, warns


def _cloud_only_identity(idps: list[str], f: dict) -> list[str]:
    """The existing identity providers the network cannot reach: the cloud ones, when the site is air-gapped."""
    return [i for i in idps if i in CLOUD_IDENTITY] if f["infrastructure.deployment_model"] == "air_gapped" else []


def _std_warn(code: str, severity: str, message: str, fields: list[str]) -> dict:
    return {"code": code, "severity": severity, "message": message, "fields": fields}


def _paths(keys, origin: dict) -> list[str]:
    out = []
    for key in keys:
        out += origin.get(key) or ENGINE_FIELDS.get(key, [])
    return list(dict.fromkeys(p for p in out if p in FIELD_PATHS))


def _region(provider: str, f: dict) -> str | None:
    res = f["infrastructure.data_residency"]
    if "rbi_localisation" in f["compliance"]:
        res = "india"
    return REGION.get((provider, res))


def _component(layer: str, sl: dict, origin: dict, f: dict, result: dict) -> dict:
    pick, ex = sl["pick"], sl["explanation"]
    choice, extra = pick["name"], ""
    item = load_kb()["index"].get(pick["id"], {})
    if item.get("kind") == "none" or (layer == "database" and item.get("static_only")):
        choice, extra = "None", ""  # the section 4 spelling for a layer that is not needed; the name says why
        ex = dict(ex, paragraph=f"{pick['name']}. {ex.get('paragraph') or ''}".strip())
    if layer == "frontend" and result.get("companion"):
        comp = result["companion"]
        apps = "/".join(x for x in ("Android", "iOS") if x.lower() in f["project.platforms"])
        choice += f" + {comp['name']} for the {apps} app"
        extra = f" {comp['why']}"
    if layer == "database" and sl.get("managed_offering") and choice != "None":
        choice += f": {sl['managed_offering']}"
    if layer == "hosting":
        api = sl.get("api_host")
        if api:
            choice += f" for the frontend + {api['name']} for the API"
        provider = load_kb()["index"].get((api or {}).get("id") or pick["id"], {}).get("provider", "")
        region = _region(provider, f)
        if region:
            choice += f", region {region}"
    # The answers that added the most points to this pick, then the hard constraints that ruled rivals out.
    scored = sorted((c for c in ex.get("input_contributions", []) if c["points"] >= DRIVER_MIN_POINTS
                     and c["input"] not in ("baseline", "clamp")), key=lambda c: -c["points"])
    ruled = _paths([c for x in sl.get("excluded", []) for c in x.get("constraints", [])], origin)
    driven_by = list(dict.fromkeys(_paths([c["input"] for c in scored], origin)[:DRIVERS_SCORED]
                                   + ruled[:DRIVERS_RULED])) or ["project.type"]
    alternatives = [{"choice": w["name"], "why_not": w["text"]} for w in sl.get("why_not", [])][:3]
    companion = result["companion"]["name"] if layer == "frontend" and result.get("companion") else None
    alternatives = [x for x in alternatives if x["choice"] != companion]
    taken = {pick["name"], companion} | {x["choice"] for x in alternatives}
    for x in sl.get("excluded", []):
        if len(alternatives) >= 4:
            break
        if x["name"] not in taken:
            alternatives.append({"choice": x["name"], "why_not": "Ruled out: " + "; ".join(x["reasons"][:2])})
    if not alternatives:
        alternatives = [{"choice": r["name"], "why_not": f"Scores {r['score']:.1f} against the pick's {pick['score']:.1f}"}
                        for r in sl.get("ranking", []) if r["name"] != pick["name"]][:1]
    return {"choice": choice, "justification": (ex.get("paragraph") or " ".join(ex.get("why", []))) + extra,
            "driven_by": driven_by, "alternatives": alternatives,
            "tradeoffs": list(dict.fromkeys(ex.get("tradeoffs", []) + ex.get("risks", [])))}


def _supporting(result: dict, f: dict) -> list[dict]:
    out = []
    services = [(s, False) for s in result.get("supporting_services", [])] + \
               [(s, True) for s in result.get("deferred_services", [])]
    for s, deferred in services:
        if s["role"] == "Collaboration sync" and f["project.type"] == "gaming":
            continue  # a game server owns the state; merging documents (CRDTs) is for co-editing tools
        if s["role"] == "Search" and not f["requirements.full_text_search"]:
            continue  # the engine adds search for shops and content sites; the scenario says it needs none
        layer = SERVICE_LAYER.get(s["role"], "other")
        fields = OTHER_FIELDS.get(s["role"]) or SERVICE_FIELDS[layer]
        if f["infrastructure.data_residency"] != "none" and layer in ("storage", "auth", "cache", "observability", "ml"):
            fields = fields + ["infrastructure.data_residency"]
        tradeoffs = []
        if s.get("system"):
            tradeoffs.append(f"One more system to run: {s['system']}")
        if s.get("trigger"):
            tradeoffs.append(f"Add it {s['trigger']}" if deferred else f"Can wait until {s['trigger']}")
        why = s["why"] + (" Deferred: the team's operations budget keeps it out of the first release." if deferred else "")
        out.append({"layer": layer, "choice": s["name"], "justification": why, "driven_by": fields,
                    "alternatives": [], "tradeoffs": tradeoffs, "source": s.get("source"), "role": s["role"]})
    idps = _systems(f["infrastructure.existing_systems"])[1]
    idps = [i for i in idps if i not in _cloud_only_identity(idps, f)]
    if idps and f["requirements.auth"] != "none":
        replaced = [x for x in out if x["role"] in ("Authentication", "Enterprise SSO")]
        first = out.index(replaced[0]) if replaced else len(out)
        out = [x for x in out if x not in replaced]
        out.insert(first, _reuse_identity(idps[0], replaced))
    for x in out:
        x.pop("role", None)
    out.append(_ci_cd(f))
    return out


def _reuse_identity(idp: str, replaced: list[dict]) -> dict:
    alts = [{"choice": x["choice"], "why_not": f"A second identity system to run beside {idp}, which already holds "
             "the users"} for x in replaced][:2]
    return {"layer": "auth", "choice": f"{idp} (existing), signed in through {IDENTITY_HOW.get(idp, 'OpenID Connect')}",
            "justification": f"infrastructure.existing_systems lists {idp}: users sign in with the accounts it already "
                             "manages, so there is no new user store, MFA and password rules come from it, and "
                             "removing someone there removes their access here.",
            "driven_by": ["infrastructure.existing_systems", "requirements.auth"], "alternatives": alts,
            "tradeoffs": [f"Sign-in depends on {idp} being reachable"],
            "source": IDENTITY_DOCS.get(idp, "https://openid.net/developers/how-connect-works/")}


def _ci_cd(f: dict) -> dict:
    deploy = f["infrastructure.deployment_model"]
    if deploy in ("on_premise", "air_gapped"):
        choice, alt, why = ("GitLab CI/CD (self-managed GitLab on your servers)", "Jenkins",
                            "Builds and deploys run inside your network; an air-gapped site needs a runner and an "
                            "artefact registry that never reach the internet.")
    else:
        choice, alt, why = ("GitHub Actions", "GitLab CI/CD",
                            "Every push runs the tests and deploys the same way; hosted runners mean no build server "
                            "to operate.")
    return {"layer": "ci_cd", "choice": choice, "justification": why,
            "driven_by": ["infrastructure.deployment_model", "team.size"],
            "alternatives": [{"choice": alt, "why_not": "Equivalent pipelines; one more tool to learn for no gain here"}],
            "tradeoffs": ["Pipeline minutes are metered on hosted runners"] if deploy not in ("on_premise", "air_gapped")
            else ["You operate the CI server and its runners"],
            "source": "https://docs.github.com/actions" if deploy not in ("on_premise", "air_gapped")
            else "https://docs.gitlab.com/ci/"}


def _style(result: dict) -> str:
    text = result.get("architecture", {}).get("style", "")
    return next((v for k, v in STYLE if text.startswith(k)), "other")


def _warnings(result: dict, origin: dict) -> list[dict]:
    out = []
    for w in result.get("warnings", []):
        message = " ".join(x.strip() for x in (w.get("title", "") + ".", w.get("detail", ""), w.get("resolution", "")) if x)
        message = UI_POINTER.sub(".", message)  # the output file has no app panels to point at
        for app_words, file_words in FORM_WORDS:
            message = message.replace(app_words, file_words)
        out.append(_std_warn(w["code"], w["severity"], message, _paths(w.get("fields", []), origin)))
    return out


def _assumptions(result: dict) -> list[str]:
    out = []
    for a in result.get("assumptions", []):
        label = a.get("label") or a.get("field", "")
        reason = a.get("reason", "")
        for app_words, file_words in FORM_WORDS:
            reason = reason.replace(app_words, file_words)
        out.append(f"{label}: {reason}".strip())
    return out


def _cost(result: dict, f: dict) -> dict:
    c = result["cost"]
    lines = [f"{x['component']}: ${x['low']:,.0f}-{x['high']:,.0f} ({x['basis']})" for x in c.get("lines", [])]
    budget = f["budget.monthly_infra_usd"]
    return {"min": round(c["total_low"]), "max": round(c["total_high"]),
            "assumptions": [c.get("note", ""), f"Scale tier: {c.get('tier', '')}",
                            f"Budget check: ${budget:,.0f}/month stated, status '{c.get('status', '')}'"] + lines}


def _summary(result: dict, stack: dict, style: str, cost: dict) -> str:
    names = {l: re.split(r" \(|,|: ", stack[l]["choice"])[0] for l in LAYERS}
    roles = {"frontend": "on the frontend", "backend": "for the backend", "database": "for data"}
    used = [f"{names[l]} {role}" for l, role in roles.items() if names[l] != "None"]
    unused = [l for l in roles if names[l] == "None"]
    first = (f"A {style.replace('_', ' ')} build: {', '.join(used)}, hosted on {names['hosting']}"
             + (f"; no {' or '.join(unused)} is needed" if unused else "") + ".")
    money = f"${cost['min']:,}" if cost["min"] == cost["max"] else f"${cost['min']:,}-{cost['max']:,}"
    why = result.get("architecture", {}).get("why", "")
    return f"{first} About {money} a month. {why.split('. ')[0].rstrip('.')}."


def run_text(text: str, capped: bool = True) -> dict | list[dict]:
    """run() on the text of a scenario file. A JSON array holds several scenarios (the organisers share the public ones
    that way), and gives a list with one output per element. Capped (the API), an array longer than
    MAX_SCENARIOS_PER_FILE is one invalid_input result instead; the command line runs any length. Text that is not
    JSON is one invalid_input result, not an exception."""
    try:
        doc = json.loads(text)
    except (ValueError, RecursionError) as e:  # RecursionError: arrays or objects nested past Python's limit
        return _file_error(f"not valid JSON: {e}" if isinstance(e, ValueError) else "nested too deeply to be a scenario file")
    if isinstance(doc, list) and doc:
        if capped and len(doc) > MAX_SCENARIOS_PER_FILE:
            return _file_error(f"holds {len(doc):,} scenarios; one file runs at most {MAX_SCENARIOS_PER_FILE}")
        return [run(x) for x in doc]
    return run(doc)


def _file_error(message: str) -> dict:
    out = run(None)
    out["validation_errors"] = [{"field": "(file)", "message": message}]
    return out


def run(doc) -> dict:
    """Validate a standard scenario, recommend, and return the section 4 output. Never raises on bad input."""
    sid = doc.get("scenario_id") if isinstance(doc, dict) else None
    head = {"scenario_id": sid if isinstance(sid, (str, int)) else None, "engine_version": __version__}
    fields, errors, missing, unknown = validate(doc)
    if errors:
        errors += [{"field": m, "message": "required field is missing"} for m in missing]
        return dict(head, status="invalid_input", summary="The scenario has invalid fields; no stack was produced.",
                    architecture_style=None, stack=None, estimated_monthly_cost_usd=None, warnings=[],
                    assumptions=[], validation_errors=errors)

    answers, origin, notes, extra = to_answers(fields)
    result = recommend(answers, with_counterfactuals=False)
    warnings = [_std_warn("MISSING_REQUIRED_FIELD", "warning",
                          f"{m} is required but missing; the documented default "
                          f"{fields[m]!r} was used (listed in assumptions).", [m]) for m in missing]
    warnings += [_std_warn("UNKNOWN_FIELD", "info", f"{k} is not part of the standard schema and was ignored.", [k])
                 for k in unknown]
    warnings += extra + _warnings(result, origin)
    absent = [path for path, _kind, required, *_ in FIELDS if not required and _get(doc, path)[1] is None
              and not (path == "requirements.p95_latency_ms" and _get(doc, path)[0])]
    absent += [f"priorities.{k}" for k in PRIORITY_KEYS if (doc.get("priorities") or {}).get(k) is None]
    assumptions = ([f"{m} missing: used {fields[m]!r}" for m in missing]
                   + [f"{a} not given: {ABSENT_NOTE.get(a) or f'default {fields[a]!r}'}" for a in absent]
                   + notes + _assumptions(result))
    for w in warnings:
        if (w["severity"] == "critical" or w["code"] == "RELAXED_CONSTRAINT") and w["code"] != "NO_FEASIBLE_OPTION":
            assumptions.append(f"Relaxed or flagged ({w['code']}): {w['message']}")
    if not result.get("feasible"):
        return dict(head, status="infeasible", summary="No stack meets every hard constraint; see the critical warnings.",
                    architecture_style=None, stack=None, estimated_monthly_cost_usd=None, warnings=warnings,
                    assumptions=assumptions, validation_errors=[])
    if not fields["requirements.full_text_search"] and any(
            s["role"] == "Search" for s in result.get("supporting_services", []) + result.get("deferred_services", [])):
        assumptions.append("requirements.full_text_search is false, so no search service is recommended, although "
                           "projects of this type usually add one")
    stack = {l: _component(l, result["stack"][l], origin, fields, result) for l in LAYERS}
    stack["supporting"] = _supporting(result, fields)
    style = _style(result)
    cost = _cost(result, fields)
    worst = {w["severity"] for w in warnings}
    status = "ok_with_warnings" if worst & {"warning", "critical"} else "ok"
    return dict(head, status=status, summary=_summary(result, stack, style, cost), architecture_style=style,
                stack=stack, estimated_monthly_cost_usd=cost, warnings=warnings, assumptions=assumptions,
                validation_errors=[])
