"""Architecture style, supporting services and cost estimate for a chosen stack."""
from __future__ import annotations

from .kb import CLOUD_NAMES, load_kb
from .profile import TIER_LABELS, TIER_NAMES, USD_PER_INR, typical_users
from .scoring import (
    DERIVED_SHAPES,
    STEADY_TRAFFIC_TIER,
    entry_plan,
    hard_constraints,
    plan_price,
    seat_cost,
    self_hosted_baas,
    shape_models,
    specialist_reason,
    static_site,
    tier_cost,
    usage_cost,
)

HYPERSCALER = ("aws", "gcp", "azure")

# Ops budget: how many extra systems (cache, secondary store, analytics store, ingestion log, search
# engine) a team can reasonably run next to its app and primary database. A judgement call, stated
# as such in the output: (largest team size in the band, extra systems allowed).
OPS_BUDGET = [(2, 1), (5, 2), (12, 4)]


# Extra monthly cost of a database the team runs itself because its vendor has no managed service on the
# host's cloud (backup storage, monitoring, standby capacity), as a multiple of the managed price band.
# A planning allowance, stated as one in the cost line.
SELF_MANAGED_COST_FACTOR = 1.25


def ops_budget(team: int) -> int | None:
    """Extra systems allowed for a team of this size; None means no cap."""
    for top, cap in OPS_BUDGET:
        if team <= top:
            return cap
    return None


def portable_offering(item: dict, host: dict, onprem: bool, hybrid: bool, no_hyperscaler: bool = False) -> str | None:
    """Managed offering for a datastore. Under hybrid deployment, name the cloud service and its
    on-premises twin (same engine and version), so the same code runs in both places. With AWS, Google Cloud and
    Azure ruled out, an offering that names one of them gives way to the self-managed setup."""
    offers = item.get("managed_offerings", {})
    cloud = offers.get("onprem" if onprem else host.get("provider")) or offers.get("any")
    if no_hyperscaler and cloud and any(n in cloud for n in ("Amazon", "AWS", "Azure", "Google", "Cloud SQL", "Atlas")):
        cloud = offers.get("onprem") or cloud
    if hybrid and not onprem and offers.get("onprem"):
        cloud = (cloud or "a managed " + item["name"]).replace(" / Aurora", "").replace(" (+ RDS Proxy for serverless)", "")
        twin = offers["onprem"][0].lower() + offers["onprem"][1:]
        return f"{cloud} in the cloud; {twin} on-premises (same engine and version)"
    return cloud


def database_offering(db: dict, host: dict, p: dict) -> str:
    """The managed offering the stack's database runs as on this host (the API's host under split hosting)."""
    # 3. Self-managed cloud VMs (EC2-style or a VPS such as Hetzner) run the database themselves, as on-premises.
    onprem = host.get("kind") == "onprem" or (bool(p.get("self_managed")) and (host.get("vm", False) or host.get("kind") == "vps"))
    return portable_offering(db, host, onprem, p["deployment"] == "hybrid", p.get("cloud_preference") == "no_hyperscaler") or \
        f"a managed {db['name']} service in the same region as your compute"


def usable_plans(db: dict, offer: str, p: dict) -> list[dict]:
    """Entry plans (and the host's own smallest plans) that the stack can actually buy: the plan's vendor is the
    managed offering named for this host, or the database's own vendor (BigQuery); under HIPAA, only plans
    whose vendor signs a Business Associate Agreement for them."""
    hipaa = "hipaa" in p["compliance"]
    return [ep for ep in db.get("entry_plans", []) + db.get("host_plans", [])
            if (ep.get("vendor", ep["name"]) in offer or ep.get("vendor", ep["name"]) in db["name"])
            and (ep.get("baa") or not hipaa)]


def with_usable_plans(db: dict, offer: str, p: dict) -> dict:
    """The database item with only the plans usable on this host, for pricing (see usable_plans)."""
    if "entry_plans" not in db and "host_plans" not in db:
        return db
    return dict(db, entry_plans=usable_plans(db, offer, p))


def _env(p: dict, host: dict) -> dict:
    """The constraints every supporting service must respect."""
    return {"onprem": p["deployment"] == "on_prem" or host.get("kind") == "onprem",
            "india": "data_residency_india" in p["compliance"],
            "eu": "data_residency_eu" in p["compliance"],
            "hipaa": "hipaa" in p["compliance"],
            "hybrid": p["deployment"] == "hybrid",
            "air_gapped": bool(p.get("air_gapped")),
            # The team runs its own software on cloud VMs: no managed database, identity or monitoring service.
            "self_managed": bool(p.get("self_managed")) and p["deployment"] == "cloud",
            "cloud": host.get("provider") if host.get("provider") in HYPERSCALER else None,
            "no_hyperscaler": p.get("cloud_preference") == "no_hyperscaler"}


def _app_host_kind(stack: dict) -> str:
    """How the server code is hosted, for the availability text: serverless (the platform spreads functions
    across zones), static (files from a CDN edge, no app server) or instances (you run 2+ behind a load balancer)."""
    h = stack.get("api_host") or stack["hosting"]
    if h.get("kind") in ("faas", "frontend_paas") or h.get("id") in REQUEST_BILLED:
        return "serverless"
    return "static" if h.get("kind") == "static_cdn" else "instances"


def architecture(p: dict, d: dict, stack: dict) -> dict:
    """Pick the architecture style (static, BaaS-first, serverless, services, modular monolith) plus redundancy plan."""
    team, tier = p["team_size"], d["compute_tier"]
    backend = stack["backend"]
    pref = p["architecture"]
    onprem = p["deployment"] == "on_prem" or stack["hosting"].get("kind") == "onprem"
    sources = ["https://martinfowler.com/bliki/MonolithFirst.html",
               "https://martinfowler.com/articles/microservice-trade-offs.html"]
    if backend.get("kind") == "none":
        style = "Static site (pre-built pages on a CDN)"
        why = ("Users only read what the team publishes, so every page is built at deploy time and served as files: "
               "no server code or database to run, patch or pay for. Add an API or a BaaS when users need to sign in, post or pay. "
               f"About {p['dau']:,} daily users read pages from the CDN.")
        sources = ["https://docs.astro.build/en/guides/content-collections/"]
        return {"style": style, "why": why, "sources": sources,
                "redundancy": "The CDN serves the pre-built pages from many locations; the git repository is the backup."}
    if backend.get("kind") == "baas" and onprem:
        style = f"BaaS-first, self-hosted ({backend['name'].split(' (')[0]} containers on your servers + thin functions)"
        why = (f"The self-hosted {backend['name'].split(' (')[0]} stack covers auth, data access and realtime, but your team runs "
               "its containers, upgrades and backups; put custom logic in a few functions until it outgrows them.")
    elif backend.get("kind") == "baas":
        style = "BaaS-first (managed backend + thin server-side functions)"
        why = "A backend-as-a-service covers auth, data access and realtime; put custom logic in a few functions until it outgrows them."
    elif backend.get("kind") == "faas" or d["architecture"] == "serverless":
        style = "Serverless, event-driven"
        why = "Request-scoped functions scale to zero and remove server management; keep functions small and stateless."
    elif d["architecture"] == "microservices" or (pref == "auto" and team >= 15 and tier >= 3):
        style = "Service-oriented (a few coarse services, one per team)"
        why = f"{team} engineers at {d['tier_label']} benefit from independently deployable services, one per team."
        sources.append("https://martinfowler.com/bliki/ConwaysLaw.html")
    else:
        style = "Modular monolith"
        why = f"With {team} engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later."
    if pref not in ("auto",) and d["architecture"] != pref:
        why += f" (Your preference '{pref}' was overridden; see warnings.)"
    from .export import _num
    why += (f" Sized for ~{_num(d['peak_rps']) if d['peak_rps'] else '<0.1'} requests/s at peak, about "
            f"{_num(d['data_12mo_gb'])} GB of data within 12 months and a {d['availability']:g}% availability target.")
    if single_instance(stack) and backend.get("kind") != "baas" and d["availability"] >= 99.9:
        # A second instance would need its own copy of the database file, so no redundancy is possible.
        db = short_name(stack["database"])
        redundancy = (f"Single instance: {db} is one local file, so the app cannot run a second instance and a "
                      f"restart or host failure is downtime. This stack does not meet the {d['availability']:g}% "
                      "target; it needs a server database with automated failover")
        return {"style": style, "why": why, "redundancy": redundancy, "sources": sources}
    if onprem:
        redundancy = {99.0: "Single server + nightly backups copied off the machine",
                      99.9: "2+ app instances behind a load balancer, database replica with automated failover (e.g. Patroni)",
                      99.95: "App and database spread over two separate locations (different hosts and racks or rooms), health checks, zero-downtime deploys",
                      99.99: "Two data centres with tested failover, 24x7 on-call"}
    elif backend.get("kind") == "baas":
        redundancy = {99.0: f"{backend['name'].split(' (')[0]} runs the backend; keep daily backups/exports of your data",
                      99.9: f"{backend['name'].split(' (')[0]} runs the backend on a paid plan; turn on point-in-time recovery and check the plan's uptime commitment",
                      99.95: f"Paid {backend['name'].split(' (')[0]} plan with an uptime SLA, point-in-time recovery, and a status page your users can see",
                      99.99: f"Above most BaaS plan SLAs: needs an enterprise {backend['name'].split(' (')[0]} contract or your own multi-region backend"}
    elif _app_host_kind(stack) == "serverless":
        redundancy = {99.0: "The platform runs the functions across zones, with no instances for you to run; daily database backups",
                      99.9: "The platform runs the functions across zones, with no instances for you to run; managed DB with automated failover",
                      99.95: "Platform-managed functions across zones; multi-AZ database, health checks, zero-downtime deploys",
                      99.99: "Platform-managed functions across zones + multi-region database failover drills, 24x7 on-call"}
    elif _app_host_kind(stack) == "static":
        redundancy = {99.0: "Pages are served from the CDN edge, with no app server to run; daily database backups",
                      99.9: "Pages are served from the CDN edge, with no app server to run; managed DB with automated failover",
                      99.95: "CDN edge for pages; multi-AZ database, health checks, zero-downtime deploys",
                      99.99: "CDN edge for pages + multi-region database failover drills, 24x7 on-call"}
    else:
        redundancy = {99.0: "Single instance + daily backups",
                      99.9: "2+ app instances behind a load balancer, managed DB with automated failover",
                      99.95: "Multi-AZ app and database, health checks, zero-downtime deploys",
                      99.99: "Multi-AZ everywhere + multi-region failover drills, 24x7 on-call"}
    text = redundancy.get(d["availability"], "")
    if text and "availability" in d.get("defaulted", ()) and d["availability"] > 99.0:
        # The bill prices no redundancy for a target nobody stated (_avail), so the text says so.
        text += f" (not priced: no availability target was stated; {d['availability']:g}% is the default goal)"
    return {"style": style, "why": why, "redundancy": text, "sources": sources}


# Document corpus above which full-text search gets its own engine (inverted index, ranking).
SEARCH_CORPUS_GB = 100



def document_corpus_gb(d: dict) -> float:
    """Planning estimate of the document part of the data (the corpus a text search indexes): the 12-month
    total split over the data shapes the way data_fit weighs them, the primary shape counting double. With
    no document shape there is no document corpus."""
    shapes = [d["primary_shape"], *d["secondary_shapes"]]
    if "document" not in shapes:
        return 0.0
    share = (2 if d["primary_shape"] == "document" else 1) / (1 + len(shapes))
    return d["data_12mo_gb"] * share


# Built-in text search of the primary database, used before adding a search engine.
BUILTIN_SEARCH = {"postgres": "Postgres full-text search", "timescaledb": "Postgres full-text search",
                  "mysql": "MySQL FULLTEXT indexes", "mongodb": "MongoDB text indexes (Atlas Search on Atlas)",
                  "sqlite": "SQLite FTS5", "clickhouse": "ClickHouse token/ngram indexes",
                  "sqlserver": "SQL Server full-text search"}
