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
from .advice import SSO_DAU_PER_MAU, service_notes
from .explain import LANG_LABELS, mobile_name
from .kb import LAYERS, field_specs, load_kb
from .recommender import recommend

PROJECT_TYPES = ("content_site", "web_app", "saas_b2b", "ecommerce", "marketplace", "social", "realtime_collab",
                 "fintech", "healthtech", "data_analytics", "iot", "ai_ml_product", "internal_tool", "gaming",
                 "api_platform", "other")
PLATFORMS = ("web", "android", "ios", "desktop", "api_only")
COMPLIANCE = ("gdpr", "dpdp", "hipaa", "pci_dss", "rbi_localisation", "soc2", "iso27001")
PRIORITY_KEYS = ("cost", "time_to_market", "scalability", "performance", "maintainability", "security")
SECTIONS = ("project", "scale", "team", "budget", "timeline", "infrastructure", "requirements")

# Words in project.description that carry a build duty the structured fields cannot express. Each adds one note to
# assumptions, quoting the words it matched; none sets a field, so the description still cannot move the stack.
DESCRIPTION_NOTES = [(re.compile(rx, re.I), note) for rx, note in (
    (r"\bupi\b", "use a payment gateway that takes UPI collections, UPI AutoPay mandates for repeat debits such as "
     "EMIs, and payouts to users' accounts through its payout API (Razorpay and Cashfree offer all three)"),
    (r"\b(?:e-?)?kyc\b", "identity documents are sensitive personal data: keep them in the private object store with "
     "server-side encryption, open them only through short-lived signed URLs, log every access, and keep them as "
     "long as the regulator requires (RBI's KYC Master Direction: at least five years after the relationship ends)"),
    (r"double[- ]entry|\bledgers?\b", "write each money movement as balanced debit and credit rows in one database "
     "transaction, append-only (a correction is a new reversing entry, never an edit), and derive balances from "
     "the rows"),
    (r"credit[- ]scor\w*|risk[- ]scor\w*", "version the scoring model and store which version scored each "
     "application with its inputs, so every decision can be explained and replayed later"),
    (r"\bgps\b|geo-?tagged|\blatitude\b|\blongitude\b|geolocat\w*", "store latitude and longitude with each "
     "record, and add a spatial index (PostGIS on PostgreSQL, or the database's own geo type) once you query by "
     "distance or area"),
    (r"\b[23]g\b(?!\s+of\b)|intermittent|patchy|low[- ]bandwidth|poor (?:network|connectivity|signal)|weak (?:network|signal)",
     "compress photos and other uploads on the device, send changes in small batches, and make uploads resumable "
     "(for example with the tus protocol) so a dropped connection does not restart them"),
    (r"low[- ]end|\b[1-3] ?gb (?:of )?ram\b|entry[- ]level (?:phones|devices)|budget (?:phones|devices)",
     "test on the slowest target device, keep the app bundle and memory use small (screens loaded on demand, "
     "virtualised lists), and resize images before they are shown"),
    (r"per[- ]seat|seat[- ]based|per[- ]user (?:pricing|billing|plans?)", "bill through the payment provider's "
     "subscriptions with the seat count as the quantity, updated when an organisation adds or removes members"),
    (r"\bchat(?:s|ting)?\b", "store messages in the database ordered per conversation, deliver them over the "
     "realtime connection, and send a push notification when the recipient is offline"),
    (r"\bmarkdown\b", "keep the posts as Markdown files in the repository and build the pages from them at deploy "
     "time; a CMS is needed only when people who do not use git write the content"),
    (r"\bbookings?\b|\bappointments?\b|\breservations?\b|\btime ?slots?\b", "stop double booking in the database: "
     "a unique constraint or a row lock on the slot inside one transaction, with a short hold while payment "
     "completes"),
    (r"\binventory\b|\bstock levels?\b", "take stock in the same transaction as the order (a conditional update "
     "that fails at zero), so two buyers cannot both get the last item"),
    (r"\baudit (?:trail|log)s?\b", "write audit rows append-only, with who, what, when and the old and new values, in "
     "the same transaction as the change they record"),
    (r"\binvoices?\b|\bgst\b", "number invoices in one consecutive series per financial year and never change an "
     "issued one; a correction is a credit note (for GST invoices in India, CGST rule 46 requires both)"),
    (r"multi-?lingual|several languages|multiple languages|regional languages|\bi18n\b|\btranslations?\b",
     "keep every user-facing string in translation files from the first screen, store text as UTF-8, and check "
     "layouts with the longest language's strings"),
)]


def description_notes(text: str) -> list[str]:
    """The notes the description's words call for, each quoting the words that matched."""
    return [f"Read from project.description ('{m.group(0)}'): {note}"
            for rx, note in DESCRIPTION_NOTES for m in [rx.search(text or "")] if m]

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
TOP_LEVEL = set(SECTIONS) | {"scenario_id", "compliance", "priorities", "extensions"}
# Questionnaire answers a scenario file may add in an optional "extensions" object (report section 4): inputs the
# standard schema has no field for. Each is checked against its question in data/questions.json and then used as
# that answer; a key not listed here is an UNKNOWN_FIELD notice, as elsewhere.
EXTENSION_KEYS = ("data_shapes", "consistency", "regions", "lock_in_tolerance", "cacheable_share", "background_work",
                  "peak_rps", "data_growth_gb_month", "tenancy", "architecture")
EXTENSION_PATHS = tuple(f"extensions.{k}" for k in EXTENSION_KEYS)

APP_TYPE = {"content_site": "content_site", "web_app": "saas", "saas_b2b": "saas", "ecommerce": "ecommerce",
            "marketplace": "ecommerce", "social": "social_network", "realtime_collab": "realtime_collab",
            "fintech": "fintech", "healthtech": "healthcare", "data_analytics": "analytics_dashboard",
            "iot": "iot_telemetry", "ai_ml_product": "ml_product", "internal_tool": "internal_tool",
            "gaming": "realtime_collab", "api_platform": "saas", "other": "saas"}
APP_TYPE_NOTES = {
    "marketplace": "a two-sided marketplace (listings, bookings, payouts) is scored like e-commerce",
    "web_app": "a general web application is scored like a SaaS product",
    "api_platform": "an API platform is scored like a SaaS product whose clients call the API",
    "gaming": "a live game backend is scored like a realtime collaboration product: shared state over live "
              "connections, with dedicated game servers for the matches",
    "other": "a project of type 'other' is scored like a SaaS product",
}
# The engine's priorities are a ranked list of at most three; the standard's 1-5 levels are read in this order.
PRIORITY_ENGINE = {"cost": "cost", "time_to_market": "speed", "scalability": "scale", "performance": "performance",
                   "maintainability": "maintainability", "security": "security"}
LANGUAGE_ALIASES = {"js": "javascript", "ts": "typescript", "c#": "csharp", "cs": "csharp", ".net": "csharp",
                    "dotnet": "csharp", "golang": "go", "nodejs": "node", "node.js": "node", "py": "python", "c++": "cpp",
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
                      (r"\boracle\b(?! cloud)", "oracle"), (r"\bdb2\b", "db2")]
