# StackSense recommendation: DocMind (RAG search)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For an 'ML / AI product' project at Medium (10k-100k daily users) scale (~69 peak req/s) built by 4 engineer(s) in 12 weeks, StackSense recommends Next.js (React) + Python + FastAPI + PostgreSQL + Google Cloud Run (architecture: Modular monolith). Estimated infrastructure cost: $367-$4,939/month (stretch budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Next.js (React)** | 87.8 | 3.0, solid (1.5-4 points) | Nuxt (Vue) (-3.0) |
| Backend | **Python + FastAPI** | 90.0 | 0.7, close call (under 1.5) | Python + Django (-0.7, tie) |
| Database | **PostgreSQL** | 87.0 | 1.6, solid (1.5-4 points) | Microsoft SQL Server (-1.6) |
| Hosting | **Google Cloud Run** | 99.8 | 2.8, solid (1.5-4 points) | DigitalOcean (App Platform + Managed DBs) (-2.8) |

Stack score: **94.1** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Modular monolith**: With 4 engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later. Sized for ~69 requests/s at peak, about 560 GB of data within 12 months and a 99.9% availability target.

Availability approach: The platform runs the functions across zones, with no instances for you to run; managed DB with automated failover

### How the parts fit

1. **Request path**: The browser loads Next.js (React) from Google Cloud Run; it sends API calls to the Python + FastAPI service on Google Cloud Run (~69 requests/s at peak), which queries PostgreSQL.
2. **Sign-in**: Sign-in uses FastAPI's OAuth2 password flow with hashed passwords in your API, with the users in your database: Clerk would cost about $2,025 a month at ~150,000 monthly users; the Python + FastAPI API checks the session or token on every request.
3. **Data**: PostgreSQL is the system of record (about 560 GB within 12 months); uploaded files go to Cloud Storage + Cloud CDN.
4. **Deploy**: CI builds a container image and rolls it out on Google Cloud Run with health checks and zero-downtime restarts. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Medium (10k-100k daily users) (peak ~69 req/s, derived); database tier: Medium (100 GB-1 TB of data) (~560 GB in 12 months)
- Budget: ~$1,500/month
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Warnings and how they were resolved