BUILTIN_SEARCH_DOCS = {"postgres": "https://www.postgresql.org/docs/current/textsearch.html",
                       "timescaledb": "https://www.postgresql.org/docs/current/textsearch.html",
                       "mysql": "https://dev.mysql.com/doc/refman/8.4/en/fulltext-search.html",
                       "mongodb": "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-text/",
                       "sqlite": "https://www.sqlite.org/fts5.html",
                       "clickhouse": "https://clickhouse.com/docs",
                       "sqlserver": "https://learn.microsoft.com/en-us/sql/relational-databases/search/full-text-search"}

# Job queues a functions-only platform delivers to functions, by hosting provider: (name, source).
PLATFORM_QUEUES = {"aws": ("Amazon SQS with a Lambda consumer", "https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html"),
                   "cloudflare": ("Cloudflare Queues (a Worker consumes each batch)", "https://developers.cloudflare.com/queues/"),
                   "": ("A hosted HTTP queue that calls your functions (e.g. Upstash QStash)",
                        "https://upstash.com/docs/qstash/overall/getstarted")}


def _redis_offering(text: str, env: dict) -> str:
    """Keep the cache offering inside the residency and HIPAA limits."""
    if env["india"] and env["hipaa"] and ("Workers KV" in text or "Upstash" in text):
        return "Self-managed Valkey in your Indian region, on servers covered by your host's BAA"
    if env["india"] and ("Workers KV" in text or "Upstash" in text):
        return "Upstash Redis in its Mumbai region, or self-managed Valkey in your Indian region"
    if env["hipaa"] and "Upstash" in text:
        return "Upstash Redis (Enterprise plan with a signed BAA), or keep sessions in the primary database"
    return text


def analytics_only_excluded(items: list[dict], db_candidates: list[dict], p: dict, d: dict) -> list[dict]:
    """Databases kept out of the primary role only by a poor fit for the primary data shape or by a
    strong-consistency requirement. Neither applies to an analytical or search store: it holds a derived
    copy fed from the system of record and serves only that shape, so such a store (a columnar store or a
    search engine for a document or relational project) stays a candidate for the supporting store."""
    have = {c["id"] for c in db_candidates}
    out = []
    for it in items:
        if it["id"] in have:
            continue
        reasons = hard_constraints("database", it, p, d)
        if reasons and all(r[1] in ("data_shapes", "consistency") for r in reasons):
            out.append({"id": it["id"], "name": it["name"], "item": it})
    return out