# Databases the engine does not score: they stay the system of record and the new app integrates with them.
UNSCORED_DATABASES = {"oracle": "Oracle Database", "db2": "IBM Db2"}
# Existing platforms each kept in its own layer: (pattern, name, kind, source). A message system carries the new
# background jobs and events, a warehouse the analytics; a content or commerce platform keeps its content.
EXISTING_PLATFORMS = [
    (r"\bkafka\b", "Apache Kafka", "queue", "https://kafka.apache.org/intro"),
    (r"rabbit ?mq", "RabbitMQ", "queue", "https://www.rabbitmq.com/docs"),
    (r"\bibm mq\b|websphere mq", "IBM MQ", "queue", "https://www.ibm.com/products/mq"),
    (r"snowflake", "Snowflake", "warehouse", "https://docs.snowflake.com/en/user-guide/intro-key-concepts"),
    (r"databricks", "Databricks", "warehouse", "https://docs.databricks.com/"),
    (r"bigquery", "BigQuery", "warehouse", "https://docs.cloud.google.com/bigquery/docs"),
    (r"redshift", "Amazon Redshift", "warehouse", "https://docs.aws.amazon.com/redshift/"),
    (r"wordpress", "WordPress", "cms", "https://developer.wordpress.org/rest-api/"),
    (r"drupal", "Drupal", "cms", "https://www.drupal.org/docs/core-modules-and-themes/core-modules/jsonapi-module"),
    (r"shopify", "Shopify", "commerce", "https://shopify.dev/docs/api/storefront"),
    (r"magento|adobe commerce", "Adobe Commerce (Magento)", "commerce", "https://developer.adobe.com/commerce/webapi/"),
]
# CI systems a team already runs; the new app's pipelines go there: (pattern, name, source).
EXISTING_CI = [(r"\bjenkins\b", "Jenkins", "https://www.jenkins.io/doc/book/pipeline/"),
               (r"\bgitlab\b", "GitLab CI/CD", "https://docs.gitlab.com/ci/"),
               (r"azure devops|azure pipelines|\bvsts\b|\btfs\b", "Azure Pipelines (Azure DevOps)",
                "https://learn.microsoft.com/azure/devops/pipelines/get-started/what-is-azure-pipelines")]
PLATFORM_API = {"WordPress": "the WordPress REST API", "Drupal": "Drupal's core JSON:API module",
                "Shopify": "the Shopify Storefront API", "Adobe Commerce (Magento)": "Adobe Commerce's REST or GraphQL API"}
# The engine services an existing platform replaces, by the platform's kind.
PLATFORM_ROLES = {"queue": ("Background jobs", "Ingestion buffer"), "warehouse": ("Analytics",)}
BEING_REPLACED = re.compile(r"being replaced|to be replaced|replacing|migrat|retir|sunset|decommission")
# Project types whose in-app sales are digital goods, and each store's billing rule: (name, rule, source).
DIGITAL_GOODS = ("gaming", "social", "content_site", "web_app", "ai_ml_product", "realtime_collab", "other")
STORE_RULES = {
    "ios": ("App Store In-App Purchase", "Apple's App Review Guideline 3.1.1 requires in-app purchase to unlock "
            "features, subscriptions, in-game currencies and premium content",
            "https://developer.apple.com/app-store/review/guidelines/#in-app-purchase"),
    "android": ("Google Play Billing", "Google Play's payments policy requires its billing system for digital items "
                "such as virtual currencies, extra lives and add-on items",
                "https://support.google.com/googleplay/android-developer/answer/9858738"),
}
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
                (r"sharepoint|\b(?:microsoft|ms) outlook\b|\boutlook 20\d\d\b|^\s*outlook\b(?!.*\b(?:weather|forecast\w*|markets?)\b)"
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
    (r"python ?(2(\.\d+)?|3\.(?:10|[0-9]))\b", "Python {0}", "it has reached end of life",
     "https://devguide.python.org/versions/"),
    (r"\bvue(?:\.?js)? ?(2)(?:\.\d+)*\b", "Vue {0}", "it reached end of life on 31 Dec 2023", "https://v2.vuejs.org/eol/"),
    (r"\bwindows ?(7)\b", "Windows {0}", "extended support has ended",
     "https://learn.microsoft.com/lifecycle/products/windows-7"),
    (r"\boracle(?: database| db)? ?(8i|9i|10g|11g|12c|18c|(?:9|10|11|12)\.\d)", "Oracle Database {0}",
     "Premier and Extended Support have ended; only Sustaining Support, with no new fixes, remains",
     "https://www.oracle.com/us/support/library/lifetime-support-technology-069183.pdf"),
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
    (r"spring ?boot ?(2)(?:\.\d+)*\b", "Spring Boot {0}.x", "open-source support ended with 2.7.18 on 23 Nov 2023",
     "https://spring.io/blog/2023/11/23/spring-boot-2-7-18-available-now/"),
    # Google's own deprecations table records the shutdown; the old IoT Core pages now redirect elsewhere.
    (r"(?:google )?cloud iot core|google iot core", "Google Cloud IoT Core",
     "Google shut the service down on 16 Aug 2023", "https://docs.cloud.google.com/eventarc/docs/deprecations"),
    (r"jquery ?([12])(?:\.\d+)*\b", "jQuery {0}.x", "the 1.x and 2.x branches are no longer supported",
     "https://jquery.com/support/"),
    # The repository names MinIO's AIStor editions as the alternatives, so a system that says AIStor is not flagged.
    (r"^(?!.*\baistor\b).*\bminio\b", "MinIO", "its open-source repository was archived on 25 Apr 2026 and is no "
     "longer maintained", "https://github.com/minio/minio"),
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
                 "Enterprise SSO": "auth", "Phone login (SMS OTP)": "other", "Model serving": "ml",
                 "Vector search": "ml", "Observability": "observability", "Game servers": "realtime"}
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
                "Phone login (SMS OTP)": ["requirements.auth", "infrastructure.data_residency"],
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


