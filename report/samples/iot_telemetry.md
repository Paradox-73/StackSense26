# StackSense recommendation: GridPulse (IoT)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For an 'IoT / telemetry ingestion' project at Large (500-5,000 req/s at peak) scale (~4,000 peak req/s) built by 6 engineer(s) in 16 weeks, StackSense recommends React SPA (Vite) + Go (net/http, chi or Gin) + TimescaleDB (Postgres) + AWS ECS on Fargate (architecture: Modular monolith). Estimated infrastructure cost: $1,365-$7,700/month (stretch budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **React SPA (Vite)** | 71.9 | 1.8, solid (1.5-4 points) | Next.js (React) (-1.8) |
| Backend | **Go (net/http, chi or Gin)** | 92.9 | 2.0, solid (1.5-4 points) | Python + FastAPI (-2.0) |
| Database | **TimescaleDB (Postgres)** | 79.3 | 4.2, clear (4+ points) | PostgreSQL (-4.2) |
| Hosting | **AWS ECS on Fargate** | 100.0 | 3.1, solid (1.5-4 points) | Fly.io (-3.1) |

Stack score: **86.0** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Modular monolith**: With 6 engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later. Sized for ~4,000 requests/s at peak, about 5,600 GB of data within 12 months and a 99.9% availability target.

Availability approach: 2+ app instances behind a load balancer, managed DB with automated failover

### How the parts fit

1. **Request path**: The browser loads React SPA (Vite)'s built files from Amazon S3 + CloudFront; it sends API calls to the Go service on AWS ECS on Fargate (~4,000 requests/s at peak), which queries TimescaleDB (Postgres).
2. **Sign-in**: Sign-in uses Auth0 (EU tenant) / framework built-in auth; the Go API checks the session or token on every request.
3. **Data**: TimescaleDB (Postgres) is the system of record (about 5,600 GB within 12 months). Every store above is placed in the region your residency rule requires.
4. **Deploy**: CI builds a container image and rolls it out on AWS ECS on Fargate with health checks and zero-downtime restarts. The frontend's built files are uploaded to Amazon S3 and the CDN cache is invalidated. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Large (500-5,000 req/s at peak) (peak ~4,000 req/s, provided); database tier: Large (1-10 TB of data) (~5,600 GB in 12 months)
- Budget: ~$4,000/month
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Per-layer reasoning

### Frontend: React SPA (Vite) (71.9)

Client-rendered single-page React app built with Vite; deploys as static files to any CDN.

React SPA (Vite) is the frontend for an IoT / telemetry ingestion project with about 40,000 active devices (~4,000 requests/s at peak), built by a team of 6 in 16 weeks. Search visibility is marked not needed (behind login), so rendering in the browser is acceptable, and it scores 5.0/5 for rich, app-like interaction. It leads the runner-up, Next.js (React), by 1.8 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer - weighted up because: Regulated workload.
- Rich client interactivity: 5.0/5 vs 4.1 average for this layer - weighted up because: Live device dashboards.
- Low ops burden: 5.0/5 vs 4.4 average for this layer - weighted up because: Team of 6.
- Bonus +5.0: Your team lists no frontend skill, so it will hire or learn for this frontend: hiring pool 5/5.
- Static build: cheapest and simplest hosting
- Huge component ecosystem (dashboards, charts, admin UIs)
- No server to operate for the UI

**Trade-offs**
- Team skill match is only 1.5/5 (weight 2.5).
- Client-side rendering hurts SEO and first paint on slow phones
- Routing, data fetching and state are your own architecture decisions

**Risks**
- Nobody on the team listed React SPA (Vite) or a closely related skill; plan 2-4 weeks to learn it.

**Versus runner-up:** React SPA (Vite) beats Next.js (React) by 1.8 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on seo need (+2.0), team size (+0.3). Next.js (React) is stronger on scale (dau / peak rps) (+0.3), general quality (baseline weights) (+0.2).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +41.8
- Application type: +8.2
- Team skills: +7.6
- Team size: +4.1
- Compliance: +4.1
- Realtime needs: +4.1

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Low ops burden | 5.0 | 1.5 | 12.3 |
| Ecosystem maturity | 5.0 | 1.5 | 12.3 |
| Rich client interactivity | 5.0 | 1.5 | 12.3 |
| Development speed | 4.0 | 1.0 | 6.2 |
| Realtime fit | 3.0 | 1.2 | 4.9 |
| Performance / latency | 3.0 | 1.0 | 4.1 |
| Hiring pool | 5.0 | 0.5 | 4.1 |
| Portability (low lock-in) | 5.0 | 0.5 | 4.1 |
| Learning curve | 4.0 | 0.5 | 3.1 |
| Team skill match | 1.5 | 2.5 | 2.6 |
| Structure for large teams | 2.0 | 0.3 | 0.6 |
| SEO | 2.0 | 0.2 | 0.4 |
| Adjustment: Your team lists no frontend skill, so it will hire or learn for this frontend: hiring pool 5/5 | | | +5.0 |