def supporting_services(p: dict, d: dict, stack: dict, db_candidates: list[dict]) -> list[dict]:
    """Every service the stack needs. Each one names the extra system it adds to operate (if any) and,
    when it can wait, the trigger for adding it. Services follow the stack and the deployment,
    residency and HIPAA inputs: no cloud-only service on-premises, no service without an Indian or
    EU region under a residency rule, no service without a BAA under HIPAA."""
    kb = load_kb()
    # The services sit next to the API: under split hosting that is the API's host, not the frontend platform.
    be, db, host = stack["backend"], stack["database"], stack.get("api_host") or stack["hosting"]
    prov = host.get("provider", "")
    env = _env(p, host)
    tier = d["compute_tier"]
    out = []

    def offering(dbid: str) -> str:
        text = portable_offering(kb["index"][dbid], host, env["onprem"] or env["self_managed"], env["hybrid"],
                                 env["no_hyperscaler"]) or \
            f"a managed {kb['index'][dbid]['name']} service in the same region as your compute"
        return _redis_offering(text, env) if dbid == "redis" else text

    def add(role, name, why, source, cost_id=None, cost_tier=None, system=None, trigger=None, usage=None):
        out.append({"role": role, "name": name, "why": why, "source": source, "cost_id": cost_id,
                    "cost_tier": cost_tier, "system": system, "trigger": trigger, "usage": usage})

    # Candidates come first so they win ties. Every shape except analytical and search is part of the record, so its
    # secondary store must pass the same constraints as the primary.
    analytics_pool = db_candidates + analytics_only_excluded(kb["database"], db_candidates, p, d)
    kv_hot = d["primary_shape"] == "key_value" and tier >= 1
    if be.get("kind") != "none" and db["id"] != "redis" and ((p["read_write"] == "read_heavy" and tier >= 2) or (p["latency_target_ms"] <= 100 and tier >= 1) or kv_hot):
        add("Cache", f"Redis/Valkey ({offering('redis')})",
            "Read-heavy traffic, a tight latency target or hot key-value data: keep hot reads and sessions in memory "
            "in front of a durable primary database.",
            "https://redis.io/docs/latest/develop/use/client-side-caching/", "redis", tier, "redis",
            None if tier >= 3 or kv_hot else "when p95 read latency passes your target or database CPU stays above ~60%")

    if p["realtime"] in ("core", "some"):
        if be.get("kind") == "baas":
            add("Realtime", "Built-in realtime of " + be["name"], "Subscriptions/listeners are provided by the BaaS; no socket server needed.",
                be["sources"][0])
        elif host.get("kind") in ("faas", "frontend_paas") or be.get("kind") == "faas":
            name = ("API Gateway WebSockets" if prov == "aws" else
                    "Managed pub/sub with a signed BAA (e.g. Ably or PubNub HIPAA plans)" if env["hipaa"] else
                    "Managed pub/sub (Ably, Pusher, or API Gateway WebSockets)")
            add("Realtime", name,
                "Your compute is request-scoped and cannot hold WebSocket connections; offload them to a managed realtime service.",
                "https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-websocket-api.html")
        elif p["realtime"] == "core":
            phoenix = be["id"] == "phoenix"
            name = "Phoenix PubSub (built in)" if phoenix else f"Redis pub/sub for cross-instance fan-out ({offering('redis')})"
            add("Realtime", name, "With several app instances, a message published on one must reach sockets on all others.",
                "https://redis.io/docs/latest/develop/interact/pubsub/",
                None if phoenix else "redis", None if phoenix else tier, None if phoenix else "redis")
        elif be.get("id") in WEBSOCKET_LIBS:
            lib, src = WEBSOCKET_LIBS[be["id"]]
            add("Realtime", f"WebSockets in the {short_name(be)} app ({lib})",
                "Chat and live updates for a part of the product: the app server holds the connections itself; add "
                "Redis pub/sub only when a second instance must reach the same users.", src)
        if p["app_type"] == "realtime_collab" and p["realtime"] == "core" and be.get("kind") != "baas":
            add("Collaboration sync", "Yjs shared documents (CRDTs) synced over the WebSocket connection, with Hocuspocus "
                "or y-websocket as the sync server", "Many people editing one document at once need conflict-free "
                "merging; CRDTs merge concurrent edits without locks, and the server stores snapshots, not every stroke.",
                "https://docs.yjs.dev/")

    secondary: dict[str, tuple[dict, list[str]]] = {}  # store id -> (candidate, shapes it serves)
    # A specialist store kept out of the primary role only because the project also has records it should not hold
    # (scoring.specialist_reason) serves its own shape beside the primary, the primary shape included.
    demoted = [{"id": it["id"], "name": it["name"], "item": it} for it in kb["database"]
               if it.get("system_of_record") and it["id"] not in {c["id"] for c in db_candidates}
               and specialist_reason(it, p, d)
               and all(r[0] == specialist_reason(it, p, d) for r in hard_constraints("database", it, p, d))]
    redis_listed = any(x["cost_id"] == "redis" for x in out)
    for shape in d["secondary_shapes"] + ([d["primary_shape"]] if shape_models(db, d)[d["primary_shape"]] < 4 else []):
        if shape == d["primary_shape"] and shape not in d["secondary_shapes"]:
            best = max((c for c in demoted if shape_models(c["item"], d)[shape] >= 4
                        and not (c["id"] == "redis" and redis_listed)),
                       key=lambda c: shape_models(c["item"], d)[shape], default=None)
            if best:
                secondary.setdefault(best["id"], (best, []))[1].append(shape)
            continue
        if shape_models(db, d)[shape] >= 4:
            if shape == "vector" and db["id"] in ("postgres", "timescaledb"):
                add("Vector search", "pgvector extension in the primary Postgres",
                    "Keeps embeddings next to relational data with transactional consistency; move to a dedicated vector DB only past ~10M+ vectors.",
                    "https://github.com/pgvector/pgvector")
            continue
        if shape == "search" and db["id"] in BUILTIN_SEARCH and d["data_12mo_gb"] < SEARCH_CORPUS_GB:
            continue  # the database's own text index serves a small corpus (the Search line below says so)
        # Prefer a store with a managed service on the host's cloud over one the team would have to run itself.
        # Among equal fits, a store of another cloud (BigQuery for an AWS app) loses to one that runs anywhere, and
        # one native to the host's cloud wins.
        best = max((c for c in (analytics_pool if shape in DERIVED_SHAPES else db_candidates + demoted) if c["id"] != db["id"]),
                   key=lambda c: (shape_models(c["item"], d)[shape], c["item"].get("cloud") in (None, prov),
                                  prov not in (c["item"].get("self_managed_on") or {}), c["item"].get("cloud") == prov),
                   default=None)
        if best and shape_models(best["item"], d)[shape] >= 4:
            secondary.setdefault(best["id"], (best, []))[1].append(shape)
    # One store serving several shapes is one system to run, so it is listed (and priced) once.
    for best, shapes in secondary.values():
        label = ", ".join(s.replace("_", " ") for s in shapes)
        fits = "; ".join(f"'{s.replace('_', ' ')}' {shape_models(db, d)[s]}/5 against {shape_models(best['item'], d)[s]}/5"
                         for s in shapes)
        # Priced by what it holds: beside an analytics or search primary, a store of records (accounts, settings,
        # metadata) holds rows that grow with the users, not the analytics volume, so it takes the traffic's tier.
        holds_records = d["primary_shape"] in DERIVED_SHAPES and not set(shapes) & set(DERIVED_SHAPES)
        add(f"Secondary store ({label})", f"{best['name']} ({offering(best['id'])})",
            f"Your primary database fits your data less well than {best['name']}: {fits}."
            + (f" It holds the records, not the ~{d['data_12mo_gb']:,.0f} GB in {db['name']}, so it is priced at the traffic's scale."
               if holds_records else ""),
            best["item"]["sources"][0], best["id"], tier if holds_records else d["db_tier"], best["id"],
            f"when {label} queries on {db['name']} get slow or awkward (more than ~2 s, or several lookups per request)")

    # Columnar store for aggregations: at large traffic for event-heavy apps, or for a dashboard
    # whose own data passes ~100 GB in a year (row-store scans slow down well before traffic does).
    big_dashboard = p["app_type"] == "analytics_dashboard" and d["data_12mo_gb"] >= 100
    if p["app_type"] in ("analytics_dashboard", "iot_telemetry", "ecommerce", "social_network") \
            and (tier >= 3 or big_dashboard) and shape_models(db, d)["analytical"] < 4 and "analytical" not in d["secondary_shapes"]:
        # On Google Cloud the warehouse is BigQuery (serverless, native); elsewhere ClickHouse, which runs anywhere.
        wh = "bigquery" if env["cloud"] == "gcp" and not env["hybrid"] else "clickhouse"
        short = kb["index"][wh]["name"].replace("Google ", "")
        label = offering(wh) if offering(wh).startswith(short) else f"{short} ({offering(wh)})"
        add("Analytics", f"{label} fed by a continuous copy of database changes",
            "Run heavy aggregations on a columnar store instead of the transactional database.",
            # Priced at the app's scale: by the data it copies when data volume is the trigger, by traffic otherwise.
            kb["index"][wh]["sources"][0], wh, d["db_tier"] if big_dashboard else tier, wh,
            None if big_dashboard else "when dashboard or reporting queries on the primary database take more than ~2 s")

    # Write volume follows the users and the request rate; open connections alone (users online at once) do not
    # need a log in front of the database.
    if p["app_type"] == "iot_telemetry" or (p["read_write"] == "write_heavy" and d["dau_tier"] >= 3):
        managed = {"aws": "Amazon Kinesis / MSK", "gcp": "Google Pub/Sub", "azure": "Azure Event Hubs"}.get(
            "" if env["hybrid"] else env["cloud"] or "", "Redpanda/Kafka or NATS JetStream")
        add("Ingestion buffer", managed + (" (MQTT via AWS IoT Core)" if prov == "aws" and p["app_type"] == "iot_telemetry" else ""),
            "A durable log absorbs write bursts and keeps device ingestion separate from database writes, and lets you replay messages.",
            "https://kafka.apache.org/documentation/#design", system="ingestion",
            trigger=None if p["app_type"] == "iot_telemetry" else "when write bursts push database write latency up or requests start timing out")
    else:
        jobs = {"node": "BullMQ (Redis)", "python": "Celery / RQ / Dramatiq (Redis/Valkey broker)", "ruby": "Sidekiq (Redis/Valkey)",
                "elixir": "Oban",
                "jvm": "Spring Batch / SQS listeners" if prov == "aws" and not env["hybrid"] and not env["self_managed"]
                else "Spring Batch / JobRunr",
                "dotnet": "Hangfire / Azure Queue" if prov == "azure" and not env["hybrid"] and not env["self_managed"]
                else "Hangfire",
                "go": "River / Asynq", "php": "Laravel Queues"}
        if be.get("kind") == "server" and host.get("kind") in ("faas", "frontend_paas") and not stack.get("api_host"):
            # Functions-only hosting has no always-on process to run a worker or hold a queue connection,
            # so the queue must be one the platform delivers to functions.
            name, src = PLATFORM_QUEUES.get(prov, PLATFORM_QUEUES[""])
            add("Background jobs", name,
                f"Send emails, process uploads and call slow APIs outside the request path. {stack['hosting']['name']} "
                "runs only short request-scoped functions, so a worker-process queue (BullMQ, Celery, Sidekiq) has nowhere "
                "to run; use a queue that calls your functions with each job.", src)
        elif be.get("kind") == "server":
            worker_on = f" (worker on {stack['api_host']['name']})" if stack.get("api_host") else ""
            lang = be.get("language")
            why = "Send emails, process uploads and call slow APIs outside the request path."
            # Redis that a line always kept (realtime fan-out) already adds; a cache line that can be deferred
            # does not count, since the queue would still need Redis without it.
            already = db["id"] == "redis" or any(x["cost_id"] == "redis" and not x["trigger"] for x in out)
            if lang == "ruby" and not already:
                # Rails' default queue keeps jobs in the app's own database, so no Redis instance is needed.
                add("Background jobs", "Solid Queue (Rails default, jobs in your database)" + worker_on, why,
                    "https://guides.rubyonrails.org/active_job_basics.html")
            elif lang in QUEUE_NEEDS_REDIS and not already and tier <= 1 and d["budget_usd"] <= 0                     and db["id"] in DB_QUEUES:
                # On a $0 budget at small scale a Redis instance is one more plan to pay for or keep under a free
                # quota: the jobs live in the database the app already has.
                name, src = DB_QUEUES[db["id"]].get(lang, DB_QUEUES[db["id"]][""])
                add("Background jobs", name.format(db=db["name"].split(" (")[0]) + worker_on,
                    why + " On a $0 budget the jobs table lives in your database, so no Redis instance is needed; "
                    f"add {QUEUE_NEEDS_REDIS[lang][0]} on Redis when job volume outgrows it.", src)
            elif lang in QUEUE_NEEDS_REDIS and db["id"] != "redis":
                # These queues keep their jobs in Redis, so the instance is a running cost. It is listed
                # (and priced) here unless it is already there.
                why += f" {QUEUE_NEEDS_REDIS[lang][0]} keeps its jobs in Redis, so the app needs a Redis/Valkey instance"
                why += " (the one already listed above)." if already else f" ({offering('redis')})."
                add("Background jobs", jobs[lang] + worker_on, why, QUEUE_NEEDS_REDIS[lang][1],
                    None if already else "redis", None if already else tier, "redis")
            else:
                add("Background jobs", jobs.get(lang, "A job queue") + worker_on, why, "https://12factor.net/processes")

    static = be.get("kind") == "none"
    work = set(p.get("special_workloads") or [])
    if "search" in d["secondary_shapes"]:
        work.add("text_search")  # a search shape the primary store does not serve well is a search workload
    # The primary store is a search engine, or a secondary store above already serves the search shape.
    search_served = db["models"]["search"] >= 4 or any("search" in shapes for _, shapes in secondary.values())
    doc_gb = document_corpus_gb(d)
    big_corpus = doc_gb >= SEARCH_CORPUS_GB
    builtin = BUILTIN_SEARCH.get(db["id"])
    small_search = "text_search" in work and not big_corpus and builtin and d["data_12mo_gb"] < SEARCH_CORPUS_GB
    if search_served:
        pass  # the stack already has its search engine
    elif not static and small_search:
        add("Search", f"{builtin} to start; Meilisearch/Typesense/OpenSearch past ~{SEARCH_CORPUS_GB} GB or when "
            "facets & typo-tolerance matter",
            f"About {d['data_12mo_gb']:,.0f} GB of data in a year fits the database's own text index; a separate search "
            "cluster would add a second system and its bill before it is needed.", BUILTIN_SEARCH_DOCS[db["id"]])
    elif not static and ("text_search" in work or big_corpus):
        engine = ("OpenSearch (self-hosted)" if env["onprem"] or env["hybrid"] else
                  {"aws": "Amazon OpenSearch Service", "gcp": "Elastic Cloud on Google Cloud, or self-managed OpenSearch on GKE",
                   "azure": "Azure AI Search"}.get(env["cloud"] or "", "Meilisearch or Typesense (cloud or self-hosted); OpenSearch past ~10M documents"))
        if big_corpus:
            size = (f"~{doc_gb:,.0f} GB of documents" if doc_gb >= d["data_12mo_gb"] else
                    f"~{doc_gb:,.0f} GB of documents (an estimate: the document share of your ~{d['data_12mo_gb']:,.0f} GB "
                    f"total, from your {len(p['data_shapes'])} data shapes)")
        else:
            size = f"your data (up to ~{d['data_12mo_gb']:,.0f} GB in total within 12 months; the searchable part may be smaller)"
        add("Search", engine, f"Search across {size} needs an inverted index with relevance "
            "ranking, highlighting and filters; database text indexes slow down and rank poorly at this size.",
            "https://opensearch.org/docs/latest/", system="search")
    elif p["app_type"] in ("ecommerce", "content_site", "social_network") or (p["app_type"] == "saas" and tier >= 3):
        if static:
            add("Search", "Pagefind (a static search index built at deploy time)",
                "Full-text search for a static site with no server: the index ships with the pages.", "https://pagefind.app/")
        elif builtin:
            add("Search", f"{builtin} to start; Meilisearch/Typesense/OpenSearch when facets & typo-tolerance matter",
                "Catalogue/content search with relevance tuning outgrows LIKE queries quickly.", "https://www.meilisearch.com/docs")
        else:
            engine = ("Meilisearch / Typesense / OpenSearch (self-hosted)" if env["onprem"] else
                      "Typesense or Algolia (Firebase extensions sync Firestore to them)" if db["id"] == "firestore" else
                      "Meilisearch / Typesense / OpenSearch")
            add("Search", engine, f"{db['name']} has no full-text search, so text search needs a separate index.",
                "https://www.meilisearch.com/docs", system="search",
                trigger="when users need to search posts, products or people by text")

    _special_workloads(p, d, env, add, has_storage=lambda: any(x["role"] == "Object storage" for x in out),
                       storage=lambda: _object_storage(env, prov))

    takes_money = "pay" in d["user_actions"] or (p["app_type"] in ("ecommerce", "fintech") and "user_actions" in d["defaulted"])
    if takes_money and env["air_gapped"]:
        add("Payments", "Payments taken outside the air-gapped network, by a separate connected system whose records "
            "are imported and reconciled", "No payment gateway can be reached from a network with no internet; "
            "keeping card data out entirely also keeps the isolated network out of PCI-DSS scope.",
            "https://www.pcisecuritystandards.org/document_library/")
    elif takes_money:
        pg = "Razorpay / Cashfree (India) or Stripe" if "india" in p["regions"] else "Stripe / Adyen"
        add("Payments", f"{pg} with hosted checkout (card tokens)",
            "Card data never touches your servers, which keeps your PCI-DSS audit scope to the smallest self-assessment form (SAQ A).",
            "https://www.pcisecuritystandards.org/document_library/")

    home = spa_static_home(stack) if d["web"] and not env["onprem"] else None
    if home:
        name, src, per_gb, fee = home
        why = (f"{short_name(stack['frontend'])} is built to static files (HTML, JavaScript, CSS): a bucket behind the "
               f"cloud's CDN serves them from the edge, so the {short_name(be)} instances on {host['name']} only answer "
               "API calls, and a frontend release is an upload plus a cache invalidation.")
        if per_gb is None:
            add("Static frontend", name, why, src, "aws_s3_cloudfront", tier)
        else:
            gb = p["dau"] * 30 * SPA_MB_PER_USER_DAY / 1024
            usd = fee + gb * per_gb
            basis = (f"~{SPA_MB_PER_USER_DAY:g} MB of files per active user a day (~{gb:,.0f} GB a month) at ${per_gb:g}/GB"
                     + (f" plus the ${fee:g} monthly base fee" if fee else "") + f" ({SPA_STATIC_PRICE_SOURCES[prov]})")
            add("Static frontend", name, why, src, usage=(usd, usd, basis))
    if p.get("cacheable_share") == "most" and not static and be.get("kind") != "baas":
        add("CDN", "Cloudflare or CloudFront in front of the app",
            "You said most requests return the same content to everyone; a CDN answers them without touching the servers, "
            "so the servers are sized for the remaining share.",
            "https://developers.cloudflare.com/cache/concepts/default-cache-behavior/")

    if static:
        pass  # images live in the repository and are served by the host's CDN
    elif p["app_type"] in ("social_network", "content_site", "ecommerce", "healthcare", "ml_product") or d["mobile"]:
        if be["id"] == "firebase":
            add("Object storage", "Cloud Storage for Firebase (included in the Firebase project)",
                "Media and documents belong in object storage, not the database; Firebase security rules cover both.",
                "https://firebase.google.com/docs/storage")
        elif be["id"] == "supabase" and not env["onprem"]:
            add("Object storage", "Supabase Storage (included, with a CDN)",
                "Media and documents belong in object storage, not the database; row-level security policies cover both.",
                "https://supabase.com/docs/guides/storage")
        elif not any(x["role"] == "Object storage" for x in out):
            add("Object storage", _object_storage(env, prov), "Media and documents belong in object storage, not the database.",
                "https://aws.amazon.com/s3/")

    if be.get("kind") != "baas" and "sign_in" in d["user_actions"]:
        add("Authentication", _auth(env), "Do not hand-roll password storage, MFA or SSO.",
            "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html")
    if p.get("enterprise_sso"):
        sso = be.get("sso")
        if sso:
            mau = p["dau"] / SSO_DAU_PER_MAU
            extra = max(0.0, mau - sso["free_mau"]) * sso["usd_per_mau"]
            add("Enterprise SSO", sso["name"], "Customers log in with their own identity provider (Entra ID / Azure AD, "
                "Okta, Google Workspace) over SAML or OIDC.", sso["source"],
                usage=(extra, extra, f"~{mau:,.0f} monthly SSO users ({SSO_DAU_PER_MAU:.0%} of them active on a day), "
                                     f"{sso['free_mau']} included, then ${sso['usd_per_mau']} each"))
            # The budget check prices the bill without usage terms (estimate_cost usage=False), the same at every user
            # count of a tier; the per-user SSO price is too large to leave out, so it counts the tier's typical users.
            typical = typical_users(p, d["compute_tier"]) / SSO_DAU_PER_MAU
            tier_extra = max(0.0, typical - sso["free_mau"]) * sso["usd_per_mau"]
            out[-1]["tier_usage"] = (tier_extra, tier_extra, f"~{typical:,.0f} monthly SSO users, typical of the "
                                     f"{TIER_NAMES[d['compute_tier']]} scale tier")
        elif env["air_gapped"]:  # cloud identity providers are unreachable; the directory inside the network is not
            add("Enterprise SSO", "Keycloak (self-hosted) federating your on-premises directory (Active Directory or "
                "another LDAP server) over LDAPS or Kerberos",
                "An air-gapped network cannot reach a cloud identity provider (Entra ID, Okta, Google Workspace); Keycloak's "
                "user federation reads the accounts and groups from the directory inside the network and gives your API "
                "one OIDC token format.", "https://www.keycloak.org/docs/latest/server_admin/#_user-storage-federation",
                system="keycloak")
        else:
            add("Enterprise SSO", "Keycloak identity brokering (self-hosted, free): each customer's Entra ID / Azure AD, "
                "Okta or Google Workspace over SAML 2.0 or OIDC",
                "Customers log in with their own identity provider; the broker turns each SAML or OIDC login into one "
                "token format for your API.", "https://www.keycloak.org/docs/latest/server_admin/", system="keycloak")

    if p["offline"]:
        if db["id"] == "firestore" or be["id"] == "firebase":
            sync = ("Firestore offline persistence (built into the client SDKs)",
                    "https://firebase.google.com/docs/firestore/manage-data/enable-offline")
        elif db["id"] in ("postgres", "timescaledb") or be["id"] == "supabase":
            sync = ("PowerSync or ElectricSQL: a local SQLite copy on the device kept in sync with Postgres",
                    "https://docs.powersync.com/")
        else:
            sync = ("Local SQLite on the device plus a sync API with per-record version numbers",
                    "https://www.sqlite.org/whentouse.html")
        add("Offline sync", sync[0], "Offline use needs a local copy of the data and conflict handling when the device "
            "reconnects; the primary database does not provide that by itself.", sync[1])

    if "desktop" in p["platforms"]:
        add("Desktop app", "Electron, packaging the web frontend as a Windows, macOS and Linux app",
            "One codebase for web and desktop; Tauri gives smaller installers but needs some Rust for native features.",
            "https://www.electronjs.org/docs/latest/")
    if d["mobile"] and env["air_gapped"]:
        add("Notifications", "In-app and on-device notifications only",
            "Firebase Cloud Messaging and Apple Push Notification service need the internet, which an air-gapped "
            "network does not have.", "https://firebase.google.com/docs/cloud-messaging")
    elif d["mobile"]:
        why = "Standard channel for mobile engagement on Android and iOS."
        if env["hipaa"]:
            why += (" Push services are not covered by a BAA: put no health information in the notification "
                    "text (e.g. 'You have a new message') and show the content only after the user signs in.")
        add("Push notifications", "Firebase Cloud Messaging (+ APNs) or Expo Notifications", why,
            "https://firebase.google.com/docs/cloud-messaging")

    if scoring_model(p):
        # A trained scoring or classification model (credit score, fraud score): a CPU endpoint, not an LLM service.
        where = "" if env["hybrid"] or env["self_managed"] else env["cloud"] or ""
        if not where and host.get("kind") in ("frontend_paas", "faas"):
            where = "functions"  # a function platform runs no container beside the API
        ml, src = SCORING_SERVING.get(where, SCORING_SERVING["self"])
        add("Model serving", ml, "Serve the model from its own endpoint, versioned and monitored apart from the web "
            "tier; a small scoring model runs on CPU.", src)
    elif p["app_type"] == "ml_product" or p.get("ml_features", "none") != "none":
        ml = {"gcp": "Vertex AI endpoints", "aws": "Amazon Bedrock / SageMaker", "azure": "Azure AI Foundry"}.get(
            "" if env["hybrid"] else env["cloud"] or "")
        if not ml and env["hybrid"]:
            ml = "a self-hosted inference server (vLLM) packaged as a container, so it runs in both places"
        if not ml:
            ml = ("a self-hosted inference server (vLLM or Hugging Face TGI) on your own GPUs" if env["onprem"] else
                  "a model API under a signed BAA, or self-hosted vLLM on HIPAA-eligible GPUs" if env["hipaa"] else
                  "self-hosted vLLM on GPUs in your Indian region, or a model API that processes data in India" if env["india"] else
                  "self-hosted vLLM on GPUs in your EU region, or a model API that processes data in the EU" if env["eu"] else
                  "a hosted model API or GPU inference provider")
        add("Model serving", ml, "Keep GPU inference separate from the web tier so each scales on its own metric.",
            "https://cloud.google.com/vertex-ai/docs")

    if static:
        add("Observability", "An uptime check plus the host's web analytics",
            "With no server code there is nothing to trace; watch that the pages are up and how fast they load.",
            "https://web.dev/articles/vitals")
    else:
        if env["hybrid"] and not env["onprem"]:
            # Kubernetes manifests carry over only when the cloud host is Kubernetes; any other container host
            # shares the images, and a function or frontend platform shares the application code.
            if host.get("kind") == "kubernetes":
                split, src = ("Same container images and Kubernetes manifests on-premises and in the cloud",
                              "https://kubernetes.io/docs/concepts/overview/")
            elif (host.get("runs") or {}).get("containers"):
                split, src = (f"Same container images on-premises and in the cloud: {host['name']} in the cloud, "
                              "Docker Compose or Kubernetes on your servers",
                              "https://docs.docker.com/get-started/docker-overview/")
            else:
                split, src = (f"Same application code on-premises and in the cloud: {host['name']} in the cloud, "
                              "the same code packaged as container images on your servers",
                              "https://docs.docker.com/get-started/docker-overview/")
            add("Hybrid split", split,
                "Keep the system of record where your rules require it (usually on-premises) with replicas or a read copy "
                "in the cloud; run the stateless app tier in both, deployed by one pipeline, and avoid cloud-only managed "
                "APIs in the request path.", src)
        add("Observability", f"OpenTelemetry instrumentation -> {_observability(env)}",
            "Traces, metrics and error tracking from day one; required to defend an availability target.",
            "https://opentelemetry.io/docs/")
    regimes = [n for k, n in (("hipaa", "The HIPAA Security Rule"), ("pci_dss", "PCI-DSS")) if k in p["compliance"]]
    if regimes:
        add("Audit & security", "Encrypted storage (KMS), audit logging, least-privilege IAM, WAF",
            f"{' and '.join(regimes)} {'both require' if len(regimes) > 1 else 'requires'} access controls, audit trails and encryption.",
            "https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html" if "hipaa" in p["compliance"]
            else "https://www.pcisecuritystandards.org/document_library/")
    return _distinct_names(out)