- **[WARNING] Budget below the top of the estimate**: $367-$4,939/month against $1,500/month: the top (~3x today's load) and the middle are over, most of the rise in inference and PostgreSQL. *Resolution:* Raise the budget before the load grows.

## Per-layer reasoning

### Frontend: Next.js (React) (87.8)

React meta-framework with server rendering, static generation, React Server Components and file-based routing.

Next.js (React) is the frontend for an ML / AI product project with about 30,000 daily users (~69 requests/s at peak), built by a team of 4 in 12 weeks. Search visibility is marked important (landing/product pages), and it serves full HTML from the server or the build (SEO 5.0/5), so crawlers read the content without running JavaScript. It leads the runner-up, Nuxt (Vue), by 3.0 points (out of 100 on the whole-stack score, the average of the four layer scores).

**Why**
- Development speed: 5.0/5 vs 4.0 average for this layer - weighted up because: 12-week MVP; Fast iteration on models.
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer - weighted up because: Regulated workload.
- Rich client interactivity: 5.0/5 vs 4.1 average for this layer - weighted up because: Interactive AI UX (streaming, chat).
- Team skill match (4.5/5, direct): your team lists React, a direct match for Next.js (React).
- SSR/SSG/ISR give crawlers full HTML (strong SEO, fast LCP)
- Largest React ecosystem and hiring pool
- Same codebase can host API routes / server actions for small apps

**Trade-offs**
- App Router + Server Components add conceptual load
- Some features (ISR, image optimisation, middleware) are smoothest on Vercel

**Versus runner-up:** Next.js (React) beats Nuxt (Vue) by 3.0 points (out of 100 on the whole-stack score, the average of the four layer scores), mainly on general quality (baseline weights) (+1.1), team skills (+0.9), time to mvp (+0.6).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +33.0
- Team skills: +13.3
- SEO need: +12.1
- Application type: +10.6
- Time to MVP: +9.1
- Compliance: +3.0

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Development speed | 5.0 | 2.5 | 15.2 |
| SEO | 5.0 | 2.2 | 13.3 |
| Team skill match | 4.5 | 2.5 | 13.3 |
| Ecosystem maturity | 5.0 | 1.5 | 9.1 |
| Rich client interactivity | 5.0 | 1.5 | 9.1 |
| Low ops burden | 4.0 | 1.5 | 6.8 |
| Learning curve | 5.0 | 1.0 | 6.1 |
| Realtime fit | 3.0 | 1.7 | 5.2 |
| Performance / latency | 4.0 | 0.8 | 3.6 |
| Hiring pool | 5.0 | 0.5 | 3.0 |
| Portability (low lock-in) | 4.0 | 0.5 | 2.3 |
| Structure for large teams | 3.0 | 0.3 | 0.9 |

**Alternatives**
- Nuxt (Vue) (stack 91.1, -3.0): Scores 75.7 on its own; its stack is 3.0 points behind the pick.
- React SPA (Vite) (stack 91.0, -3.1): Scores 75.4 on its own; its stack is 3.1 points behind the pick.

**Why not the others?**
- Why not Nuxt (Vue)? (runner-up) Swapping it in lowers the stack score by 3.0 points. Next.js (React) is stronger on development speed (5.0 vs 4.0), team skill match (4.5 vs 3.5); Nuxt (Vue) is stronger on portability (low lock-in) (5.0 vs 4.0).
- Why not React SPA (Vite)? (popular choice) Swapping it in lowers the stack score by 3.1 points. Next.js (React) is stronger on SEO (5.0 vs 2.0), development speed (5.0 vs 4.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0).

**Excluded by hard constraints**
- React Native (Expo): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Flutter: Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Native iOS + Android (Swift / Kotlin): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- No frontend (API only): You target a user interface, so a frontend is needed
- Qt (C++): Desktop toolkit; you do not target desktop
- Tauri (Rust): Desktop toolkit; you do not target desktop
- .NET MAUI (C#): Desktop toolkit; you do not target desktop
- Electron (JavaScript): Desktop toolkit; you do not target desktop
- Unity (C#): Game engine; the project is not a game
- Unreal Engine (C++): Game engine; the project is not a game

### Backend: Python + FastAPI (90.0)

Async Python API framework with type-hint validation (Pydantic) and automatic OpenAPI docs.

Python + FastAPI serves the API at about 69 requests/s at peak (Medium (10k-100k daily users)) for a team of 4. The team lists fastapi and Python, so it needs no new server language (team skill match 5.0/5). It runs as a long-running Python service, so background jobs, WebSockets and database connection pools live in one deployable process. Python + Django is within 0.7 points, inside the tie margin (stacks this close count as tied); the tie went to Python + FastAPI on adjacent team skills (19 vs 18.5, summed skill fit).

**Why**
- Development speed: 5.0/5 vs 4.3 average for this layer - weighted up because: 12-week MVP; Fast iteration on models.
- Learning curve: 5.0/5 vs 4.0 average for this layer - weighted up because: 12-week MVP.
- Portability (low lock-in): 5.0/5 vs 4.5 average for this layer.
- Bonus +6: Your team already ships Python + FastAPI (fastapi, python listed in team skills).
- Stack synergy (+12): Model inference and pipelines stay in Python (PyTorch, Hugging Face, scikit-learn), so no second runtime is needed.
- Team skill match (5.0/5, direct): your team lists fastapi, Python, a direct match for Python + FastAPI.
- Direct access to the Python ML/data ecosystem (PyTorch, scikit-learn, pandas)
- Auto-generated OpenAPI docs and request validation
- Async I/O for model-serving and API gateways

**Trade-offs**
- No built-in admin/ORM/auth (bring SQLAlchemy, etc.)
- Python is slower than Go/.NET for CPU-bound request handling

**Versus runner-up:** Python + FastAPI and Python + Django are within 0.7 points of each other, inside the 1-point tie margin, so they count as tied. Python + FastAPI is stronger on realtime fit (3.0 vs 2.0), performance / latency (4.0 vs 3.0); Python + Django is stronger on ecosystem maturity (5.0 vs 4.0), structure for large teams (4.0 vs 2.0). Choose Python + Django instead if a mature ecosystem matters more to you than live updates. The tie went to Python + FastAPI on adjacent team skills (19 vs 18.5, summed skill fit). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +39.1
- Team skills: +21.8
- Time to MVP: +9.5
- Application type: +4.8
- Monthly budget: +3.2
- Realtime needs: +3.2

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Development speed | 5.0 | 2.5 | 15.8 |
| Team skill match | 5.0 | 2.5 | 15.8 |
| Cost at your scale | 5.0 | 1.5 | 9.5 |
| Scalability | 4.0 | 1.5 | 7.1 |
| Low ops burden | 4.0 | 1.5 | 7.1 |
| Ecosystem maturity | 4.0 | 1.5 | 7.1 |
| Learning curve | 5.0 | 1.0 | 6.3 |
| Realtime fit | 3.0 | 1.7 | 5.4 |
| Performance / latency | 4.0 | 0.8 | 3.8 |
| Portability (low lock-in) | 5.0 | 0.5 | 3.2 |
| Hiring pool | 4.0 | 0.5 | 2.4 |
| Structure for large teams | 2.0 | 0.3 | 0.5 |
| Adjustment: Your team already ships Python + FastAPI (fastapi, python listed in team skills) | | | +6.0 |

**Alternatives**
- Python + Django (stack 93.5, -0.7): Scores 87.4 on its own; its stack is 0.7 points behind the pick.
- Node.js + Express (stack 89.2, -5.0): Loses: Model inference and pipelines stay in Python (PyTorch, Hugging Face, scikit-learn), so no second runtime is needed.

**Why not the others?**
- Why not Python + Django? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.7 points lower; either is defensible. Python + FastAPI is stronger on realtime fit (3.0 vs 2.0), team skill match (5.0 vs 4.5); Python + Django is stronger on ecosystem maturity (5.0 vs 4.0), structure for large teams (4.0 vs 2.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 5.0 points. Python + FastAPI is stronger on development speed (5.0 vs 4.0), team skill match (5.0 vs 4.5); Node.js + Express is stronger on realtime fit (4.0 vs 3.0), ecosystem maturity (5.0 vs 4.0). 3.0 of the 5.0 points come from a stack compatibility rule: Model inference and pipelines stay in Python (PyTorch, Hugging Face, scikit-learn), so no second runtime is needed.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 12.0 points. Python + FastAPI is stronger on team skill match (5.0 vs 1.5), development speed (5.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on ecosystem maturity (5.0 vs 4.0), scalability (5.0 vs 4.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn. 3.0 of the 12.0 points come from a stack compatibility rule: Model inference and pipelines stay in Python (PyTorch, Hugging Face, scikit-learn), so no second runtime is needed.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: PostgreSQL (87.0)

Open-source relational database with ACID transactions, JSONB, full-text search and extensions (PostGIS, pgvector, TimescaleDB).

Your data is mainly relational and reaches about 560 GB within 12 months; PostgreSQL fits relational data 5/5. You need strong consistency, and PostgreSQL gives it: a read after a write always sees that write. Its share of the estimated bill is $75-$989 a month, against a total budget of $1,500 a month. It leads the runner-up, Microsoft SQL Server, by 1.6 points.

Suggested offering: Cloud SQL / AlloyDB for PostgreSQL

**Why**
- Data-model fit: 4.7/5 vs 3.9 average for this layer.
- Consistency fit: 5.0/5 vs 4.7 average for this layer - weighted up because: Strong consistency required.
- Realtime fit: 3.0/5 vs 2.6 average for this layer - weighted up because: Some realtime features; Streamed model output holds a connection open for each response.
- Team skill match (4.5/5, direct): your team lists SQL, a direct match for PostgreSQL.
- Default choice for relational data: constraints, joins, transactions
- Extensions cover JSON, search, geo, time-series and vectors
- Every cloud offers it managed; zero vendor lock-in

**Trade-offs**
- Single-writer primary: write scale-out needs sharding (Citus) or Aurora Limitless
- Connection-per-process model needs PgBouncer/RDS Proxy under serverless

**Versus runner-up:** PostgreSQL beats Microsoft SQL Server by 1.6 points (out of 100 on the whole-stack score, the average of the four layer scores), mainly on general quality (baseline weights) (+1.1), realtime needs (+0.3), application type (+0.1).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +53.5
- Team skills: +10.7
- Consistency need: +7.3
- Time to MVP: +2.4
- Compliance: +2.4
- Realtime needs: +2.4

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.7 | 5.0 | 22.4 |
| Consistency fit | 5.0 | 2.5 | 12.2 |
| Team skill match | 4.5 | 2.5 | 10.7 |
| Ecosystem maturity | 5.0 | 1.5 | 7.3 |
| Cost at your scale | 4.6 | 1.5 | 6.6 |
| Scalability | 4.0 | 1.5 | 5.5 |
| Low ops burden | 4.0 | 1.5 | 5.5 |
| Learning curve | 5.0 | 1.0 | 4.9 |
| Realtime fit | 3.0 | 1.7 | 4.2 |
| Performance / latency | 4.0 | 0.8 | 2.9 |
| Hiring pool | 5.0 | 0.5 | 2.4 |
| Portability (low lock-in) | 5.0 | 0.5 | 2.4 |

**Alternatives**
- Microsoft SQL Server (stack 92.5, -1.6): Scores 80.5 on its own; its stack is 1.6 points behind the pick.
- MySQL (stack 90.1, -4.0): Scores 70.8 on its own; its stack is 4.0 points behind the pick.

**Why not the others?**
- Why not Microsoft SQL Server? (runner-up) Swapping it in lowers the stack score by 1.6 points. PostgreSQL is stronger on realtime fit (3.0 vs 2.0), data-model fit (4.7 vs 4.3).
- Why not MySQL? (popular choice) Swapping it in lowers the stack score by 4.0 points. PostgreSQL is stronger on data-model fit (4.7 vs 4.0), realtime fit (3.0 vs 2.0); MySQL takes a penalty: Fits your vector records 2/5, so they would need a second database; PostgreSQL holds all your record shapes.
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 8.1 points. PostgreSQL is stronger on data-model fit (4.7 vs 2.7), consistency fit (5.0 vs 3.5); MongoDB is stronger on realtime fit (4.0 vs 3.0), scalability (5.0 vs 4.0); MongoDB takes a penalty: Only 2/5 fit for your primary 'relational' data.

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5)
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~560 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your relational, vector data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational, vector data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational, vector data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.9% availability
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: Google Cloud Run (99.8)

Serverless containers: any Docker image, request-based autoscaling to zero, WebSockets supported.

Google Cloud Run hosts the stack for users in North America and Europe at a 99.9% availability target. It runs the Python + FastAPI API as long-running processes with WebSockets, sized for ~69 requests/s at peak. Its share of the estimated bill is $60-$383 a month, against a total budget of $1,500 a month. It leads the runner-up, DigitalOcean (App Platform + Managed DBs), by 2.8 points.

Runs here: Next.js (server rendering + static files), the Python + FastAPI API as long-running processes. The database runs as a separate managed service (see Database).

**Why**
- Low ops burden: 5.0/5 vs 4.2 average for this layer - weighted up because: Team of 4.
- Learning curve: 5.0/5 vs 4.4 average for this layer - weighted up because: 12-week MVP.
- Scalability: 5.0/5 vs 4.6 average for this layer - weighted up because: Medium (10k-100k daily users).
- Bonus +12.0: Runs on your preferred cloud (GCP).
- Team skill match (5.0/5, direct): your team lists Docker, GCP, a direct match for Google Cloud Run.
- Container portability with serverless billing
- No cluster to operate

**Trade-offs**
- Request timeout (max 60 min) limits very long-lived connections
- Cold starts when scaled to zero

**Versus runner-up:** Google Cloud Run beats DigitalOcean (App Platform + Managed DBs) by 2.8 points (out of 100 on the whole-stack score, the average of the four layer scores), mainly on cloud preference (+3.0), team skills (+0.6), general quality (baseline weights) (+0.6). DigitalOcean (App Platform + Managed DBs) is stronger on stack compatibility (+1.0), realtime needs (+0.5).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +44.7
- Team skills: +18.5
- Cloud preference: +12.0
- Scale (DAU / peak RPS): +3.7
- Time to MVP: +3.7
- Team size: +3.7

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 5.0 | 2.5 | 18.5 |
| Scalability | 5.0 | 1.5 | 11.1 |
| Low ops burden | 5.0 | 1.5 | 11.1 |
| Cost at your scale | 4.7 | 1.5 | 10.4 |
| Ecosystem maturity | 4.0 | 1.5 | 8.3 |
| Learning curve | 5.0 | 1.0 | 7.4 |
| Region coverage | 5.0 | 1.0 | 7.4 |
| Realtime fit | 3.0 | 1.7 | 6.3 |
| Performance / latency | 4.0 | 0.8 | 4.4 |
| Portability (low lock-in) | 4.0 | 0.5 | 2.8 |
| Adjustment: Runs on your preferred cloud (GCP) | | | +12.0 |

**Alternatives**
- DigitalOcean (App Platform + Managed DBs) (stack 91.3, -2.8): Note: Git-push deploys with managed database add-ons are the shortest path to production for a monolith.
- Google Kubernetes Engine (Autopilot) (stack 90.8, -3.4): Scores 86.4 on its own; its stack is 3.4 points behind the pick.

**Why not the others?**
- Why not DigitalOcean (App Platform + Managed DBs)? (runner-up) Swapping it in lowers the stack score by 2.8 points. Google Cloud Run is stronger on scalability (5.0 vs 4.0), team skill match (5.0 vs 4.5); DigitalOcean (App Platform + Managed DBs) is stronger on realtime fit (4.0 vs 3.0), cost at your scale (4.8 vs 4.7).
- Why not Vercel? (popular choice) Swapping it in lowers the stack score by 6.5 points. Google Cloud Run is stronger on team skill match (5.0 vs 4.0), realtime fit (3.0 vs 2.0); Vercel is stronger on performance / latency (5.0 vs 4.0), cost at your scale (4.8 vs 4.7). 1.7 of the 6.5 points come from a stack compatibility rule: This framework can be adapted to serverless functions, but you lose in-memory state, background jobs and WebSockets.
- Why not AWS ECS on Fargate? (popular choice) Swapping it in lowers the stack score by 6.0 points. Google Cloud Run is stronger on team skill match (5.0 vs 2.5), low ops burden (5.0 vs 3.0); AWS ECS on Fargate is stronger on realtime fit (4.0 vs 3.0), ecosystem maturity (5.0 vs 4.0).
- Why not Render? (popular choice) Swapping it in lowers the stack score by 3.5 points. Google Cloud Run is stronger on scalability (5.0 vs 4.0), ecosystem maturity (4.0 vs 3.0); Render is stronger on realtime fit (4.0 vs 3.0), cost at your scale (4.8 vs 4.7).

**Excluded by hard constraints**
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay
- Firebase Hosting (static): Only for read-only sites; your users sign in, post or pay
- Google Cloud Storage + Cloud CDN (static): Only for read-only sites; your users sign in, post or pay
- Azure Static Web Apps: Only for read-only sites; your users sign in, post or pay; No SOC 2 report available
- Azure Blob Storage + Front Door (static): Only for read-only sites; your users sign in, post or pay; No SOC 2 report available
- Hetzner Cloud / VPS (Docker, Coolify): No SOC 2 report available
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs

## Stack compatibility checks

- (synergy, +12) Model inference and pipelines stay in Python (PyTorch, Hugging Face, scikit-learn), so no second runtime is needed.

## Supporting services

- **Cache**: Redis/Valkey (Memorystore): Read-heavy traffic, a tight latency target or hot key-value data: keep hot reads and sessions in memory in front of a durable primary database.
- **Realtime**: WebSockets in the Python + FastAPI app (FastAPI WebSockets): Chat and live updates for a part of the product: the app server holds the connections itself; add Redis pub/sub only when a second instance must reach the same users.
- **Vector search**: pgvector extension in the primary Postgres: Keeps embeddings next to relational data with transactional consistency; move to a dedicated vector DB only past ~10M+ vectors.
- **Background jobs**: Celery (Redis/Valkey broker): Send emails, process uploads and call slow APIs outside the request path. Celery with a Redis broker (or RQ / Dramatiq) keeps its jobs in Redis, so the app needs a Redis/Valkey instance (Memorystore).
- **Object storage**: Cloud Storage + Cloud CDN: Media and documents belong in object storage, not the database.
- **Authentication**: FastAPI's OAuth2 password flow with hashed passwords in your API, with the users in your database: Clerk would cost about $2,025 a month at ~150,000 monthly users: Do not hand-roll password storage, MFA or SSO.
- **Model serving**: Vertex AI endpoints: Keep GPU inference separate from the web tier so each scales on its own metric.
- **Observability**: OpenTelemetry instrumentation -> Cloud Monitoring/Trace: Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: Google Cloud Run | 60 | 383 | Medium (10k-100k daily users) price band, from the band's floor up to its price at ~3x the load, for 30,000 daily users (48% of the way up the tier, log scale) |
| Database: PostgreSQL | 75 | 989 | Medium (100 GB-1 TB of data) database tier (~560 GB in 12 months), from the band's floor up to its price at ~3x the load, for ~560 GB of data (75% of the way up the tier, log scale); priced as Cloud SQL / AlloyDB for PostgreSQL; x1.5 for 99.9% availability (standby/replicas) |
| Cache: Redis / Valkey | 30 | 192 | Medium (10k-100k daily users) price band (the app's scale), from the band's floor up to its price at ~3x the load, for 30,000 daily users (48% of the way up the tier, log scale) |
| Model serving: inference | 202 | 3,375 | ~1 call/user/day x 1,500 tokens = ~1,350M tokens/month at $0.15-2.5 per million |
| **Total** | **367** | **4,939** | |

About ₹35,232-₹474,144 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, each read where the project sits inside its tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Must run on-premises**: hosting: Google Cloud Run -> On-prem VMs + Docker Compose
  - Why hosting changes: Google Cloud Run is now ruled out: Public-cloud service; deployment must be on-premises.
- **Team has no relevant prior skills**: backend: Python + FastAPI -> Node.js + Express
  - Why backend changes: Python + FastAPI lost a bonus (Your team already ships Python + FastAPI (fastapi, python listed in team skills)), moving the gap 6.0 points toward Node.js + Express; hiring pool moved the gap 4.0 points toward Node.js + Express (Node.js + Express 5.0/5 vs Python + FastAPI 4.0/5, weight 0.5 -> 3.0).

## Next-best complete stacks

- Next.js (React) + Python + Django + PostgreSQL + Google Cloud Run (93.5, -0.7)
- Next.js (React) + Python + FastAPI + Microsoft SQL Server + Google Cloud Run (92.5, -1.6)
- Next.js (React) + Python + Django + Microsoft SQL Server + Google Cloud Run (91.9, -2.3)

## Sources

- https://nextjs.org/docs
- https://react.dev
- https://survey.stackoverflow.co/2025/technology
- https://web.dev/articles/rendering-on-the-web
- https://nextjs.org/docs/app/getting-started/deploying
- https://fastapi.tiangolo.com/
- https://docs.pydantic.dev/latest/
- https://fastapi.tiangolo.com/advanced/websockets/
- https://www.postgresql.org/docs/current/
- https://github.com/pgvector/pgvector
- https://www.citusdata.com/
- https://www.pgbouncer.org/
- https://supabase.com/pricing
- https://neon.com/docs/introduction/plans
- https://aiven.io/pricing/postgresql
- https://supabase.com/docs/guides/platform/compute-and-disk
- https://neon.com/pricing
- https://neon.com/docs/introduction/regions
- https://supabase.com/docs/guides/platform/regions
- https://vercel.com/docs/marketplace-storage
- https://neon.com/docs/security/compliance
- https://cloud.google.com/run/docs
- https://cloud.google.com/run/pricing
- https://cloud.google.com/run/docs/triggering/websockets
- https://cloud.google.com/security/compliance/hipaa
- https://cloud.google.com/docs/buildpacks/php
- https://cloud.google.com/docs/buildpacks/overview
- https://cloud.google.com/run/sla
- https://cloud.google.com/run/docs/configuring/min-instances