def _check_extension(spec: dict, value) -> str | None:
    """The error for one extensions value against its question's type and options, or None."""
    allowed = [o["value"] for o in spec.get("options", [])]
    kind = spec.get("type")
    if kind == "select" and value not in allowed:
        return f"must be one of: {', '.join(allowed)}"
    if kind == "multiselect" and (not isinstance(value, list) or not value or any(v not in allowed for v in value)):
        return f"must be a non-empty list of: {', '.join(allowed)}"
    if kind == "number" and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0
                             or value != value or value in (float("inf"),)):
        return "must be a number of 0 or more"
    if kind == "bool" and not isinstance(value, bool):
        return "must be true or false"
    return None


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
    fields["extensions"] = {}
    ext = doc.get("extensions")
    if ext is not None and not isinstance(ext, dict):
        errors.append({"field": "extensions", "message": "must be an object"})
    elif ext:
        specs = field_specs()
        for key, value in ext.items():
            if key not in EXTENSION_KEYS:
                unknown.append(f"extensions.{key}")
                continue
            err = _check_extension(specs[key], value)
            if err:
                errors.append({"field": f"extensions.{key}", "message": err})
            else:
                fields["extensions"][key] = value
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
        hit = hit or any(re.search(pattern, low) for pattern, *_ in EXISTING_PLATFORMS + EXISTING_CI)
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
    _relax_contradictions(f, notes, warns)
    app = APP_TYPE[ptype]
    phones_only = "web" not in platforms and bool({"android", "ios"} & set(platforms))
    if ptype == "other" and phones_only:
        app = "mobile_first"
        notes.append("project.type 'other' with only phone platforms is scored as a mobile-first app")
    elif ptype == "gaming" and not f["requirements.realtime"]:
        # A turn-based or asynchronous game keeps realtime off as given; a live game is scored as realtime below.
        app = "mobile_first" if phones_only else "saas"
        notes.append("project.type 'gaming' with requirements.realtime false: a turn-based or asynchronous game is "
                     f"scored like {'a mobile-first app' if phones_only else 'a SaaS product'}, and realtime stays off")
    elif ptype in APP_TYPE_NOTES:
        notes.append(f"project.type '{ptype}': {APP_TYPE_NOTES[ptype]}")
    put("app_type", app, "project.type")
    put("project_name", (f["project.name"] or "Unnamed project")[:120], "project.name")
    if f["project.description"]:
        notes.append("project.description sets no field in a scenario file: every choice comes from the structured "
                     "fields, so wording cannot move the stack (in the app, the description reader only suggests "
                     "fields for you to confirm); a fixed keyword list adds the 'Read from project.description' "
                     "notes, which change no pick")
        notes += description_notes(f["project.description"])
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
        ("phone_otp", "requirements.auth", auth == "phone_otp"),
        ("game_client", "project.type", ptype == "gaming")) if on]
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
        if f["requirements.file_media_storage"]:  # the total includes the uploads (engine/profile.py splits it)
            put("data_includes_files", True, "scale.data_volume_gb_12_months", "requirements.file_media_storage")

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
    if ignored and not skills:
        # Listed but unsupported: the team still knows only these, so every backend is in a language it must learn.
        skills.append("other_language")
    put("team_skills", list(dict.fromkeys(skills)), "team.languages")
    if ignored:
        notes.append(f"team.languages not in the knowledge base: {', '.join(ignored)}; no candidate is written in "
                     + ("them" if len(ignored) > 1 else "it") + ", so they match no option"
                     + (", and a backend in any other language takes the unfamiliar-language penalty"
                        if skills == ["other_language"] else ""))
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
    if "gdpr" in compliance and residency == "none":
        # GDPR applies to people in the EU, so the users are placed there: hosts are scored for EU users and the stack
        # gets an EU region. data_residency stays unset, so this is a preference, not a hard rule.
        put("regions", ["europe"], "compliance")
        notes.append("gdpr with no data_residency: the users are taken to be in the EU, so the stack is placed in an EU "
                     "region; this is a preference, not a residency rule")
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
        where = ("The servers are your own, so keep them, their backups and any replica in a data centre inside the "
                 "required country." if onprem else
                 f"Pick {'an' if CLOUD_NAMES[cloud][0] in 'AEIOU' else 'a'} {CLOUD_NAMES[cloud]} region inside the required country "
                 "before you deploy." if cloud in CLOUD_NAMES else
                 "Pick a provider region inside the required country before you deploy, from independent hosts only "
                 "(cloud_preference 'none')." if cloud == "none" else
                 "Pick a region inside the required country before you deploy; AWS, Google Cloud and Azure cover the "
                 "most countries.")
        warns.append(_std_warn("RESIDENCY_UNVERIFIED", "warning",
                               "data_residency 'other' names no country, so the engine cannot check provider regions. "
                               + where, ["infrastructure.data_residency", "infrastructure.deployment_model"]
                               if onprem else ["infrastructure.data_residency"]))
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
    if [i for i in idps if i not in _cloud_only_identity(idps, f)] and f["requirements.auth"] != "none":
        put("identity_reused", True, "infrastructure.existing_systems")  # sign-in goes through it (_reuse_identity)
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
        elif dbid in UNSCORED_DATABASES:
            notes.append(f"Existing database '{text}': {UNSCORED_DATABASES[dbid]} stays the system of record and is "
                         "integrated, not migrated: the new app keeps its own data in the recommended database and reaches "
                         f"{UNSCORED_DATABASES[dbid]} through its client drivers or a change-data-capture feed")
    _platform_notes(f, notes, warns)
    retired = {e[0] for e in eol}
    for text in other:
        if text in retired:  # past its vendor's support: its data moves, it is not kept as a record
            notes.append(f"Existing system '{text}': past its vendor's support (see the EOL_EXISTING_SYSTEM warning), so "
                         "it is not kept as a system of record; move its data and duties into the new stack before "
                         "go-live")
            continue
        how, cloud_only = next(((api, c) for pattern, api, c in INTEGRATIONS if re.search(pattern, text.lower())),
                               (None, False))
        if how is None:
            notes.append(f"Existing system '{text}': no known integration path. StackSense has no interface on record "
                         "for it, so find out how it shares data (an API, a database, file exports) before planning the "
                         "integration; it stays the system of record for its own data")
            continue
        if cloud_only and deploy == "air_gapped":
            warns.append(_std_warn("EXISTING_SYSTEM_UNREACHABLE", "warning",
                                   f"'{text}' is a cloud service, and {unreachable} through {how}. Move its data across "
                                   "the air gap with the site's approved transfer process, or keep that integration on a "
                                   "connected system outside the network.",
                                   ["infrastructure.existing_systems", "infrastructure.deployment_model"]))
            continue
        notes.append(f"Existing system '{text}': integrated through {how}; it stays the system of record for its own data")
    for key, value in f.get("extensions", {}).items():
        if key == "regions" and f["infrastructure.data_residency"] != "none":
            notes.append(f"extensions.regions ignored: infrastructure.data_residency '{f['infrastructure.data_residency']}' "
                         "already fixes where the data and its users are")
            continue
        put(key, value, f"extensions.{key}")
        notes.append(f"extensions.{key} = {value!r}: answer taken from the scenario file's extensions block")
    return a, origin, notes, warns


def _platforms(texts: list[str]) -> list[tuple[str, str, str, str]]:
    """Existing platforms named in free text, in EXISTING_PLATFORMS order: (text, name, kind, source), the first text
    per platform. Of two of one kind, the first carries the new app's work and the other is kept as it is."""
    out = []
    for pattern, name, kind, source in EXISTING_PLATFORMS:
        text = next((t for t in texts if re.search(pattern, t.lower())), None)
        if text is not None:
            out.append((text, name, kind, source))
    return out


def _reuse_services(result: dict, f: dict) -> dict:
    """The engine's result with each service an existing platform covers replaced by that platform, and the replaced
    services' cost lines removed: the existing broker carries the queue, the existing warehouse the analytics."""
    services, deferred = list(result.get("supporting_services", [])), list(result.get("deferred_services", []))
    gone = set()
    for text, name, kind, source in _platforms(f["infrastructure.existing_systems"]):
        hit = [s for s in services + deferred if s["role"] in PLATFORM_ROLES.get(kind, ())]
        if not hit or any(s["name"].endswith("(existing)") for s in hit):
            continue  # nothing to replace, or an earlier platform of this kind already carries it
        was = " and ".join(dict.fromkeys(s["name"].split(" (")[0] for s in hit))
        why = (f"infrastructure.existing_systems lists '{text}': the new app's background jobs and events go through it "
               f"as new topics or queues instead of {was}, so there is no second message system to run, secure and "
               "monitor." if kind == "queue" else
               f"infrastructure.existing_systems lists '{text}': analytics queries run there, fed by a continuous copy of "
               f"the app database's changes, instead of a new {was} store beside it.")
        first, new = hit[0], {"role": hit[0]["role"], "name": f"{name} (existing)", "why": why, "source": source}
        services = [new if s is first else s for s in services if s is first or s not in hit]
        if first in deferred:  # the platform already runs, so nothing waits on the operations budget
            services.insert(0, new)
        deferred = [s for s in deferred if s not in hit]
        gone |= {s["role"] for s in hit}
    if not gone:
        return result
    cost = dict(result["cost"])
    dropped = [x for x in cost.get("lines", []) if x["component"].split(":")[0] in gone]
    cost["lines"] = [x for x in cost.get("lines", []) if x not in dropped]
    cost["total_low"] = cost["total_low"] - sum(x["low"] for x in dropped)
    cost["total_high"] = cost["total_high"] - sum(x["high"] for x in dropped)
    return dict(result, supporting_services=services, deferred_services=deferred, cost=cost)