def _distinct_names(services: list[dict]) -> list[dict]:
    """One service name per role: the SPA's built files and user uploads can both land in the cloud's bucket + CDN
    (Amazon S3 + CloudFront twice). The uploads line then says it is a second bucket behind the same CDN."""
    names = [s["name"] for s in services]
    for name in {n for n in names if names.count(n) > 1}:
        same = [s for s in services if s["name"] == name]
        keep = next((s for s in same if s["role"] == "Static frontend"), same[0])
        bucket, _, cdn = name.partition(" + ")
        for s in same:
            if s is not keep:
                purpose = "uploaded files" if s["role"] == "Object storage" else s["role"].lower()
                s["name"] = (f"{bucket} (a separate bucket for {purpose}, served through the same "
                             f"{cdn or 'CDN'} as the {keep['role'].lower()})")
    return services


# Usage assumptions for special workloads (planning figures; each is printed with its cost line).
MEDIA_GB_PER_USER_DAY = 0.005         # ~5 MB of images/files served per active user a day
EGRESS_USD_PER_GB = (0.01, 0.09)      # zero-egress object storage (R2) to a hyperscaler CDN
VIDEO_MIN_PER_USER_DAY = 20           # minutes watched or spent in a call per active user a day
VOD_USD_PER_MIN = (0.0008, 0.0012)    # delivered minutes, Cloudflare Stream / Mux list prices
# Video built from object storage + a transcoder + a CDN (S3 + MediaConvert + CloudFront, or the Google Cloud
# equivalents). Planning figures: adaptive HD streams average ~2.7 Mbit/s (~20 MB a minute); one minute is uploaded
# for every 500 watched; transcoding the bitrate ladder costs $0.015-0.03 per uploaded minute (per-output-minute
# list prices of AWS Elemental MediaConvert and the Transcoder API, several renditions). CDN data transfer is billed
# in volume tiers (CloudFront, North America and Europe, per GB a month).
VIDEO_MB_PER_MIN = 20
VIDEO_UPLOAD_SHARE = 0.002
TRANSCODE_USD_PER_MIN = (0.015, 0.03)
CDN_USD_PER_GB_TIERS = [(10_240, 0.085), (51_200, 0.080), (153_600, 0.060), (512_000, 0.040), (1_048_576, 0.030),
                        (5_242_880, 0.025), (float("inf"), 0.020)]  # (cumulative GB up to, price)


def cdn_transfer_usd(gb: float) -> float:
    """Monthly CDN data transfer bill for `gb`, through the volume tiers."""
    usd, prev = 0.0, 0.0
    for top, price in CDN_USD_PER_GB_TIERS:
        if gb <= prev:
            break
        usd += (min(gb, top) - prev) * price
        prev = top
    return usd
LIVE_USD_PER_MIN = (0.0005, 0.004)    # participant-minutes, self-managed SFU on cloud VMs to Daily/Twilio
MAP_LOADS_PER_USER_DAY = 0.3   # map screens (order tracking) are opened on a fraction of visits
# Job queues that store their jobs in Redis (the queue's own docs): language -> (queue, vendor doc).
QUEUE_NEEDS_REDIS = {
    "node": ("BullMQ", "https://docs.bullmq.io/"),
    "python": ("Celery with a Redis broker (or RQ / Dramatiq)",
               "https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html"),
    "ruby": ("Sidekiq", "https://github.com/sidekiq/sidekiq/wiki/Using-Redis"),
}
# Job queues that keep their jobs in the app's own SQL database (row locks with SKIP LOCKED, or a polled jobs table).
_PG_QUEUES = {"node": ("pg-boss (jobs in PostgreSQL)", "https://github.com/timgit/pg-boss"),
              "python": ("Procrastinate (jobs in PostgreSQL)", "https://procrastinate.readthedocs.io/"),
              "": ("A jobs table in {db} polled by a worker", "https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE")}
_SQL_QUEUE = {"": ("A jobs table in {db} polled by a worker", "https://12factor.net/processes")}
DB_QUEUES = {"postgres": _PG_QUEUES, "timescaledb": _PG_QUEUES, "mysql": _SQL_QUEUE, "sqlite": _SQL_QUEUE,
             "sqlserver": _SQL_QUEUE}
MAP_USD_PER_LOAD = (0.0005, 0.005)    # Google Maps / Mapbox dynamic map loads, high-volume tier to list price
OTP_PER_USER_DAY = 0.05               # one SMS login every ~20 days (sessions last weeks)
OTP_USD = {"india": (0.002, 0.005), "other": (0.01, 0.05)}


SSO_DAU_PER_MAU = 0.2  # daily to monthly users, the same planning heuristic the brief reader uses


SMS_BY_CLOUD = {"aws": "Twilio Verify or Amazon SNS / Cognito SMS",
                "gcp": "Twilio Verify or Identity Platform phone sign-in (SMS)",
                "azure": "Twilio Verify or Azure Communication Services SMS"}