**Alternatives**
- Next.js (React) (stack 84.2, -1.8): Scores 64.7 on its own; its stack is 1.8 stack points behind the pick.
- Angular (stack 83.8, -2.3): Scores 62.9 on its own; its stack is 2.3 stack points behind the pick.

**Why not the others?**
- Why not Next.js (React)? (runner-up) Swapping it in lowers the stack score by 1.8 points. React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0); Next.js (React) is stronger on performance / latency (4.0 vs 3.0), development speed (5.0 vs 4.0); Next.js (React) takes a penalty: No search visibility needed: server rendering adds a Node.js server for pages that React SPA (Vite) serves as static files.

**Excluded by hard constraints**
- React Native (Expo): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Flutter: Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Native iOS + Android (Swift / Kotlin): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)

### Backend: Go (net/http, chi or Gin) (92.9)

Compiled, statically typed language with built-in concurrency; ships as a single static binary.

Go (net/http, chi or Gin) serves the API at about 4,000 requests/s at peak (Large (500-5,000 req/s at peak)) for a team of 6. It runs as a long-running Go service, so background jobs, WebSockets and database connection pools live in one deployable process. It leads the runner-up, Python + FastAPI, by 2.0 stack points.

**Why**
- Scalability: 5.0/5 vs 4.3 average for this layer - weighted up because: Large (500-5,000 req/s at peak); Continuous device ingestion.
- Performance / latency: 5.0/5 vs 3.7 average for this layer - weighted up because: Large (500-5,000 req/s at peak).
- Low ops burden: 5.0/5 vs 4.2 average for this layer - weighted up because: Team of 6.
- Bonus +6: Your team already ships Go (net/http, chi or Gin) (go listed in team skills).
- Team skill match (4.5/5, direct): your team lists Go, a direct match for Go (net/http, chi or Gin).
- High throughput per core and low memory means fewer servers
- Goroutines handle many concurrent connections (telemetry, websockets)
- Single binary, tiny container images, fast cold starts

**Trade-offs**
- More code for CRUD than Rails/Django
- Smaller web-framework ecosystem

**Versus runner-up:** Go (net/http, chi or Gin) beats Python + FastAPI by 2.0 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on scale (dau / peak rps) (+0.8), application type (+0.4), realtime needs (+0.4).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +41.5
- Team skills: +20.6
- Scale (DAU / peak RPS): +13.3
- Application type: +6.7
- Realtime needs: +5.0
- Team size: +3.3

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Scalability | 5.0 | 3.5 | 23.3 |
| Team skill match | 4.5 | 2.5 | 14.6 |
| Low ops burden | 5.0 | 1.5 | 10.0 |
| Ecosystem maturity | 4.0 | 1.5 | 7.5 |
| Cost at your scale | 5.0 | 1.0 | 6.7 |
| Performance / latency | 5.0 | 1.0 | 6.7 |
| Realtime fit | 4.0 | 1.2 | 6.0 |
| Learning curve | 5.0 | 0.5 | 3.3 |
| Development speed | 3.0 | 1.0 | 3.3 |
| Portability (low lock-in) | 5.0 | 0.5 | 3.3 |
| Hiring pool | 3.0 | 0.5 | 1.7 |
| Structure for large teams | 2.0 | 0.3 | 0.5 |
| Adjustment: Your team already ships Go (net/http, chi or Gin) (go listed in team skills) | | | +6.0 |

**Alternatives**
- Python + FastAPI (stack 84.1, -2.0): Scores 85.1 on its own; its stack is 2.0 stack points behind the pick.
- Python + Django (stack 84.0, -2.0): Scores 84.9 on its own; its stack is 2.0 stack points behind the pick.