def _store_billing(result: dict, f: dict) -> dict:
    """A phone app that sells digital goods (levels, in-game currency, subscriptions, premium content) must sell them
    through the store's own billing; a card processor stays only for the web. Shops, marketplaces, fintech and
    healthtech sell physical goods or real-world services, which the stores' rules send to a card processor instead."""
    phones = [x for x in ("ios", "android") if x in f["project.platforms"]]
    pay = next((s for s in result.get("supporting_services", []) if s["role"] == "Payments"), None)
    if not (phones and pay and f["requirements.payments"] and f["project.type"] in DIGITAL_GOODS):
        return result
    web = "web" in f["project.platforms"]
    rules = [STORE_RULES[x] for x in phones]
    name = (" and ".join(r[0] for r in rules) + " for digital goods and subscriptions sold in the app"
            + (f"; {pay['name']} for purchases on the website" if web else ""))
    why = ("Digital goods bought inside a phone app go through the store's own billing: " + "; ".join(r[1] for r in rules)
           + "." + (f" Purchases on the website can still use {pay['name']}." if web else "")
           + " Physical goods and services used outside the app are the exception, paid through a card processor.")
    new = {"role": "Payments", "name": name, "why": why, "source": rules[0][2]}
    return dict(result, supporting_services=[new if s is pay else s for s in result["supporting_services"]])


def _platform_notes(f: dict, notes: list[str], warns: list[dict]) -> None:
    """How each existing platform is kept, and a warning when a running content or commerce platform would be
    rebuilt by the stack shown instead of kept."""
    first = {}
    for text, name, kind, source in _platforms(f["infrastructure.existing_systems"]):
        if kind in ("queue", "warehouse") and kind in first:
            notes.append(f"Existing {'message system' if kind == 'queue' else 'warehouse'} '{text}': {name} is kept as it "
                         f"is for the systems that use it; the new app's {'jobs and events' if kind == 'queue' else 'analytics'} "
                         f"go through {first[kind]}")
        elif kind == "queue":
            notes.append(f"Existing message system '{text}': {name} carries the new app's background jobs and events, "
                         "so no second broker is added")
        elif kind == "warehouse":
            notes.append(f"Existing warehouse '{text}': analytics run in {name}, so no second analytics store is added")
        elif BEING_REPLACED.search(text.lower()):
            notes.append(f"Existing {name} '{text}' is being replaced: move its data across through {PLATFORM_API[name]} "
                         f"({source})")
        else:
            what = "content" if kind == "cms" else "catalogue, orders and customers"
            warns.append(_std_warn("EXISTING_PLATFORM_REBUILT", "warning",
                                   f"'{text}' is a running {name} system, and the stack shown is a new build beside it. "
                                   f"Keep {name} for the {what}, as it is or headless behind the new frontend through "
                                   f"{PLATFORM_API[name]} ({source}), unless replacing it is the goal: a rebuild moves "
                                   f"every record of the {what} and every URL across.",
                                   ["infrastructure.existing_systems"]))
        first.setdefault(kind, name)


def _relax_contradictions(f: dict, notes: list[str], warns: list[dict]) -> None:
    """Fields that cannot all hold (section 6): a critical warning, and the weaker field relaxed in place, so every
    later step (stack, services, summary) sees the relaxed value; assumptions say exactly what was relaxed."""
    users = max(f["scale.users_at_launch"], f["scale.users_12_months"])
    peak = f["scale.peak_concurrent_users"]
    if peak is not None and peak > users:
        warns.append(_std_warn("CONCURRENT_ABOVE_USERS", "critical",
                               f"scale.peak_concurrent_users ({peak:,}) is more than the {users:,} users the project will "
                               "ever have: more people cannot be online at once than exist. Relaxed: concurrency is capped "
                               f"at {users:,}, every user online at once; correct the figure if it counts connections or "
                               "devices rather than people.", ["scale.peak_concurrent_users", "scale.users_12_months"]))
        notes.append(f"Relaxed: scale.peak_concurrent_users {peak:,} capped at the user count, {users:,}")
        f["scale.peak_concurrent_users"] = users
    if not set(f["project.platforms"]) - {"api_only"}:
        client = [(path, what) for path, what in (("requirements.offline_support", "working offline needs an app on the "
                                                   "user's device"), ("requirements.seo_critical", "search ranking needs "
                                                   "web pages for crawlers")) if f[path]]
        if client:
            warns.append(_std_warn("API_ONLY_CLIENT_REQUIREMENT", "critical",
                                   f"project.platforms is api_only, so there is no client, but {' and '.join(w for _, w in client)}. "
                                   f"Relaxed: {' and '.join(p for p, _ in client)} treated as false, so no offline sync or "
                                   "pre-rendered pages are added; add web, android or ios to project.platforms if a client "
                                   "is planned.", ["project.platforms"] + [p for p, _ in client]))
            for path, _ in client:
                notes.append(f"Relaxed: {path} true treated as false (project.platforms is api_only)")
                f[path] = False
    deploy = f["infrastructure.deployment_model"]
    if f["requirements.seo_critical"] and deploy == "air_gapped":
        warns.append(_std_warn("SEO_RESTRICTED_DEPLOYMENT", "critical",
                               "requirements.seo_critical needs public pages that search engines crawl, but an air-gapped "
                               "network has no internet connection, so no crawler can reach them. Relaxed: "
                               "requirements.seo_critical treated as false; publish public pages from a separate site "
                               "outside the network.", ["requirements.seo_critical", "infrastructure.deployment_model"]))
        notes.append("Relaxed: requirements.seo_critical true treated as false (infrastructure.deployment_model is air_gapped)")
        f["requirements.seo_critical"] = False
    elif f["requirements.seo_critical"] and deploy == "on_premise":
        warns.append(_std_warn("SEO_RESTRICTED_DEPLOYMENT", "warning",
                               "requirements.seo_critical needs public pages that search engines crawl, and on-premises "
                               "servers sit behind your firewall with no CDN in the stack. Kept: the pages are rendered on "
                               "your servers, so open them to the internet through the firewall or a reverse proxy, or "
                               "publish them from a separate public site.",
                               ["requirements.seo_critical", "infrastructure.deployment_model"]))


def _language_warning(result: dict, f: dict, a: dict) -> list[dict]:
    """The team lists only languages no backend in the knowledge base is written in: name the one it must learn."""
    kb = load_kb()
    be = kb["index"].get(result["stack"]["backend"]["pick"]["id"], {})
    skills = set(a.get("team_skills", []))
    if not f["team.languages"] or be.get("kind") not in ("server", "faas") or \
            skills & {s for it in kb["backend"] for s in it.get("skills", [])}:
        return []
    labels = {o["value"]: o["label"] for o in field_specs()["team_skills"]["options"]}
    carry = sorted(labels.get(s, s) for s in skills & set(be.get("related_skills", [])))
    lang = LANG_LABELS.get(be.get("language", ""), be["name"])
    listed = ", ".join(f["team.languages"])
    return [_std_warn("BACKEND_LANGUAGE_NOT_LISTED", "warning",
                      f"Backend in a language the team did not list. team.languages lists {listed}, and no backend in "
                      "the knowledge base is written in " + ("it" if len(f["team.languages"]) == 1 else "any of them")
                      + (f"; {' and '.join(carry)} carr{'y' if len(carry) > 1 else 'ies'} over to {be['name']}" if carry else "")
                      + f". The backend is {be['name']}: plan time for the team to learn {lang} before the first "
                      "release.", ["team.languages"])]


def _mobile_language_warning(result: dict, f: dict) -> list[dict]:
    """A native phone app in a language team.languages does not list (the card says so too): a delivery risk."""
    gap = _native_language_gap(result["stack"]["frontend"]["pick"]["id"], (result.get("companion") or {}).get("id"), f=f)
    if not gap:
        return []
    return [_std_warn("MOBILE_LANGUAGE_NOT_LISTED", "warning",
                      "Native app in a language the team did not list." + gap
                      + " Plan time to learn it or hire for it before the first release.",
                      ["team.languages", "project.platforms"])]