def _special_workloads(p: dict, d: dict, env: dict, add, has_storage, storage) -> None:
    """Services for workloads the four main picks do not cover, each with a usage-based cost."""
    work = set(p.get("special_workloads") or [])
    dau30 = p["dau"] * 30
    if work & {"media_uploads", "video_on_demand"} and not has_storage():
        add("Object storage", storage(), "Uploaded files and video belong in object storage, not the database.",
            "https://aws.amazon.com/s3/")
    if "media_uploads" in work and p["app_type"] != "internal_tool":  # staff files: the app serves them, no CDN
        gb = dau30 * MEDIA_GB_PER_USER_DAY
        add("Media delivery", "Your reverse proxy (nginx) serving files from the object store, images resized by "
            "imgproxy on your servers" if env["onprem"] else
            # Uploads under HIPAA hold health information: no public CDN caches them (the storage line says so too).
            "Short-lived signed URLs from the object storage, issued by the API after an access check (no public CDN "
            "for PHI)" if env["hipaa"] else
            "CDN in front of the object storage, with image resizing at the edge",
            "Hand uploads out from the object storage, not the app server; each signed URL expires within minutes and "
            "every download is logged for the HIPAA audit trail." if env["hipaa"] and not env["onprem"] else
            "Serve uploads from the object store through the reverse proxy, not the app server; resize images on the fly "
            "instead of storing every size." if env["onprem"] else
            "Serve uploads from the CDN, not the app server; resize images on the fly instead of storing every size.",
            "https://developers.cloudflare.com/r2/pricing/",
            usage=(gb * EGRESS_USD_PER_GB[0], gb * EGRESS_USD_PER_GB[1],
                   f"~{gb:,.0f} GB served a month ({MEDIA_GB_PER_USER_DAY * 1000:.0f} MB per active user a day) "
                   f"at ${EGRESS_USD_PER_GB[0]}-{EGRESS_USD_PER_GB[1]}/GB"))
    if "video_on_demand" in work:
        name = ("FFmpeg transcoding workers + MinIO + an HLS-serving web server (self-hosted)" if env["onprem"] else
                "S3 + AWS Elemental MediaConvert + CloudFront under the AWS BAA" if env["hipaa"] else
                "S3 + AWS Elemental MediaConvert + CloudFront" if env["cloud"] == "aws" else
                "Transcoder API + Cloud Storage + Cloud CDN" if env["cloud"] == "gcp" else
                "Cloudflare Stream or Mux (upload, transcoding, adaptive streaming and CDN in one)")
        mins = dau30 * VIDEO_MIN_PER_USER_DAY
        watched = f"~{mins / 1e6:,.1f}M minutes watched a month ({VIDEO_MIN_PER_USER_DAY} min per active user a day)"
        if name.startswith("Cloudflare Stream"):
            # One managed service bills per minute delivered, transcoding and CDN included.
            usage = (mins * VOD_USD_PER_MIN[0], mins * VOD_USD_PER_MIN[1],
                     f"{watched} at ${VOD_USD_PER_MIN[0]}-{VOD_USD_PER_MIN[1]} per minute delivered "
                     "(transcoding and delivery included)")
            src = "https://developers.cloudflare.com/stream/pricing/"
        else:
            # Building it from storage, a transcoder and a CDN: the bill is the CDN's data transfer plus transcoding.
            gb = mins * VIDEO_MB_PER_MIN / 1024
            up = mins * VIDEO_UPLOAD_SHARE
            lo = cdn_transfer_usd(gb) + up * TRANSCODE_USD_PER_MIN[0]
            hi = gb * CDN_USD_PER_GB_TIERS[0][1] + up * TRANSCODE_USD_PER_MIN[1]
            usage = (lo, hi, f"{watched}: ~{gb / 1e3:,.0f} TB of CDN data transfer ({VIDEO_MB_PER_MIN:g} MB per minute of "
                             f"adaptive HD) at CDN volume prices from ${CDN_USD_PER_GB_TIERS[0][1]}/GB down to "
                             f"${CDN_USD_PER_GB_TIERS[-1][1]}/GB (high end: no volume discount), plus transcoding ~"
                             f"{up / 1e6:,.2f}M uploaded minutes (1 per {1 / VIDEO_UPLOAD_SHARE:,.0f} watched) at "
                             f"${TRANSCODE_USD_PER_MIN[0]}-{TRANSCODE_USD_PER_MIN[1]} per minute for the bitrate ladder"
                             + ("; on your own servers the transfer is your bandwidth bill" if env["onprem"] else ""))
            src = "https://aws.amazon.com/cloudfront/pricing/"
        add("Video on demand", name, "Video must be transcoded into several bitrates and streamed (HLS/DASH) from a CDN; "
            "serving MP4 files from the app server breaks on slow connections and costs far more in egress.",
            src, usage=usage)
    if "live_video" in work:
        name = ("Self-hosted LiveKit or Jitsi (WebRTC SFU) on your servers, with a TURN relay" if env["onprem"] else
                "Video with a signed BAA: Amazon Chime SDK, Twilio Video or Daily (HIPAA plans)" if env["hipaa"] else
                "LiveKit (cloud in its India region, or self-hosted in your Indian region)" if env["india"] else
                "Managed WebRTC video: LiveKit Cloud, Daily or Twilio Video")
        mins = dau30 * VIDEO_MIN_PER_USER_DAY
        add("Live video", name, "Calls and live classes need a WebRTC selective forwarding unit (SFU) and TURN relays near "
            "users; a web server cannot relay media streams.", "https://docs.livekit.io/home/",
            usage=(mins * LIVE_USD_PER_MIN[0], mins * LIVE_USD_PER_MIN[1],
                   f"~{mins / 1e6:,.1f}M participant-minutes a month ({VIDEO_MIN_PER_USER_DAY} min per active user a day) "
                   f"at ${LIVE_USD_PER_MIN[0]}-{LIVE_USD_PER_MIN[1]} per participant-minute"))
    if "live_location" in work:
        loads = dau30 * MAP_LOADS_PER_USER_DAY
        name = ("Self-hosted OpenStreetMap tiles (OpenMapTiles) + location updates over your realtime channel" if env["onprem"] else
                "Google Maps Platform, Mapbox or Ola Maps + location updates over the realtime channel" if "india" in p["regions"] else
                "Google Maps Platform or Mapbox + location updates over the realtime channel")
        add("Maps & live location", name, "Send position updates every few seconds over WebSockets (not polling) and keep only "
            "the latest point per device in a fast store; map tiles and routing come from a maps provider.",
            "https://developers.google.com/maps/billing-and-pricing/pricing",
            usage=(loads * MAP_USD_PER_LOAD[0], loads * MAP_USD_PER_LOAD[1],
                   f"~{loads / 1e6:,.1f}M map loads a month ({MAP_LOADS_PER_USER_DAY} per active user a day) "
                   f"at ${MAP_USD_PER_LOAD[0]}-{MAP_USD_PER_LOAD[1]} each"))
    if "phone_otp" in work:
        india = "india" in p["regions"]
        price = OTP_USD["india" if india else "other"]
        sms = dau30 * OTP_PER_USER_DAY
        add("Phone login (SMS OTP)", "An SMS gateway inside your network (a GSM modem driven by Kannel or Gammu), or "
            "authenticator-app codes (TOTP) instead of SMS" if env["air_gapped"] else
            "MSG91 or Twilio Verify, with DLT-registered SMS templates" if india else
            # The cloud's own SMS service only on that cloud and when the team may use managed services there.
            SMS_BY_CLOUD.get("" if env["self_managed"] or env["hybrid"] else env["cloud"] or "", "Twilio Verify or Vonage Verify"),
            "One-time codes need an SMS gateway with rate limits against SMS-pumping fraud"
            + ("; Indian operators deliver only DLT-registered templates." if india else "."),
            "https://www.twilio.com/en-us/verify/pricing",
            usage=(sms * price[0], sms * price[1],
                   f"~{sms:,.0f} SMS a month (one login every ~20 days per active user) at ${price[0]}-{price[1]} each"))
    if "user_code" in work:
        add("Code sandbox", "Separate worker pool running submissions in gVisor or Firecracker sandboxes (or self-hosted Judge0)",
            "User code must never run in the web server's process or network: isolate it with CPU, memory, time and "
            "network limits on machines that hold no secrets.", "https://gvisor.dev/docs/", system="sandbox")


def _object_storage(env: dict, prov: str) -> str:
    if env["onprem"]:
        return "MinIO or Ceph (S3-compatible, self-hosted)"
    if env["hybrid"]:
        return "S3 API everywhere: the cloud's object storage in the cloud, MinIO on-premises (same client code)"
    if env["cloud"]:
        return {"aws": "Amazon S3 + CloudFront", "gcp": "Cloud Storage + Cloud CDN", "azure": "Blob Storage + Front Door"}[env["cloud"]]
    if env["india"]:
        return ("S3-compatible storage in an Indian region (DigitalOcean Spaces BLR1 or MinIO on your servers) + CDN"
                if env["no_hyperscaler"] else
                "S3-compatible storage in an Indian region (Amazon S3 Mumbai or Google Cloud Storage asia-south1) + CDN")
    if env["hipaa"]:
        return ("MinIO on your BAA-covered servers (no public CDN for PHI)" if env["no_hyperscaler"] else
                "Amazon S3 or Google Cloud Storage under a signed BAA (+ CDN for public, non-PHI files only)")
    if env["eu"]:
        return "S3-compatible storage in an EU jurisdiction (Cloudflare R2 EU or Backblaze B2 EU Central) + CDN"
    if prov == "cloudflare":
        return "Cloudflare R2 (+ Cloudflare CDN)"
    if prov == "digitalocean":
        return "DigitalOcean Spaces + built-in CDN"
    return "S3-compatible storage (Cloudflare R2 / Backblaze B2) + CDN"


def _auth(env: dict) -> str:
    if env["onprem"] or env["self_managed"]:
        return "Keycloak (self-hosted)"
    if env["hybrid"]:
        return "Keycloak (runs on-premises and in the cloud; OIDC for every app)"
    if env["hipaa"]:
        fallback = "Keycloak self-hosted in your Indian region (on BAA-covered servers)" if env["india"] else "Auth0 with a signed BAA"
        return {"aws": "Amazon Cognito (HIPAA-eligible)", "gcp": "Identity Platform (covered by Google Cloud BAA)",
                "azure": "Microsoft Entra External ID"}.get(env["cloud"] or "", fallback)
    if env["india"]:
        return ("Amazon Cognito in the Mumbai region" if env["cloud"] == "aws" else
                "Keycloak self-hosted in your Indian region, or framework built-in auth")
    if env["eu"]:
        return "Auth0 (EU tenant) / framework built-in auth"
    return "Clerk / Auth0 / framework built-in auth"


def _observability(env: dict) -> str:
    if env["onprem"] or env["hybrid"]:
        return "self-hosted Grafana + Prometheus + Loki + Tempo (the same stack on-premises and in the cloud)"
    if env["self_managed"]:
        return "self-hosted Grafana + Prometheus + Loki + Tempo on your own VMs"
    if env["cloud"]:
        return {"aws": "CloudWatch + X-Ray", "gcp": "Cloud Monitoring/Trace", "azure": "Azure Monitor / App Insights"}[env["cloud"]]
    if env["hipaa"]:
        return "Datadog or New Relic under a signed BAA, or self-hosted Grafana + Prometheus + Loki"
    if env["india"]:
        return ("the host's built-in metrics and logs, kept in your Indian region; self-hosted Grafana + Prometheus + "
                "Loki there once you outgrow them")
    return "Grafana Cloud / Sentry"