**Why not the others?**
- Why not Python + FastAPI? (runner-up) Swapping it in lowers the stack score by 2.0 points. Go (net/http, chi or Gin) is stronger on scalability (5.0 vs 4.0), low ops burden (5.0 vs 4.0); Python + FastAPI is stronger on development speed (5.0 vs 3.0), hiring pool (4.0 vs 3.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 8.2 points. Go (net/http, chi or Gin) is stronger on team skill match (4.5 vs 1.5), scalability (5.0 vs 4.0); Node.js + Express is stronger on ecosystem maturity (5.0 vs 4.0), hiring pool (5.0 vs 3.0); Node.js + Express takes a penalty: Nobody on the team listed Node.js or a closely related skill: a new server language to learn.
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 2.0 points. Go (net/http, chi or Gin) is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 2.0); Python + Django is stronger on development speed (5.0 vs 3.0), ecosystem maturity (5.0 vs 4.0).
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 8.0 points. Go (net/http, chi or Gin) is stronger on team skill match (4.5 vs 1.5), low ops burden (5.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on ecosystem maturity (5.0 vs 4.0), hiring pool (5.0 vs 3.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: TimescaleDB (Postgres) (79.3)

Postgres extension adding hypertables, compression and continuous aggregates for time-series.

Your data is mainly time-series and reaches about 5,600 GB within 12 months; TimescaleDB (Postgres) fits time-series data 5/5. The workload is write-heavy, and its write scaling scores 4/5. Its share of the estimated bill is $750-$4,500 a month, against a total budget of $4,000 a month. It leads the runner-up, PostgreSQL, by 4.2 stack points.

Suggested offering: Timescale Cloud (Tiger Data) on AWS

**Why**
- Data-model fit: 4.5/5 vs 3.5 average for this layer - weighted up because: Write-heavy: the storage engine must match the workload.
- Learning curve: 5.0/5 vs 4.1 average for this layer.
- Hiring pool: 4.0/5 vs 3.5 average for this layer.
- Team skill match (5.0/5, direct): your team lists PostgreSQL, SQL, a direct match for TimescaleDB (Postgres).
- Full SQL + joins with relational data on the same database
- 90%+ compression and automatic rollups for telemetry
- Postgres tooling and skills carry over

**Trade-offs**
- Realtime fit is only 2.0/5 (weight 1.2).
- Some features use the Timescale License (not on every managed Postgres)
- Very high-cardinality firehoses may need ClickHouse instead

**Risks**
- Timescale Cloud (Tiger Data) on AWS is a separate service from AWS ECS on Fargate: create it in the cloud region where AWS ECS on Fargate runs your app, or every query crosses between regions.

**Versus runner-up:** TimescaleDB (Postgres) beats PostgreSQL by 4.2 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on data shape (+3.5), general quality (baseline weights) (+0.8), read/write mix (+0.3). PostgreSQL is stronger on realtime needs (+0.3), compliance (+0.1).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +47.3
- Team skills: +12.1
- Scale (DAU / peak RPS): +7.2
- Read/write mix: +4.2
- Application type: +3.6
- Team size: +1.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.5 | 6.0 | 25.1 |
| Scalability | 4.0 | 3.5 | 12.7 |
| Team skill match | 5.0 | 2.5 | 12.1 |
| Low ops burden | 4.0 | 1.5 | 5.4 |
| Ecosystem maturity | 4.0 | 1.5 | 5.4 |
| Cost at your scale | 4.1 | 1.0 | 3.8 |
| Performance / latency | 4.0 | 1.0 | 3.6 |
| Consistency fit | 4.0 | 1.0 | 3.6 |
| Learning curve | 5.0 | 0.5 | 2.4 |
| Hiring pool | 4.0 | 0.5 | 1.8 |
| Portability (low lock-in) | 4.0 | 0.5 | 1.8 |
| Realtime fit | 2.0 | 1.2 | 1.4 |

**Alternatives**
- PostgreSQL (stack 81.8, -4.2): Scores 62.5 on its own; its stack is 4.2 stack points behind the pick.
- Microsoft SQL Server / Azure SQL Database (stack 80.5, -5.5): Scores 57.3 on its own; its stack is 5.5 stack points behind the pick.

**Why not the others?**
- Why not PostgreSQL? (runner-up) Swapping it in lowers the stack score by 4.2 points. TimescaleDB (Postgres) is stronger on data-model fit (4.5 vs 3.5); PostgreSQL is stronger on ecosystem maturity (5.0 vs 4.0), realtime fit (3.0 vs 2.0); PostgreSQL takes a penalty: Only 3/5 fit for your primary 'time series' data.
- Why not MySQL? (popular choice) Ruled out for your answers: Write-heavy load at Large (1-10 TB of data) on a store that fits 'time_series' data 2/5 with write scaling 3/5.
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 7.2 points. TimescaleDB (Postgres) is stronger on team skill match (5.0 vs 1.5), data-model fit (4.5 vs 3.5); MongoDB is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 2.0); MongoDB takes a penalty: Fits your data shapes 3.5/5 against 4.5/5 for TimescaleDB (Postgres).

**Excluded by hard constraints**
- MySQL: Write-heavy load at Large (1-10 TB of data) on a store that fits 'time_series' data 2/5 with write scaling 3/5
- Redis / Valkey: Write-heavy load at Large (1-10 TB of data) on a store that fits 'time_series' data 2/5 with write scaling 5/5; In-memory store: ~5,600 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your time series, relational data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- OpenSearch / Elasticsearch: Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Poor fit for 'time_series' data as the primary store (1/5); Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your time series, relational data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Write-heavy load at Large (1-10 TB of data) on a store that fits 'time_series' data 2/5 with write scaling 1/5; Single-node file database: no failover, so it cannot meet 99.9% availability; One writer at a time for the whole file: 144.0M+ requests a day at Large (500-5,000 req/s at peak) is past the 1M a day SQLite's own guide says it has been shown to handle
- Cloud Firestore: Poor fit for 'time_series' data as the primary store (2/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'time_series' data as the primary store (1/5)

### Hosting: AWS ECS on Fargate (100.0)

Serverless containers on AWS: no nodes to manage, integrates with ALB, RDS, IAM, CloudWatch.

AWS ECS on Fargate hosts the stack for users in Europe at a 99.9% availability target. It runs the Go API as long-running processes with WebSockets, sized for ~4,000 requests/s at peak. Its share of the estimated bill is $600-$3,000 a month, against a total budget of $4,000 a month. It leads the runner-up, Fly.io, by 3.1 stack points.

Runs here: the Go API as long-running processes. React SPA is built to static files that are served from Amazon S3 + CloudFront, not from these instances (see Supporting services). The database runs as a separate managed service (see Database).

**Why**
- Scalability: 5.0/5 vs 4.5 average for this layer - weighted up because: Large (500-5,000 req/s at peak); Continuous device ingestion.
- Ecosystem maturity: 5.0/5 vs 4.2 average for this layer - weighted up because: Regulated workload.
- Realtime fit: 4.0/5 vs 3.5 average for this layer - weighted up because: Some realtime features.
- Bonus +12.0: Runs on your preferred cloud (AWS).
- Team skill match (5.0/5, direct): your team lists AWS, Docker, a direct match for AWS ECS on Fargate.
- Containers without Kubernetes complexity

**Trade-offs**
- AWS networking/IAM learning curve
- ALB + NAT gateway base costs even when idle

**Versus runner-up:** AWS ECS on Fargate beats Fly.io by 3.1 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on cloud preference (+3.0), team skills (+0.5), application type (+0.4). Fly.io is stronger on stack compatibility (+1.0), realtime needs (+0.4).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +37.2
- Team skills: +16.4
- Scale (DAU / peak RPS): +12.3
- Cloud preference: +12.0
- Compliance: +9.9
- Application type: +6.6

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Scalability | 5.0 | 3.5 | 23.0 |
| Team skill match | 5.0 | 2.5 | 16.4 |
| Region coverage | 5.0 | 2.0 | 13.2 |
| Ecosystem maturity | 5.0 | 1.5 | 9.9 |
| Realtime fit | 4.0 | 1.2 | 5.9 |
| Cost at your scale | 4.5 | 1.0 | 5.8 |
| Low ops burden | 3.0 | 1.5 | 4.9 |
| Performance / latency | 4.0 | 1.0 | 4.9 |
| Learning curve | 5.0 | 0.5 | 3.3 |
| Portability (low lock-in) | 3.0 | 0.5 | 1.6 |
| Adjustment: Runs on your preferred cloud (AWS) | | | +12.0 |

**Alternatives**
- Fly.io (stack 82.9, -3.1): Note: Tiny static binaries give near-instant cold starts on scale-to-zero platforms.
- AWS EKS (Kubernetes) (stack 82.7, -3.3): Scores 86.7 on its own; its stack is 3.3 stack points behind the pick.

**Why not the others?**
- Why not Fly.io? (runner-up) Swapping it in lowers the stack score by 3.1 points. AWS ECS on Fargate is stronger on scalability (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0); Fly.io is stronger on low ops burden (4.0 vs 3.0), realtime fit (5.0 vs 4.0).
- Why not Vercel? (popular choice) Swapping it in lowers the stack score by 7.8 points. AWS ECS on Fargate is stronger on team skill match (5.0 vs 1.5), realtime fit (4.0 vs 2.0); Vercel is stronger on low ops burden (5.0 vs 3.0), performance / latency (5.0 vs 4.0).
- Why not Render? (popular choice) Swapping it in lowers the stack score by 4.9 points. AWS ECS on Fargate is stronger on scalability (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0); Render is stronger on low ops burden (5.0 vs 3.0), portability (low lock-in) (4.0 vs 3.0).

**Excluded by hard constraints**
- Cloudflare Pages + Workers: Keeping data and TLS termination inside India or the EU needs the Data Localization Suite, an Enterprise add-on; treated as not meeting a residency rule.
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud

## Supporting services

- **Ingestion buffer**: Amazon Kinesis / MSK (MQTT via AWS IoT Core): A durable log absorbs write bursts and keeps device ingestion separate from database writes, and lets you replay messages.
- **Static frontend**: Amazon S3 + CloudFront: React SPA is built to static files (HTML, JavaScript, CSS): a bucket behind the cloud's CDN serves them from the edge, so the Go instances on AWS ECS on Fargate only answer API calls, and a frontend release is an upload plus a cache invalidation.
- **Authentication**: Auth0 (EU tenant) / framework built-in auth: Do not hand-roll password storage, MFA or SSO.
- **Observability**: OpenTelemetry instrumentation -> CloudWatch + X-Ray: Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: AWS ECS on Fargate | 600 | 3,000 | Large (500-5,000 req/s at peak) price band; x1.5 for 99.9% availability (redundant instances) |
| Database: TimescaleDB (Postgres) | 750 | 4,500 | Large (1-10 TB of data) database tier (~5,600 GB in 12 months); x1.5 for 99.9% availability (standby/replicas) |
| Static frontend: AWS S3 + CloudFront (static) | 15 | 200 | Large (500-5,000 req/s at peak) price band (the app's scale) |
| **Total** | **1,365** | **7,700** | |

About ₹131,040-₹739,200 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Budget cut to $800/month (x0.2)**: hosting: AWS ECS on Fargate -> Fly.io
  - Why hosting changes: Cost at your scale moved the gap 0.6 points toward Fly.io (Fly.io 3.9/5 vs AWS ECS on Fargate 3.5/5, weight 1.0 -> 1.5, was 4.7 vs 4.5); on its own AWS ECS on Fargate still scores 16.7 higher, so Fly.io wins as part of the whole stack (a stack rule now applies: Tiny static binaries give near-instant cold starts on scale-to-zero platforms).
- **SEO becomes critical**: frontend: React SPA (Vite) -> Next.js (React)
  - Why frontend changes: SEO moved the gap 18.2 points toward Next.js (React) (Next.js (React) 5.0/5 vs React SPA (Vite) 2.0/5, weight 0.2 -> 4.2).
- **Must run on-premises**: hosting: AWS ECS on Fargate -> On-prem VMs + Docker Compose
  - Why hosting changes: AWS ECS on Fargate is now ruled out: Public-cloud service; deployment must be on-premises.
- **Team has no relevant prior skills**: backend: Go (net/http, chi or Gin) -> Node.js + Express
  - Why backend changes: Node.js + Express no longer takes a penalty (Nobody on the team listed Node.js or a closely related skill: a new server language to learn), moving the gap 14.0 points toward Node.js + Express; team skill match moved the gap 12.5 points toward Node.js + Express (Node.js + Express 3.0/5 vs Go (net/http, chi or Gin) 3.0/5, weight 2.5 -> 0.0, was 1.5 vs 4.5).

## Next-best complete stacks

- Next.js (React) + Go (net/http, chi or Gin) + TimescaleDB (Postgres) + AWS ECS on Fargate (84.2, -1.8)
- React SPA (Vite) + Python + FastAPI + TimescaleDB (Postgres) + AWS ECS on Fargate (84.1, -2.0)
- React SPA (Vite) + Python + Django + TimescaleDB (Postgres) + AWS ECS on Fargate (84.0, -2.0)

## Sources

- https://react.dev
- https://vite.dev/guide/
- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- https://go.dev/doc/
- https://go.dev/doc/effective_go#concurrency
- https://pkg.go.dev/net/http
- https://docs.timescale.com/
- https://docs.timescale.com/use-timescale/latest/compression/
- https://docs.timescale.com/about/latest/timescaledb-editions/
- https://cloud.google.com/sql/docs/postgres/extensions
- https://www.tigerdata.com/pricing
- https://www.tigerdata.com/docs/use-timescale/latest/hypertables
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
- https://aws.amazon.com/fargate/pricing/
- https://aws.amazon.com/compliance/hipaa-eligible-services-reference/
- https://aws.amazon.com/compliance/pci-dss-level-1-faqs/
- https://aws.amazon.com/ecs/sla/