RBI_STORAGE = "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11244"
PLATFORMS_INFO_WEEKS = 8  # our planning judgement: 3+ client platforms in 5-8 weeks is tight (4 or fewer is critical)


def _compliance_info(result: dict, f: dict, warnings: list[dict]) -> list[dict]:
    """Duties and risks that otherwise sit only in assumptions or service texts, as plain info warnings; a duty an
    existing warning already states is not repeated."""
    have = {w["code"] for w in warnings}
    comp, out = set(f["compliance"]), []
    services = " ".join(s["name"] for s in result.get("supporting_services", []))
    if "hipaa" in comp and "HIPAA_FREE_TIER" not in have:
        out.append(_std_warn("HIPAA_BAA_NEEDED", "info",
                             "HIPAA: sign a Business Associate Agreement (BAA) with every vendor that stores or handles "
                             "health data (host, database, file storage, sign-in, monitoring) before any patient data goes "
                             "in, and keep health data out of logs and notification text.", ["compliance"]))
    if "hosted checkout" in services:
        out.append(_std_warn("PCI_SCOPE", "info",
                             "Card payments: the hosted checkout collects card numbers on the payment provider's page, so "
                             "your PCI DSS check is the shortest self-assessment (SAQ A). Putting card fields on your own "
                             "pages, or storing card numbers, widens the audit.", ["requirements.payments", "compliance"]))
    if "gdpr" in comp:
        out.append(_std_warn("GDPR_DUTIES", "info",
                             "GDPR: sign a data processing agreement with every vendor that handles personal data, honour "
                             "access and deletion requests, and report a breach within 72 hours; a vendor outside the EU "
                             "needs Standard Contractual Clauses or the EU-US Data Privacy Framework.", ["compliance"]))
    if "dpdp" in comp:
        out.append(_std_warn("DPDP_DUTIES", "info",
                             "DPDP Act 2023: collect personal data with a clear notice and consent, let users see, correct "
                             "and erase it, and report a breach to the Data Protection Board and the people affected.",
                             ["compliance"]))
    if "rbi_localisation" in comp:
        out.append(_std_warn("RBI_COPIES_IN_INDIA", "info",
                             "RBI localisation: the entire payment data must be stored only in India, so backups, "
                             "replicas and logs that hold it must also be in an Indian region; check each destination "
                             f"before go-live ({RBI_STORAGE}).", ["compliance"]))
    avail = float(f["requirements.availability"])
    if avail >= 99.95 and not f["team.has_devops"] and not have & {"SLA_SMALL_TEAM", "BEGINNER_HIGH_AVAILABILITY"}:
        out.append(_std_warn("ON_CALL_GAP", "info",
                             f"A {avail:g}% target allows about {(100 - avail) / 100 * 30 * 24 * 60:,.0f} minutes of "
                             "downtime a month, and team.has_devops is false: someone must be on call to restore service "
                             "within minutes, or the target will be missed.",
                             ["requirements.availability", "team.has_devops"]))
    clients = [x for x in f["project.platforms"] if x != "api_only"]
    if len(clients) >= 3 and f["timeline.mvp_weeks"] <= PLATFORMS_INFO_WEEKS and "MANY_PLATFORMS_SHORT_TIMELINE" not in have:
        out.append(_std_warn("PLATFORMS_TIMELINE", "info",
                             f"{len(clients)} client platforms ({', '.join(clients)}) in {f['timeline.mvp_weeks']:g} weeks: "
                             "each needs its own build, testing and store or release work, so plan to release one "
                             "platform first and add the others after.", ["project.platforms", "timeline.mvp_weeks"]))
    return out


def _reused(result: dict, f: dict) -> tuple[str | None, str | None]:
    """The existing database the stack keeps and the existing identity provider sign-in goes through, if any."""
    db = load_kb()["index"].get(result["stack"]["database"]["pick"]["id"], {})
    dbs, idps = _systems(f["infrastructure.existing_systems"])[:2]
    idps = [i for i in idps if i not in _cloud_only_identity(idps, f)] if f["requirements.auth"] != "none" else []
    return (db["name"] if db.get("id") in dbs else None), (idps[0] if idps else None)


def _cloud_only_identity(idps: list[str], f: dict) -> list[str]:
    """The existing identity providers the network cannot reach: the cloud ones, when the site is air-gapped."""
    return [i for i in idps if i in CLOUD_IDENTITY] if f["infrastructure.deployment_model"] == "air_gapped" else []


def _std_warn(code: str, severity: str, message: str, fields: list[str]) -> dict:
    return {"code": code, "severity": severity, "message": message, "fields": fields}


def _paths(keys, origin: dict) -> list[str]:
    out = []
    for key in keys:
        out += origin.get(key) or ENGINE_FIELDS.get(key, [])
    return list(dict.fromkeys(p for p in out if p in FIELD_PATHS or p in EXTENSION_PATHS))


def _region(provider: str, f: dict) -> str | None:
    res = f["infrastructure.data_residency"]
    if "rbi_localisation" in f["compliance"]:
        res = "india"
    elif res == "none" and "gdpr" in f["compliance"]:
        res = "eu"  # GDPR with no residency places the users in the EU (to_answers)
    return REGION.get((provider, res))