def apply_ops_budget(p: dict, services: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """Split services into kept and deferred. Must-haves (no trigger: auth, observability, payments,
    audit, realtime, compliance controls, and systems the scale already needs) are always kept.
    Deferrable ones are kept, cheapest-to-run first, only while the team's budget of extra systems
    lasts; the rest are listed with the trigger for adding them."""
    team = p["team_size"]
    cap = ops_budget(team)
    systems = {s["system"] for s in services if s.get("system") and not s.get("trigger")}
    priority = ["redis", "search", "ingestion"]
    deferrable = sorted((s for s in services if s.get("trigger")),
                        key=lambda s: priority.index(s["system"]) if s["system"] in priority else len(priority))
    allowed = set()
    for s in deferrable:
        if s["system"] in systems or cap is None or len(systems) < cap:
            systems.add(s["system"])
            allowed.add(id(s))
    kept = [s for s in services if not s.get("trigger") or id(s) in allowed]
    deferred = [s for s in services if s.get("trigger") and id(s) not in allowed]
    budget = {"team_size": team, "cap": cap, "extra_systems": sorted(systems),
              "note": ("Our estimate: a team of 1-2 people runs at most 1 extra system next to its app and database, "
                       "3-5 people 2, 6-12 people 4, 13 or more no cap. Compliance and security services are never deferred.")}
    return kept, deferred, budget


SERVER_RENDERED = ("nextjs", "nuxt", "sveltekit", "htmx")

# A browser app built to static files (an SPA) on a stack whose code runs on instances of a hyperscaler: the
# built files belong in that cloud's object storage behind its CDN, not in the API's containers (no instance
# time spent handing out files, cached at the edge, deployed apart from the API). Per cloud: (name, source,
# price per GB delivered, fixed monthly fee). AWS is priced from the knowledge base's S3 + CloudFront item.
# Each server framework's own WebSocket support, for realtime features that are a part of the product.
WEBSOCKET_LIBS = {
    "django": ("Django Channels", "https://channels.readthedocs.io/"),
    "fastapi": ("FastAPI WebSockets", "https://fastapi.tiangolo.com/advanced/websockets/"),
    "express": ("Socket.IO", "https://socket.io/docs/v4/"),
    "nestjs": ("NestJS WebSocket gateways", "https://docs.nestjs.com/websockets/gateways"),
    "spring_boot": ("Spring WebSocket with STOMP", "https://docs.spring.io/spring-framework/reference/web/websocket.html"),
    "dotnet": ("ASP.NET Core SignalR", "https://learn.microsoft.com/aspnet/core/signalr/introduction"),
    "rails": ("Action Cable", "https://guides.rubyonrails.org/action_cable_overview.html"),
    "laravel": ("Laravel Reverb", "https://laravel.com/docs/reverb"),
    "go": ("coder/websocket or gorilla/websocket", "https://pkg.go.dev/github.com/coder/websocket"),
    "phoenix": ("Phoenix Channels", "https://hexdocs.pm/phoenix/channels.html"),
}
SPA_STATIC_HOME = {
    "aws": ("Amazon S3 + CloudFront", "https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html",
            None, None),
    "gcp": ("Cloud Storage bucket + Cloud CDN", "https://cloud.google.com/cdn/docs/setting-up-cdn-with-bucket",
            0.08, 0.0),   # cache egress to North America/Europe, first 10 TiB (https://cloud.google.com/cdn/pricing)
    "azure": ("Azure Blob Storage static website + Azure Front Door Standard",
              "https://learn.microsoft.com/azure/storage/blobs/storage-blob-static-website",
              0.083, 35.0),  # Standard base fee + first 10 TB out (https://azure.microsoft.com/pricing/details/frontdoor/)
}
SPA_STATIC_PRICE_SOURCES = {"gcp": "https://cloud.google.com/cdn/pricing",
                            "azure": "https://azure.microsoft.com/en-us/pricing/details/frontdoor/"}
# Planning figure: the SPA's JavaScript, CSS and images delivered per active user a day (bundles of 0.5-2 MB,
# mostly cached by the browser between visits).
SPA_MB_PER_USER_DAY = 1.0
SPA_INSTANCE_HOSTS = ("containers", "kubernetes", "paas", "vps")


def spa_static_home(stack: dict) -> tuple | None:
    """(name, source, price per GB, monthly fee) of the object storage + CDN that serves a static browser app's
    built files, when the frontend is built to static files and the host runs instances on a hyperscaler."""
    fe, host = stack["frontend"], stack.get("api_host") or stack["hosting"]
    if fe.get("kind") != "web" or fe["id"] in SERVER_RENDERED or stack["backend"].get("kind") not in ("server", "faas"):
        return None
    if stack["hosting"].get("kind") not in SPA_INSTANCE_HOSTS:
        return None
    return SPA_STATIC_HOME.get(host.get("provider"))


def short_name(item: dict) -> str:
    """Name of a technology without its parenthesised note, e.g. 'Next.js' for 'Next.js (React)'."""
    return item["name"].split(" (")[0]


def baas_hosts_everything(d: dict, stack: dict) -> bool:
    """Mobile-only app on a BaaS: the app ships through the stores and the BaaS runs the backend,
    so no host of your own is needed (a landing page is optional)."""
    return d["mobile"] and not d["web"] and stack["backend"].get("kind") == "baas" and not d.get("workers")


# Split hosting. A frontend platform runs a server framework only as short-lived functions. From
# this scale tier up, or when realtime is core, the API gets its own long-running host and the
# frontend platform keeps the pages: always-on instances hold pooled database connections,
# background work and WebSockets, and at steady high traffic cost less than per-request functions.
API_HOST_MIN_TIER = STEADY_TRAFFIC_TIER  # Large (100k-1M DAU) and up
API_HOST_KINDS = ("containers", "kubernetes", "paas", "vps")
SPLIT_RULES = ("light_server_on_frontend_paas", "heavy_server_on_frontend_paas", "frontend_paas_rdbms_pooling")


def api_host_reasons(p: dict, d: dict, stack: dict) -> list[str]:
    """Why the API needs a long-running host of its own; empty when it does not."""
    if stack["hosting"].get("kind") != "frontend_paas" or stack["backend"].get("kind") != "server":
        return []
    out = []
    if d["compute_tier"] >= API_HOST_MIN_TIER:
        out.append(f"at {d['tier_label']} scale (~{d['peak_rps'] or 0:,.0f} peak req/s) traffic is steady, so always-on "
                   "instances with pooled database connections cost less than per-request functions")
    if p["realtime"] == "core":
        out.append("realtime is core, and WebSocket connections need a process that stays up")
    return out


def pick_api_host(stack: dict, hosting_scored: list[dict], rules: list[dict], match) -> dict | None:
    """Best long-running host for the API: hosting layer score plus the compatibility rules that do
    not involve the frontend (the frontend stays on the frontend platform). `hosting_scored` holds
    only hosts that passed the hard constraints; `match(items, rules)` returns the rules that apply."""
    rules = [r for r in rules if "frontend" not in {**r.get("when", {}), **(r.get("not") or {})}]
    best = None
    for c in hosting_scored:
        if c["item"].get("kind") not in API_HOST_KINDS:
            continue
        hits = match(dict(stack, hosting=c["item"]), rules)
        sc = c["score"] + sum(r["delta"] for r in hits)
        if best is None or sc > best[0] + 1e-9:
            best = (sc, c, hits)
    if not best:
        return None
    sc, c, hits = best
    return {"id": c["id"], "name": c["name"], "score": round(c["score"], 1), "item": c["item"],
            "rules": [{"id": r["id"], "delta": r["delta"], "note": r["note"]} for r in hits]}


def split_note(stack: dict, api: dict, rule_id: str) -> str:
    """Text for a frontend-platform caveat once the API has its own host."""
    if rule_id == "frontend_paas_rdbms_pooling":
        return (f"Only the API on {api['name']} should open database connections, through a pool. Server code left "
                f"on {stack['hosting']['name']} that queries the database directly needs a pooled/HTTP driver (Neon "
                "serverless driver, Supabase pooler, PlanetScale) to avoid connection exhaustion.")
    return (f"Split hosting: {short_name(stack['frontend'])} stays on {stack['hosting']['name']}, and the "
            f"{short_name(stack['backend'])} API runs on {api['name']} as a long-running service. That is two "
            "platforms to deploy, monitor and pay for, and the frontend calls the API across origins (set up CORS "
            "or a rewrite on the frontend platform).")


def runs_here(d: dict, stack: dict, api_host: dict | None = None) -> str:
    """What actually runs on the hosting pick, and what runs elsewhere."""
    fe, be, host = stack["frontend"], stack["backend"], stack["hosting"]
    if api_host:
        text = (f"Runs here: {short_name(fe)} ({'server rendering + static files' if fe['id'] in SERVER_RENDERED else 'static files'}). "
                f"The {short_name(be)} API runs on {api_host['name']} as long-running processes (split hosting).")
        return text + _database_where(stack, f"{api_host['name']}'s")
    if baas_hosts_everything(d, stack):
        optional = "Firebase Hosting (free tier)" if be["id"] == "firebase" else host["name"]
        return (f"Nothing of yours needs hosting: the app ships through the App Store and Google Play, and "
                f"{short_name(be)} runs the API, auth, database and file storage. {optional} is optional, "
                "for a landing page or web admin.")
    if be.get("kind") == "none":
        return (f"Runs here: {short_name(fe)} as pre-built static pages. No server code and no database: "
                "content files are built into pages at deploy time, and the free static plan covers the traffic.")
    parts = []
    if d["web"] and fe.get("kind") == "mobile":
        parts.append("the web app's pages (the mobile app ships through the app stores)")
    elif d["web"] and spa_static_home(stack):
        pass  # the built files are served from the cloud's object storage + CDN, said below
    elif d["web"]:
        parts.append(f"{short_name(fe)} ({'server rendering + static files' if fe['id'] in SERVER_RENDERED else 'static files'})")
    request_scoped = host.get("kind") in ("frontend_paas", "faas")
    if be.get("kind") == "server":
        parts.append(f"the {short_name(be)} API" + (" as serverless functions" if request_scoped else " as long-running processes"))
    elif be.get("kind") == "faas":
        parts.append("the serverless functions")
    text = "Runs here: " + (", ".join(parts) if parts else "nothing but optional static pages") + "."
    home = spa_static_home(stack) if d["web"] else None
    if home:
        text += (f" {short_name(fe)} is built to static files that are served from {home[0]}, not from these "
                 "instances (see Supporting services).")
    if be.get("kind") == "baas":
        text += f" {short_name(be)} runs the API, auth and database as its own managed service."
    else:
        text += _database_where(stack, "this host's")
    return text


def _database_where(stack: dict, disk: str) -> str:
    """Where the database runs, for runs_here(). An embedded single-file database (SQLite) is not a
    service at all: the API process opens the file on its own disk. `disk` names whose disk that is."""
    db, host = stack["database"], stack["hosting"]
    if db.get("static_only"):
        return " There is no database: content files in the repository are built into the pages at deploy time."
    if db.get("single_node"):
        return (f" The database is {short_name(db)}, an embedded single-file database: one file on {disk} disk that the "
                f"{short_name(stack['backend'])} process opens directly, with no separate database server (copy the file "
                "to object storage for backups).")
    if host.get("kind") in ("onprem", "vps"):
        return ""
    return " The database runs as a separate managed service (see Database)."


# Availability multiplier for capacity you run yourself (instances, nodes, database replicas):
# 99.9% needs a second instance or a standby, 99.95% spreads over zones, 99.99% adds a second region.
# Platforms that bill per request or per plan (frontend PaaS, functions, a BaaS, serverless
# databases) include their redundancy in the price.
AVAILABILITY_MULT = {99.0: 1.0, 99.9: 1.5, 99.95: 2.0, 99.99: 3.0}
INSTANCE_HOSTS = ("containers", "kubernetes", "paas", "vps", "onprem")
REQUEST_BILLED = ("gcp_cloud_run",)  # scales per request across zones by default
# Model serving: about one model call per active user a day of ~1,500 tokens, priced from a small
# hosted model to a mid-size one (published per-million-token prices, mid 2026).
MODEL_CALLS_PER_USER_DAY = 1
MODEL_TOKENS_PER_CALL = 1500
MODEL_USD_PER_M_TOKENS = (0.15, 2.5)
# A small scoring model (credit score, fraud score) on one or two always-on CPU instances, SageMaker list prices:
# one ml.c5.large ($0.102 an hour) to two ml.m5.large ($0.121 an hour in Mumbai), about 730 hours a month.
SCORING_ENDPOINT_USD = (75.0, 180.0)
# Project types whose model is usually a trained classifier or regressor of their own (credit, fraud, risk, demand,
# anomaly scores); for other types an inference API is a hosted model, priced per call.
SCORING_APP_TYPES = ("fintech", "ecommerce", "healthcare", "iot_telemetry", "analytics_dashboard")
SCORING_SERVING = {
    "aws": ("Amazon SageMaker real-time endpoint for your own model (Amazon Bedrock for a hosted one)",
            "https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html"),
    "gcp": ("Vertex AI online prediction endpoint for your own model (Gemini on Vertex AI for a hosted one)",
            "https://cloud.google.com/vertex-ai/docs/predictions/overview"),
    "azure": ("Azure Machine Learning managed online endpoint for your own model (Azure OpenAI for a hosted one)",
              "https://learn.microsoft.com/azure/machine-learning/concept-endpoints-online"),
    "self": ("Your own model in a CPU container beside the API (BentoML, or ONNX Runtime behind a small HTTP service)",
             "https://docs.bentoml.com/"),
    "functions": ("Your model exported to ONNX and run inside the API's functions (ONNX Runtime), with no server of its own",
                  "https://onnxruntime.ai/docs/get-started/with-javascript/node.html"),
}


def scoring_model(p: dict) -> bool:
    """An inference API that serves the project's own small scoring model on CPU, not a hosted model."""
    return p.get("ml_features") == "inference_api" and p["app_type"] in SCORING_APP_TYPES


# Storage floor of a database bill: managed SSD storage per GB-month at list price (Amazon RDS gp3, the common
# block-storage price for managed databases; Atlas and Cloud SQL charge in the same range or more), and the
# copies at the high end (replica set or standby, plus backups). Columnar warehouses store compressed data at
# their own price; ClickHouse's band covers its compressed storage.
STORAGE_USD_PER_GB = {"default": 0.115, "bigquery": 0.02, "clickhouse": 0.0}
STORAGE_COPIES_HIGH = 3
STORAGE_PRICE_SOURCE = {"default": "https://aws.amazon.com/rds/postgresql/pricing/",
                        "bigquery": "https://cloud.google.com/bigquery/pricing"}


# A database that is one local file (SQLite) pins the app to one instance: a second instance would
# need its own copy of the file. Such a stack is priced as one instance and does not claim the
# redundancy a 99.9%+ target needs (architecture() says so, and the database's score carries the miss).
SINGLE_INSTANCE_BASIS = "one instance: the local database file cannot be shared, so no redundancy is priced"


def single_instance(stack: dict) -> bool:
    """True when the database runs on one node that is not bundled inside the backend."""
    db = stack["database"]
    return bool(db.get("single_node")) and stack["backend"].get("bundled_database") != db["id"]


def _avail(d: dict) -> float:
    """Redundancy multiplier for capacity you run yourself. Only a stated target is priced: the 99.9% default is a
    planning goal, and an unanswered question should not put a small project over its budget."""
    if "availability" in d.get("defaulted", ()):
        return 1.0
    return AVAILABILITY_MULT.get(d["availability"], 1.0)


# Basis note where a stated target would add redundancy: what the default leaves out.
UNSTATED_AVAILABILITY = ("no redundancy priced: no availability target was given (the {a:g}% default is a goal; "
                         "stating it adds x{m:g} for redundant capacity)")


def estimate_cost(p: dict, d: dict, stack: dict, services: list[dict], usage: bool = True) -> dict:
    """Monthly cost lines. usage=False leaves out the usage terms that follow the exact user count
    (per-operation pricing, media and inference volumes), keeping the price bands of the scale tier and
    the plan size and disk set by stored data, so the result is the same at every user count of a tier."""
    kb = load_kb()
    cost_of = usage_cost if usage else (lambda item, t, p_, d_: usage_cost(item, t, p_, d_, per_op=False))
    tier, dbt = d["compute_tier"], d["db_tier"]
    lines = []
    mult = _avail(d)
    unstated = AVAILABILITY_MULT.get(d["availability"], 1.0) if mult == 1.0 else 1.0

    def line(component, lo, hi, basis):
        lines.append({"component": component, "low": float(round(lo)), "high": float(round(hi)), "basis": basis})

    host = stack["hosting"]
    one = single_instance(stack)
    if not baas_hosts_everything(d, stack):  # otherwise the optional landing page fits a free tier
        lo, hi = tier_cost(host, tier, p)
        basis = [f"free static plan: pre-built files only" if host.get("static_cost_usd") and static_site(p)
                 else f"{d['tier_label']} price band"]
        seats = seat_cost(host, lo, p)
        if seats:
            lo, hi = lo + seats, hi + seats
            basis.append(f"includes {p['team_size']} deploying seats at ${host['seat_usd']}/month each")
        disk = host.get("local_file_disk_min_usd")
        if one and disk and lo < disk:
            # The database file must outlive restarts and deploys: on a host whose free tier has no
            # persistent disk, the cheapest durable home for the file is the paid plan that has one.
            lo, hi = float(disk), max(hi, float(disk))
            basis.append(f"persistent disk for the database file: {host['local_file_disk_note']}")
        if host.get("kind") in INSTANCE_HOSTS and host["id"] not in REQUEST_BILLED and mult > 1:
            if one:
                basis.append(SINGLE_INSTANCE_BASIS)
            else:
                lo, hi = lo * mult, hi * mult
                basis.append(f"x{mult:g} for {d['availability']:g}% availability (redundant instances)")
        elif (
            host.get("kind") in INSTANCE_HOSTS
            and host["id"] not in REQUEST_BILLED
            and unstated > 1
            and not one
            and not stack.get("api_host")
            and lo > 0
        ):
            basis.append(UNSTATED_AVAILABILITY.format(a=d["availability"], m=unstated))
        api = stack.get("api_host")
        if api:
            basis.append("pages and server rendering only; the API is priced on its own line")
        line(f"Hosting: {host['name']}", lo, hi, "; ".join(basis))
        if api:
            lo, hi = tier_cost(api, tier, p)
            basis = [f"{d['tier_label']} price band"]
            if api["id"] not in REQUEST_BILLED and mult > 1:
                if one:
                    basis.append(SINGLE_INSTANCE_BASIS)
                else:
                    lo, hi = lo * mult, hi * mult
                    basis.append(f"x{mult:g} for {d['availability']:g}% availability (redundant instances)")
            line(f"API host: {api['name']}", lo, hi, "; ".join(basis))
    be = stack["backend"]
    if be.get("kind") == "baas":
        lo, hi = cost_of(be, tier, p, d)
        what = "self-hosted on your servers, no subscription" if self_hosted_baas(be, p) else "includes its database"
        basis = ("runs on your servers; priced under hosting" if self_hosted_baas(be, p) else
                 f"plan sized for the larger of traffic ({d['tier_label']}) and ~{d['data_12mo_gb']:,.0f} GB of data in 12 months"
                 + ("; per-read/write pricing at your request volume" if be.get("usage", {}).get("doc_write_usd_per_100k") else "")
                 + ("; disk beyond the plan's allowance billed per GB" if be.get("usage", {}).get("storage_usd_per_gb") else ""))
        line(f"Backend: {be['name']} ({what})", lo, hi, basis)
    db = stack["database"]
    if be.get("bundled_database") != db["id"] and not db.get("static_only"):
        dbhost = stack.get("api_host") or host  # the database sits next to the API
        offer = database_offering(db, dbhost, p)
        dbx = with_usable_plans(db, offer, p)
        lo, hi = cost_of(dbx, dbt, p, d)
        basis = [f"{d['db_tier_label']} database tier (~{d['data_12mo_gb']:,.0f} GB in 12 months)"]
        ep = entry_plan(dbx, dbt, d)
        band_lo = db.get("cost_usd", [[0, 0]] * 6)[dbt][0]
        plans = db.get("entry_plans", []) + db.get("host_plans", [])
        if ep and (band_lo == 0 or plan_price(ep, d) <= band_lo):
            basis.append(f"from ${plan_price(ep, d):g} on {ep['name']}: {ep['limits']}")
        elif ep:
            pass  # a small managed instance at the band's floor costs less than the vendors' entry plans
        elif dbx.get("entry_plans") and dbt <= max(x["max_tier"] for x in dbx["entry_plans"]):
            basis.append(f"too much data or traffic for the free and entry plans of {offer} "
                         f"(the largest holds {max(x['max_data_gb'] for x in dbx['entry_plans']):g} GB)")
        if not ep and not db.get("usage") and d["data_tier"] < dbt:
            # Traffic set the tier, not the data: the band's top is priced for the tier's largest data, so with a
            # small dataset the top is the instance the traffic needs (up to twice the floor) plus that data's band.
            bands = db.get("cost_usd", [[0, 0]] * 6)
            top = max(lo, min(hi, max(2 * lo, lo + bands[d["data_tier"]][1])))
            if top < hi:
                hi = top
                basis.append(f"upper end for ~{d['data_12mo_gb']:,.0f} GB of data: the band's top is priced for the "
                             "largest data of the tier")
        if not ep and plans and dbt <= max(x["max_tier"] for x in plans) and not (
                dbx.get("entry_plans") and dbt <= max(x["max_tier"] for x in dbx["entry_plans"])):
            # Entry plans exist, but none is the offering on this host (or none signs a BAA): price the
            # host's own managed service from the band instead of quoting another vendor's plan.
            basis.append(f"priced as {offer}" + (": HIPAA needs a plan whose vendor signs a BAA, which no free or entry "
                                                 "plan of this database does" if "hipaa" in p["compliance"] else ""))
        if mult > 1 and not db.get("managed_only") and not db.get("single_node") and not db.get("usage"):
            lo, hi = lo * mult, hi * mult
            basis.append(f"x{mult:g} for {d['availability']:g}% availability (standby/replicas)")
        per_gb = STORAGE_USD_PER_GB.get(db["id"], STORAGE_USD_PER_GB["default"])
        if per_gb and not db.get("usage") and not db.get("single_node"):
            # However the band was set, the bill is at least the disk the data needs: one copy at the low end,
            # three (replicas or standby, plus backups) at the high end.
            slo, shi = d["data_12mo_gb"] * per_gb, d["data_12mo_gb"] * per_gb * STORAGE_COPIES_HIGH
            if slo > lo or shi > hi:
                lo, hi = max(lo, slo), max(hi, shi)
                basis.append(f"at least the storage: ~{d['data_12mo_gb']:,.0f} GB at ${per_gb:g}/GB-month, one copy to "
                             f"{STORAGE_COPIES_HIGH} copies ({STORAGE_PRICE_SOURCE.get(db['id'], STORAGE_PRICE_SOURCE['default'])})")
        if dbhost.get("provider") in (db.get("self_managed_on") or {}):
            lo, hi = lo * SELF_MANAGED_COST_FACTOR, hi * SELF_MANAGED_COST_FACTOR
            basis.append(f"x{SELF_MANAGED_COST_FACTOR:g} planning allowance: no managed {db['name']} on {CLOUD_NAMES.get(dbhost['provider'], dbhost['provider'])}, "
                         "so backup storage, monitoring and a tested failover are yours to build")
        lic = db.get("self_managed_licence") if _env(p, host)["onprem"] else None
        # Run on your own servers, a commercial database needs a licence the managed services include in their
        # price. The free edition fits only a small database with no failover (a 99.9%+ target, the default
        # included, needs a standby).
        free = lic and d["data_12mo_gb"] <= lic["free_max_gb"] and d["availability"] < 99.9
        if free:
            basis.append(f"{lic['free_edition']} edition licence: free ({lic['free_note']}; {lic['free_source']})")
        line(f"Database: {db['name']}", lo, hi, "; ".join(basis))
        if lic and not free:
            line(f"Licence: {db['name'].split(' / ')[0]} {lic['edition']}", lic["min_cores"] * lic["usd_per_core_month"],
                 lic["high_cores"] * lic["usd_per_core_month"],
                 f"{lic['min_cores']}-{lic['high_cores']} cores: {lic['note']} ({lic['source']}). {lic['free_note']} "
                 f"({lic['free_source']}).")
    seen = set()
    for s in services:
        if s.get("cost_id") and s["cost_id"] not in seen:
            seen.add(s["cost_id"])
            item = kb["index"][s["cost_id"]]
            if item.get("entry_plans") or item.get("host_plans"):
                # A store's plans, like the primary's, only where they are the offering on the API's host.
                item = with_usable_plans(item, database_offering(item, stack.get("api_host") or host, p), p)
            lo, hi = tier_cost(item, s["cost_tier"], p, d)
            basis = (f"{d['tier_label'] if s['cost_tier'] == tier else d['db_tier_label'] if s['cost_tier'] == dbt else TIER_LABELS[s['cost_tier']]}"
                     " price band (the app's scale)")
            if s["role"] == "Analytics":
                # The warehouse is fed by change-data-capture from the primary database, which keeps the rows too.
                basis += (f"; a copy of data that {db['name']} also stores (fed by a continuous copy of changes), "
                          "so that data is paid for in both stores")
            line(f"{s['role']}: {kb['index'][s['cost_id']]['name']}", lo, hi, basis)
        if s.get("usage") and usage:
            line(s["role"], *s["usage"])
        elif s.get("tier_usage") and not usage:
            line(s["role"], *s["tier_usage"])
        if s["role"] == "Model serving" and scoring_model(p) and s["name"] != SCORING_SERVING["functions"][0]:
            line("Model serving: CPU endpoint", *SCORING_ENDPOINT_USD,
                 "one or two always-on CPU instances behind a real-time endpoint: one ml.c5.large at $0.102 an hour to "
                 "two ml.m5.large at $0.115-0.121 (US East, Mumbai), https://aws.amazon.com/sagemaker/pricing/")
        elif s["role"] == "Model serving" and scoring_model(p):
            pass  # the model runs inside the API's functions, already priced with them
        elif s["role"] == "Model serving" and usage and not _env(p, host)["onprem"]:
            tokens = p["dau"] * 30 * MODEL_CALLS_PER_USER_DAY * MODEL_TOKENS_PER_CALL
            line("Model serving: inference", tokens / 1e6 * MODEL_USD_PER_M_TOKENS[0], tokens / 1e6 * MODEL_USD_PER_M_TOKENS[1],
                 f"~{MODEL_CALLS_PER_USER_DAY} call/user/day x {MODEL_TOKENS_PER_CALL:,} tokens = ~{tokens / 1e6:,.0f}M tokens/month "
                 f"at ${MODEL_USD_PER_M_TOKENS[0]}-{MODEL_USD_PER_M_TOKENS[1]} per million")
    total_lo = sum(x["low"] for x in lines)
    total_hi = sum(x["high"] for x in lines)
    budget = d["budget_usd"]
    if total_lo > budget:
        status = "over"
    elif total_hi > budget:
        status = "stretch"
    else:
        status = "within"
    inr = 1 / USD_PER_INR
    return {
        "currency": "USD", "lines": lines, "total_low": total_lo, "total_high": total_hi,
        "total_low_inr": round(total_lo * inr), "total_high_inr": round(total_hi * inr),
        "budget_usd": budget, "status": status, "tier": d["tier_label"],
        "note": "Planning estimate from published price bands at your scale tier, with the usage terms listed per line; "
                "excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.",
    }


def min_feasible_cost(p: dict, d: dict, hosting_feasible: list[dict], db_feasible: list[dict]) -> float:
    """Cheapest monthly hosting plus database cost among the technologies that pass the hard constraints."""
    if not hosting_feasible or not db_feasible:
        return 0.0
    h = min(tier_cost(x["item"], d["compute_tier"], p)[0] for x in hosting_feasible)
    dbc = min(tier_cost(x["item"], d["db_tier"], p, d)[0] for x in db_feasible)
    return h + dbc


# How a release changes the stored data, by kind of database. SQL engines have a fixed schema that versioned
# migrations change; the others keep no table schema, so a release changes the data's shape in other ways.
SCHEMALESS_CHANGE = {
    "mongodb": "MongoDB keeps no fixed schema: new code reads both the old and the new document shape during a "
               "rollout, and backfills that rewrite old documents run as versioned scripts (indexes and validation "
               "rules ship the same way).",
    "firestore": "Firestore keeps no schema: new code reads both the old and the new document shape during a rollout, "
                 "backfills run as versioned scripts, and security rules and indexes deploy with the Firebase CLI.",
    "dynamodb": "DynamoDB keeps no schema beyond its keys: new code reads both the old and the new item shape during a "
                "rollout, and tables and indexes change through infrastructure as code.",
    "cassandra": "Cassandra/ScyllaDB tables change through versioned CQL scripts that only add columns or tables, since "
                 "queries are designed around each table's key.",
    "redis": "Redis keeps no schema: a change in the stored format gets a new key prefix (or version field), so old and "
             "new code run side by side until the old keys expire.",
    "opensearch": "Index mapping changes go into a new index that is filled by a reindex, then an alias switches "
                  "searches to it.",
    "neo4j": "Neo4j keeps no fixed schema: constraints, indexes and data refactors run as versioned migration scripts "
             "(e.g. Neo4j-Migrations) before the new code serves traffic.",
}


def schema_change_text(db: dict) -> str:
    """What happens to stored data when a release ships, for the Deploy step of how_parts_fit()."""
    return SCHEMALESS_CHANGE.get(db["id"], "Database schema changes run as versioned migrations before the new code "
                                          "serves traffic.")


def how_parts_fit(p: dict, d: dict, stack: dict, services: list[dict], api_host: dict | None = None) -> list[dict]:
    """Four steps that show how the picks work together: the request path, sign-in, where the data
    (and any regulated data) lives, and how a change is deployed."""
    from .export import _num
    fe, be, db, host = stack["frontend"], stack["backend"], stack["database"], stack["hosting"]
    svc = {s["role"]: s["name"] for s in services}
    kind, hkind = be.get("kind"), host.get("kind")
    bname, hname, dname = short_name(be), host["name"], db["name"]
    peak = _num(d["peak_rps"]) if d["peak_rps"] else "<0.1"
    mobile_only = d["mobile"] and not d["web"]
    api_on = api_host["name"] if api_host else hname
    if mobile_only:
        lead, then = "The iOS/Android app, installed from the app stores,", " "
    elif fe.get("kind") == "mobile":
        lead, then = "The iOS/Android app, installed from the app stores (and the web app, served from " + hname + "),", " "
    elif fe["id"] == "htmx" and kind == "server":
        views = f" with {be['view_layer']['name']}" if be.get("view_layer") else ""
        lead, then = (f"The browser requests pages that the {bname} service renders{views} on {api_on} "
                      "(HTMX swaps in HTML fragments)"), "; "
    elif spa_static_home(stack) and not mobile_only:
        lead, then = f"The browser loads {fe['name']}'s built files from {spa_static_home(stack)[0]}", "; it "
    else:
        lead, then = f"The browser loads {fe['name']} from {hname}", "; it "
    if kind == "none":
        req = (f"{lead}'s CDN as pre-built pages; there is no API call on the request path, so ~{peak} requests/s "
               "at peak are plain file reads.")
    elif kind == "baas":
        req = (f"{lead}{then}calls {bname}'s API directly through the client SDK (~{peak} requests/s at peak), and "
               f"{bname}'s access rules decide what each user may read or write.")
    elif kind == "faas":
        req = f"{lead}{then}sends API calls to functions on {api_on}, one invocation per request (~{peak} requests/s at peak)."
    elif fe["id"] == "htmx" and kind == "server" and not mobile_only:
        req = f"{lead}; ~{peak} requests/s at peak, each answered from {dname}."
    else:
        req = f"{lead}{then}sends API calls to the {bname} service on {api_on} (~{peak} requests/s at peak), which queries {dname}."
    if kind == "none" or not ({"sign_in", "post", "pay"} & set(d["user_actions"])):
        login = "No sign-in: everything is public and read-only."
    elif kind == "baas":
        login = f"{bname} Auth signs users in and issues tokens; its access rules check the token on every read and write."
    else:
        auth = svc.get("Authentication") or svc.get("Phone login (SMS OTP)") or "the framework's built-in auth"
        checker = "each function checks the token" if kind == "faas" else f"the {bname} API checks the session or token"
        login = f"Sign-in uses {auth}; {checker} on every request."
    data = (f"Content lives as files in the git repository (about {_num(d['data_12mo_gb'])} GB); there is no database"
            if db.get("static_only") else f"{dname} is the system of record (about {_num(d['data_12mo_gb'])} GB within 12 months)")
    if kind == "baas" and be.get("bundled_database") == db["id"]:
        data += f", run by {bname}"
    if "Object storage" in svc:
        data += f"; uploaded files go to {svc['Object storage']}"
    data += "."
    if "hipaa" in p["compliance"]:
        data += (" PHI (protected health information) stays in the database and object storage, encrypted at rest, on "
                 "services covered by a signed BAA; keep it out of logs, analytics and push notification text.")
    if "pci_dss" in p["compliance"] or "Payments" in svc:
        data += (" Card and bank details never reach your servers: the payment provider's hosted checkout or SDK "
                 "collects them, and you store only its tokens.")
    if {"data_residency_india", "data_residency_eu"} & set(p["compliance"]):
        data += " Every store above is placed in the region your residency rule requires."
    if kind == "none" and hkind == "static_cdn":
        deploy = (f"CI rebuilds the pages on each push, uploads them to the bucket and invalidates the cache, so "
                  f"{hname} serves the new version.")
    elif kind == "none":
        deploy = f"A git push rebuilds the pages and {hname} publishes them to its CDN."
    elif mobile_only and (kind == "baas" or hkind == "frontend_paas"):
        deploy = "App releases go through App Store and Google Play review."
    elif host["id"] == "onprem_docker":
        deploy = "CI builds container images; Docker Compose pulls them and restarts the services on your servers."
    elif hkind == "frontend_paas" and not api_host:
        deploy = f"A git push builds the app; {hname} deploys it with a preview URL per pull request."
    elif hkind in ("kubernetes", "onprem") or (api_host or {}).get("item", {}).get("kind") == "kubernetes":
        deploy = f"CI builds container images and rolls them out on {api_on} (manifests or Helm), one service at a time."
    elif hkind == "faas":
        deploy = f"CI packages the functions and deploys them with infrastructure as code to {hname}."
    else:
        deploy = f"CI builds a container image and rolls it out on {api_on} with health checks and zero-downtime restarts."
    if spa_static_home(stack) and not mobile_only and fe.get("kind") == "web":
        deploy += f" The frontend's built files are uploaded to {spa_static_home(stack)[0].split(' + ')[0]} and the CDN cache is invalidated."
    if mobile_only and not deploy.startswith("App releases"):
        deploy += " App releases go through App Store and Google Play review."
    if fe["id"] == "react_native":
        deploy += " JavaScript-only fixes can ship as over-the-air updates (Expo EAS Update)."
    if api_host and hkind == "frontend_paas":
        deploy += f" The frontend deploys separately on {hname}."
    if kind == "baas" and db["id"] in SCHEMALESS_CHANGE:
        deploy += (f" Access rules and indexes ship with the {bname} CLI from the same repository; {db['name']} keeps no "
                   "schema, so new code reads both the old and the new document shape during a rollout.")
    elif kind == "baas":
        deploy += f" Schema changes and access rules ship with the {bname} CLI from the same repository."
    elif kind != "none":
        deploy += " " + schema_change_text(db)
    return [{"step": "Request path", "text": req}, {"step": "Sign-in", "text": login},
            {"step": "Data", "text": data}, {"step": "Deploy", "text": deploy}]