def _component(layer: str, sl: dict, origin: dict, f: dict, result: dict) -> dict:
    pick, ex = sl["pick"], sl["explanation"]
    choice, extra = pick["name"], ""
    item = load_kb()["index"].get(pick["id"], {})
    if item.get("kind") == "none" or (layer == "database" and item.get("static_only")):
        choice, extra = "None", ""  # the section 4 spelling for a layer that is not needed; the name says why
        ex = dict(ex, paragraph=f"{pick['name']}. {ex.get('paragraph') or ''}".strip())
    if layer == "frontend":
        choice = mobile_name(pick["id"], choice, f["project.platforms"])
    db, idp = _reused(result, f) if layer == "backend" and item.get("kind") != "none" else (None, None)
    if db or idp:
        extra = " It works with the existing " + " and ".join(
            ([f"{db} for data"] if db else []) + ([f"{idp} for sign-in"] if idp else [])) + "."
    if layer == "frontend" and result.get("companion"):
        comp = result["companion"]
        apps = "/".join(x for x in ("Android", "iOS") if x.lower() in f["project.platforms"])
        name = mobile_name(comp["id"], comp["name"], f["project.platforms"])
        choice += f" + {name} for the {apps} app"
        extra = f" {comp['why'].replace(comp['name'], name)}"
    if layer == "frontend":
        extra += _native_language_gap(pick["id"], (result.get("companion") or {}).get("id"), f=f)
    if layer == "database" and sl.get("managed_offering") and choice != "None":
        index = load_kb()["index"]
        host = index.get(((result["stack"]["hosting"].get("api_host") or {}).get("id")
                          or result["stack"]["hosting"]["pick"]["id"]), {})
        functions = "faas" in (host.get("kind"), index.get(result["stack"]["backend"]["pick"]["id"], {}).get("kind"))
        offering = sl["managed_offering"] if functions else re.sub(r" \(\+ [^)]*for serverless\)", "", sl["managed_offering"])
        choice += f": {offering}"
    if layer == "hosting":
        api = sl.get("api_host")
        if api:
            choice += f" for the frontend + {api['name']} for the API"
        provider = load_kb()["index"].get((api or {}).get("id") or pick["id"], {}).get("provider", "")
        region = _region(provider, f)
        if region and not choice.startswith("Provided by"):  # the scored host's region; the BaaS card has its own
            choice += f", region {region}"
    # The answers that added the most points to this pick, then the hard constraints that ruled rivals out.
    scored = sorted((c for c in ex.get("input_contributions", []) if c["points"] >= DRIVER_MIN_POINTS
                     and c["input"] not in ("baseline", "clamp")), key=lambda c: -c["points"])
    ruled = _paths([c for x in sl.get("excluded", []) for c in x.get("constraints", [])], origin)
    driven_by = list(dict.fromkeys(_paths([c["input"] for c in scored], origin)[:DRIVERS_SCORED]
                                   + ruled[:DRIVERS_RULED])) or ["project.type"]
    # Weighed alternatives that trail by more than FAR_BEHIND points are not contenders (ECS for a static blog); the
    # closest one always stays, so every layer keeps an alternative.
    near = [w for w in sl.get("why_not", []) if w.get("gap") is None or w["gap"] <= FAR_BEHIND]
    near = near or sl.get("why_not", [])[:1]
    alternatives = [{"choice": w["name"], "why_not": w["text"]} for w in near][:3]
    companion = result["companion"]["name"] if layer == "frontend" and result.get("companion") else None
    alternatives = [x for x in alternatives if x["choice"] != companion]
    taken = {pick["name"], companion} | {x["choice"] for x in alternatives}
    for x in sl.get("excluded", []):
        if len(alternatives) >= 4:
            break
        if x["name"] not in taken:
            alternatives.append({"choice": x["name"], "why_not": "Ruled out: " + "; ".join(x["reasons"][:2])})
    # An option a rule removed is worth listing when the rule is one of the user's own hard constraints (a region, a
    # compliance regime, the required cloud); a generic one ("Mobile toolkit; web is a target") is padding once scored
    # alternatives exist.
    weighed = [x for x in alternatives if not x["why_not"].startswith("Ruled out")]
    ruled = [x for x in alternatives if x["why_not"].startswith("Ruled out")]
    if weighed:
        ruled = [x for x in ruled if HARD_RULE_WORDS.search(x["why_not"])][:1]
    alternatives = weighed + ruled[:2]
    if not alternatives:
        alternatives = [{"choice": r["name"], "why_not": f"Scores {r['score']:.1f} against the pick's {pick['score']:.1f}"}
                        for r in sl.get("ranking", []) if r["name"] != pick["name"]][:1]
    return {"choice": choice, "justification": (ex.get("paragraph") or " ".join(ex.get("why", []))) + extra,
            "driven_by": driven_by, "alternatives": alternatives,
            "tradeoffs": list(dict.fromkeys(ex.get("tradeoffs", []) + ex.get("risks", [])))}


FAR_BEHIND = 15.0  # points of the 0-100 stack score
HARD_RULE_WORDS = re.compile(r"region|residency|HIPAA|BAA|PCI|ISO 27001|SOC 2|the cloud you require|air-gapped|\bIndia\b|"
                             r"\bEU\b|existing", re.I)


def _native_language_gap(*ids, f: dict) -> str:
    """A native phone app in a language team.languages does not list: say so, and name the toolkit that would reuse
    the team's web language."""
    if "native_mobile" not in ids:
        return ""
    langs = set(f["team.languages"])
    missing = [lang for plat, lang in (("ios", "swift"), ("android", "kotlin")) if plat in f["project.platforms"]
               and lang not in langs]
    if not missing:
        return ""
    apps = " and ".join({"swift": "the iOS app (Swift)", "kotlin": "the Android app (Kotlin)"}[m] for m in missing)
    web = next((n for x, n in (("typescript", "TypeScript"), ("javascript", "JavaScript")) if x in langs), None)
    return (f" team.languages does not list {' or '.join(m.capitalize() for m in missing)}, so {apps} is a language "
            "the team must learn" + (f"; React Native (Expo) would reuse the team's {web} instead." if web else "."))


ONE_PER_LAYER = ("auth", "cdn", "storage")


def _quote(layer: str, f: dict) -> str:
    """One number from the scenario that a supporting service is chosen or sized for."""
    if layer == "observability":
        a = float(f["requirements.availability"])
        return (f" A {a:g}% availability target (requirements.availability) allows about "
                f"{(100 - a) / 100 * 30 * 24 * 60:,.0f} minutes of downtime a month, so failures must show within minutes.")
    if layer == "cache" and f["requirements.p95_latency_ms"]:
        return (f" The {f['requirements.p95_latency_ms']:g} ms p95 target (requirements.p95_latency_ms) leaves little "
                "time for repeated database reads.")
    if layer == "realtime" and f["scale.peak_concurrent_users"]:
        return (f" Up to {f['scale.peak_concurrent_users']:,.0f} users online at once (scale.peak_concurrent_users) "
                "hold open connections.")
    if layer == "ci_cd":
        return f" All {f['team.size']:,.0f} engineers (team.size) release through the same pipeline."
    if layer in ("storage", "search") and f["scale.data_volume_gb_12_months"] is not None:
        return (f" The scenario stores {f['scale.data_volume_gb_12_months']:,g} GB within 12 months "
                "(scale.data_volume_gb_12_months).")
    return ""  # the users the stack is sized for are stated once, in assumptions


def _left_out(s: dict, f: dict) -> bool:
    """A service the scenario rules out although the engine would add it."""
    if s["role"] == "Collaboration sync" and f["project.type"] == "gaming":
        return True  # a game server owns the state; merging documents (CRDTs) is for co-editing tools
    return s["role"] == "Search" and not f["requirements.full_text_search"]  # the scenario says it needs none


def _deferred(result: dict, f: dict) -> list[str]:
    """Services the operations budget keeps out of the first release, as assumptions with their trigger: they are
    not part of the recommended stack, so stack.supporting does not list them."""
    ops = "the team's operations budget allows no more systems to run"
    return [f"Deferred: {s['role']} ({s['name']}) is left out of the first release, because {s.get('hold') or ops}; "
            f"add it {s['trigger']}." for s in result.get("deferred_services", []) if not _left_out(s, f)]


AUTH_WHY = {
    "email_password": "Password sign-in needs salted hashing, email verification, password resets and optional MFA, "
                      "which a maintained sign-in product or library does correctly.",
    "social": "Social sign-in (Google, Apple, GitHub) needs OAuth 2.0 and OpenID Connect flows, account linking and token "
              "refresh, which a maintained sign-in product or framework library handles.",
    "phone_otp": "Phone sign-in needs one-time codes with expiry, retry limits and lockouts against SMS-pumping fraud; the "
                 "codes go out through the SMS gateway listed with the services.",
}


def _supporting(result: dict, f: dict) -> list[dict]:
    out = []
    for s in result.get("supporting_services", []):
        if _left_out(s, f):
            continue
        layer = SERVICE_LAYER.get(s["role"], "other")
        fields = OTHER_FIELDS.get(s["role"]) or SERVICE_FIELDS[layer]
        if f["infrastructure.data_residency"] != "none" and layer in ("storage", "auth", "cache", "observability", "ml"):
            fields = fields + ["infrastructure.data_residency"]
        alts, tradeoffs = service_notes(s, result.get("profile", {}).get("compliance", []))
        tradeoffs = list(tradeoffs)
        if s.get("system"):
            tradeoffs.append(f"One more system to run: {s['system']}")
        if s.get("trigger"):
            tradeoffs.append(f"Can wait until {s['trigger']}")
        why = s["why"]
        if s["role"] == "Authentication" and f["requirements.auth"] in AUTH_WHY:
            # Say what this sign-in method needs, and where a per-user price decided the product, the users it is for.
            why = AUTH_WHY[f["requirements.auth"]] + (f" {s['price_note']}" if s.get("price_note") else "")
            fields = fields + ["scale.users_12_months"]
            if "gdpr" in f["compliance"] and s["name"].startswith("Clerk"):
                why += (" Clerk is a US company, so under GDPR sign its data processing agreement with Standard "
                        "Contractual Clauses (GDPR Chapter V).")
                fields = fields + ["compliance"]
        if f["infrastructure.data_residency"] != "none" and "infrastructure.data_residency" not in fields and re.search(
                r"region|residency|\bIndia\b|\bEU\b", s["name"] + " " + s["why"]):
            fields = fields + ["infrastructure.data_residency"]  # the residency rule shaped this service too
        layer = s.get("layer") or layer
        alts = [{"choice": c, "why_not": w} for c, w in alts if c.split(" (")[0] not in s["name"]]
        entry = {"layer": layer, "choice": s["name"], "justification": why, "driven_by": fields,
                 "alternatives": alts, "tradeoffs": tradeoffs, "source": s.get("source"), "role": s["role"]}
        first = next((x for x in out if x["layer"] == layer), None) if layer in ONE_PER_LAYER else None
        if first:  # one sign-in product, one CDN, one file store: a second line of the layer adds to the first
            if s["role"] == "Static frontend":  # it names the bucket and the CDN, so it leads
                first.update(choice=entry["choice"], source=entry["source"], role=entry["role"])
            first["justification"] += " " + why
            first["driven_by"] = list(dict.fromkeys(first["driven_by"] + fields))
            first["tradeoffs"] = list(dict.fromkeys(first["tradeoffs"] + tradeoffs))
            first["alternatives"] += [a for a in alts if a not in first["alternatives"]]
            continue
        out.append(entry)
    idps = _systems(f["infrastructure.existing_systems"])[1]
    idps = [i for i in idps if i not in _cloud_only_identity(idps, f)]
    if idps and f["requirements.auth"] != "none":
        replaced = [x for x in out if x["role"] in ("Authentication", "Enterprise SSO")]
        first = out.index(replaced[0]) if replaced else len(out)
        out = [x for x in out if x not in replaced]
        out.insert(first, _reuse_identity(idps[0], replaced))
    for x in out:  # each justification quotes the scenario number the service answers to
        x["justification"] += _quote(x["layer"], f)
        x.pop("role", None)
    out.append(_ci_cd(f))
    out[-1]["justification"] += _quote("ci_cd", f)
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
    text, name, source = next(((t, n, s) for pattern, n, s in EXISTING_CI for t in f["infrastructure.existing_systems"]
                               if re.search(pattern, t.lower())), (None, None, None))
    if name:  # the pipeline the team already runs builds the new app too
        return {"layer": "ci_cd", "choice": f"{name} (existing)",
                "justification": f"infrastructure.existing_systems lists '{text}': the new app's builds, tests and "
                                 f"deploys run as new pipelines on {name}, so there is no second CI system to learn, "
                                 "secure and pay for.",
                "driven_by": ["infrastructure.existing_systems", "infrastructure.deployment_model", "team.size"],
                "alternatives": [{"choice": "GitHub Actions", "why_not": f"A second CI system beside {name}, which "
                                  "already builds the team's other code"}],
                "tradeoffs": [f"The new pipelines share {name}'s runners and its upgrade schedule"],
                "source": source}
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
            "alternatives": [{"choice": alt, "why_not": "Equivalent pipelines; one more tool to learn for no gain here"},
                             {"choice": "Deploying by hand from a developer's machine", "why_not": "No test gate, and "
                              "each release depends on one person's setup"}],
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
        message = message.replace(  # a database the engine does not score is a system of record to integrate with
            "Recommending the closest open database; plan a migration or keep a sync from your existing one.",
            "It stays the system of record and is integrated, not migrated: the new app keeps its own data in the "
            "recommended database and reaches the existing one through its client drivers or a change-data-capture feed.")
        for app_words, file_words in FORM_WORDS:
            message = message.replace(app_words, file_words)
        out.append(_std_warn(w["code"], w["severity"], message, _paths(w.get("fields", []), origin)))
    return out


def _assumptions(result: dict) -> list[str]:
    out, defaults = [], []
    for a in result.get("assumptions", []):
        if a.get("field") == "latency_target_ms" or (a.get("field") == "availability" and a.get("kind") == "default"):
            continue  # run() and to_answers already state these defaults in the standard fields' words
        reason = a.get("reason", "")
        m = re.fullmatch(r"Not provided; using default '(.*)'\.", reason)
        if m and a.get("field"):
            # A questionnaire answer the schema has no field for: one line lists them all, in field names
            defaults.append(f"{a['field']} '{m.group(1)}'")
            continue
        label = a.get("label") or a.get("field", "")
        for app_words, file_words in FORM_WORDS:
            reason = reason.replace(app_words, file_words)
        out.append(f"{label}: {reason}".strip())
    if defaults:
        out.insert(0, "Questionnaire answers the scenario schema has no field for took their defaults: "
                   + ", ".join(defaults) + " (an extensions block can set them)")
    return out


def _cost(result: dict, f: dict) -> dict:
    c = result["cost"]
    lines = [f"{x['component']}: ${x['low']:,.0f}-{x['high']:,.0f} ({x['basis']})" for x in c.get("lines", [])]
    budget = f["budget.monthly_infra_usd"]
    return {"min": round(c["total_low"]), "max": round(c["total_high"]),
            "assumptions": [c.get("note", ""), f"Scale tier: {c.get('tier', '')}",
                            f"Budget check: ${budget:,.0f}/month stated, status '{c.get('status', '')}'"] + lines}


COMPLIANCE_NAMES = {"gdpr": "GDPR", "dpdp": "DPDP", "hipaa": "HIPAA", "pci_dss": "PCI DSS",
                    "rbi_localisation": "RBI localisation", "soc2": "SOC 2", "iso27001": "ISO 27001"}
RESIDENCY_NAMES = {"india": "India", "eu": "the EU", "us": "the US"}
CLOUD_NAMES = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure"}


def _summary(result: dict, stack: dict, style: str, cost: dict, f: dict, a: dict) -> str:
    """Two sentences (section 4 allows one or two): the stack with its monthly band, then the inputs that shaped it
    for this scenario: systems it keeps, hard constraints, the team's language, a key requirement, and the build."""
    names = {l: re.split(r" \(|,|: ", stack[l]["choice"])[0] for l in LAYERS}
    roles = {"frontend": "on the frontend", "backend": "for the backend", "database": "for data"}
    used = [f"{names[l]} {role}" for l, role in roles.items() if names[l] != "None"]
    unused = [l for l in roles if names[l] == "None"]
    money = f"${cost['min']:,}" if cost["min"] == cost["max"] else f"${cost['min']:,}-{cost['max']:,}"
    label = (result.get("architecture", {}).get("style", "").split(" (")[0] if style == "other"
             else style.replace("_", " ").replace("service oriented", "service-oriented"))
    host = names["hosting"]
    host = f"with hosting {host[0].lower()}{host[1:]}" if host.startswith("Provided by") else f"hosted on {host}"
    over = any(w["code"] == "BUDGET_INFEASIBLE" for w in result.get("warnings", []))
    first = (f"A {label} build: {', '.join(used)}, {host} for about {money} a month"
             + (f", a relaxed recommendation over your ${f['budget.monthly_infra_usd']:,.0f} budget" if over else "")
             + (f"; no {' or '.join(unused)} is needed" if unused else "") + ".")
    items = {l: load_kb()["index"].get(result["stack"][l]["pick"]["id"], {}) for l in LAYERS}
    reasons = []
    db, idp = _reused(result, f)
    # The kept engine's data moves to the offering the database line names, so the summary says where it goes.
    offering = stack["database"]["choice"].partition(": ")[2].split(" (")[0]
    moved = (" (on servers you run)" if offering.lower().startswith("self-managed") else f" (moved to {offering})"
             if offering else "")
    kept = ([f"{names['database']} data{moved}"] if db else []) + ([f"{idp} sign-in"] if idp else [])
    if kept:
        reasons.append(f"keeps the existing {' and '.join(kept)}")
    cloud, deploy = f["infrastructure.cloud_preference"], f["infrastructure.deployment_model"]
    where = ("runs inside the air-gapped network" if deploy == "air_gapped" else "runs on your own servers"
             if deploy == "on_premise" else f"stays on {CLOUD_NAMES[cloud]}" if cloud in CLOUD_NAMES else "")
    residency = "india" if "rbi_localisation" in f["compliance"] else f["infrastructure.data_residency"]
    rules = [COMPLIANCE_NAMES[c] for c in f["compliance"]][:2]
    if residency in RESIDENCY_NAMES:
        where = (f"{where} and " if where else "") + f"keeps data in {RESIDENCY_NAMES[residency]}"
    if where or rules:
        reasons.append(f"{where} under {' and '.join(rules)}" if where and rules else where or f"plans for {' and '.join(rules)}")
    skills = set(a.get("team_skills", []))
    mine = [s for s in items["backend"].get("skills", []) if s in skills] if items["backend"].get("kind") != "none" else []
    if mine:
        label_of = {o["value"]: o["label"] for o in field_specs()["team_skills"]["options"]}
        reasons.append(f"builds on the team's {label_of.get(mine[0], mine[0])}")
    need = [text for on, text in ((f["requirements.offline_support"], "keeps working offline"),
                                  (f["requirements.realtime"], "pushes live updates"),
                                  (f["requirements.seo_critical"], "gives search engines full HTML pages")) if on]
    reasons += need[:1]
    team = "a solo developer" if f["team.size"] == 1 else f"a team of {f['team.size']}"
    build = {"static": f"serves pre-built files, so there is no server for {team} to run",
             "monolith": f"ships as one deployable that {team} can build in {f['timeline.mvp_weeks']} weeks",
             "modular_monolith": f"ships as one deployable that {team} can build in {f['timeline.mvp_weeks']} weeks",
             "serverless": f"leaves the servers to the platform, so {team} writes only the product's own logic",
             "service_oriented": f"splits into a few services, one per team, for {team}",
             "microservices": f"splits into independently deployed services for {team}"}.get(style)
    reasons = reasons[:3] + ([build] if build else [])
    if not reasons:
        return first
    joined = reasons[0] if len(reasons) == 1 else f"{', '.join(reasons[:-1])}{',' if len(reasons) > 2 else ''} and {reasons[-1]}"
    return f"{first} It {joined}."


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


def _no_cost(reason: str) -> dict:
    """Section 4 keeps estimated_monthly_cost_usd an object even when there is no stack to price."""
    return {"min": 0, "max": 0, "assumptions": [f"No stack was produced ({reason}), so there is no bill to estimate"]}


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
                    architecture_style="other", stack=None,
                    estimated_monthly_cost_usd=_no_cost("the scenario has invalid fields"), warnings=[],
                    assumptions=[], validation_errors=errors)

    answers, origin, notes, extra = to_answers(fields)
    absent = [path for path, _kind, required, *_ in FIELDS if not required and _get(doc, path)[1] is None
              and not (path == "requirements.p95_latency_ms" and _get(doc, path)[0])]
    if "requirements.availability" in absent:
        # Left to the engine's own default, so it is planned as a goal, not a stated target (no standby priced).
        answers.pop("availability")
    result = recommend(answers, with_counterfactuals=False)
    warnings = [_std_warn("MISSING_REQUIRED_FIELD", "warning",
                          f"{m} is required but missing; the documented default "
                          f"{fields[m]!r} was used (listed in assumptions).", [m]) for m in missing]
    warnings += [_std_warn("UNKNOWN_FIELD", "info", f"{k} is not part of the standard schema and was ignored.", [k])
                 for k in unknown]
    relaxed = {w["code"] for w in extra if w["severity"] == "critical"}
    # SEO turned off here (an air-gapped network) is not the user marking it unnecessary.
    warnings += extra + [w for w in _warnings(result, origin)
                         if not (w["code"] == "SEO_HINT" and "SEO_RESTRICTED_DEPLOYMENT" in relaxed)]
    if result.get("feasible"):
        warnings += _language_warning(result, fields, answers)
        warnings += _mobile_language_warning(result, fields)
        warnings += _compliance_info(_store_billing(result, fields), fields, warnings)
    absent += [f"priorities.{k}" for k in PRIORITY_KEYS if (doc.get("priorities") or {}).get(k) is None]
    assumptions = ([f"{m} missing: used {fields[m]!r}" for m in missing]
                   + [f"{a} not given: {ABSENT_NOTE.get(a) or f'default {fields[a]!r}'}" for a in absent]
                   + notes + _assumptions(result))
    for w in warnings:
        if (w["severity"] == "critical" or w["code"] == "RELAXED_CONSTRAINT") and w["code"] != "NO_FEASIBLE_OPTION":
            assumptions.append(f"Relaxed or flagged ({w['code']}): {w['message']}")
    if not result.get("feasible"):
        return dict(head, status="infeasible", summary="No stack meets every hard constraint; see the critical warnings.",
                    architecture_style="other", stack=None,
                    estimated_monthly_cost_usd=_no_cost("no stack meets every hard constraint"), warnings=warnings,
                    assumptions=assumptions, validation_errors=[])
    if not fields["requirements.full_text_search"] and any(
            s["role"] == "Search" for s in result.get("supporting_services", []) + result.get("deferred_services", [])):
        assumptions.append("requirements.full_text_search is false, so no search service is recommended, although "
                           "projects of this type usually add one")
    result = _store_billing(_reuse_services(result, fields), fields)
    assumptions += _deferred(result, fields)
    db = result["stack"]["database"]
    if db.get("managed_offering") and db["managed_offering"] == (
            load_kb()["index"][db["pick"]["id"]].get("managed_offerings") or {}).get("onprem_single"):
        assumptions.append("requirements.availability not given and the project is small: the database runs on one "
                           "server with nightly backups copied off the machine, with no standby or automated failover; "
                           "state a target of 99.9 or higher to plan and price a replica")
    stack = {l: _component(l, result["stack"][l], origin, fields, result) for l in LAYERS}
    stack["supporting"] = _supporting(result, fields)
    style = _style(result)
    cost = _cost(result, fields)
    if any(w["code"] == "BUDGET_INFEASIBLE" for w in warnings):
        assumptions.append(f"Relaxed: budget (budget.monthly_infra_usd). No stack that meets the other hard constraints "
                           f"fits ${fields['budget.monthly_infra_usd']:,.0f} a month, so this recommendation relaxes "
                           f"the budget: it still meets the compliance, data residency and deployment rules, and "
                           f"costs ${cost['min']:,}-{cost['max']:,} a month against your "
                           f"${fields['budget.monthly_infra_usd']:,.0f}")
    worst = {w["severity"] for w in warnings}
    status = "ok_with_warnings" if worst & {"warning", "critical"} else "ok"
    return dict(head, status=status, summary=_summary(result, stack, style, cost, fields, answers), architecture_style=style,
                stack=stack, estimated_monthly_cost_usd=cost, warnings=warnings, assumptions=assumptions,
                validation_errors=[])
