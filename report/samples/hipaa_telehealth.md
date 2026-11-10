# StackSense recommendation: CareLink (telehealth)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Healthcare / telehealth' project at Medium (10k-100k daily users) scale (~69 peak req/s) built by 5 engineer(s) in 20 weeks, StackSense recommends React SPA (Vite) + Python + Django + PostgreSQL + AWS ECS on Fargate (architecture: Modular monolith). Estimated infrastructure cost: $370-$1,815/month (within budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **React SPA (Vite)** | 84.0 | 1.6, solid (1.5-4 points) | Next.js (React) (-1.6) |
| Backend | **Python + Django** | 88.6 | 0.6, close call (under 1.5) | Python + FastAPI (-0.6, tie) |
| Database | **PostgreSQL** | 88.7 | 0.8, close call (under 1.5) | MySQL (-0.8, tie) |
| Hosting | **AWS ECS on Fargate** | 93.0 | 3.0, solid (1.5-4 points) | Azure App Service / Container Apps (-3.0) |
| Mobile app (iOS/Android) | React Native (Expo) | 75.8 | - | - |

Stack score: **88.6** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Modular monolith**: With 5 engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later. Sized for ~69 requests/s at peak, about 280 GB of data within 12 months and a 99.95% availability target.

Availability approach: Multi-AZ app and database, health checks, zero-downtime deploys

### How the parts fit

1. **Request path**: The browser loads React SPA (Vite)'s built files from Amazon S3 + CloudFront; it sends API calls to the Python + Django service on AWS ECS on Fargate (~69 requests/s at peak), which queries PostgreSQL.
2. **Sign-in**: Sign-in uses Amazon Cognito (HIPAA-eligible); the Python + Django API checks the session or token on every request.
3. **Data**: PostgreSQL is the system of record (about 280 GB within 12 months); uploaded files go to Amazon S3 (a separate bucket for uploaded files, served through the same CloudFront as the static frontend). PHI (protected health information) stays in the database and object storage, encrypted at rest, on services covered by a signed BAA; keep it out of logs, analytics and push notification text.
4. **Deploy**: CI builds a container image and rolls it out on AWS ECS on Fargate with health checks and zero-downtime restarts. The frontend's built files are uploaded to Amazon S3 and the CDN cache is invalidated. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Medium (10k-100k daily users) (peak ~69 req/s, derived); database tier: Medium (100 GB-1 TB of data) (~280 GB in 12 months)
- Budget: ~$3,000/month
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Per-layer reasoning

### Frontend: React SPA (Vite) (84.0)

Client-rendered single-page React app built with Vite; deploys as static files to any CDN.

React SPA (Vite) is the frontend for a Healthcare / telehealth project with about 20,000 daily users (~69 requests/s at peak), built by a team of 5 in 20 weeks. Search visibility is marked not needed (behind login), so rendering in the browser is acceptable, and it scores 5.0/5 for rich, app-like interaction. It leads the runner-up, Next.js (React), by 1.6 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer - weighted up because: Clinical systems favour proven tech; 99.95% target.
- Low ops burden: 5.0/5 vs 4.4 average for this layer - weighted up because: Team of 5.
- Hiring pool: 5.0/5 vs 3.6 average for this layer.
- Team skill match (4.5/5, direct): your team lists React, a direct match for React SPA (Vite).
- Static build: cheapest and simplest hosting
- Huge component ecosystem (dashboards, charts, admin UIs)
- No server to operate for the UI

**Trade-offs**
- Client-side rendering hurts SEO and first paint on slow phones
- Routing, data fetching and state are your own architecture decisions

**Versus runner-up:** React SPA (Vite) beats Next.js (React) by 1.6 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on seo need (+2.0), team size (+0.2). Next.js (React) is stronger on general quality (baseline weights) (+0.4), latency target (+0.2).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +41.1
- Team skills: +17.2
- Application type: +7.9
- Team size: +3.9
- Availability target: +3.9
- Compliance: +3.9

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Ecosystem maturity | 5.0 | 3.0 | 23.6 |
| Team skill match | 4.5 | 2.5 | 17.2 |
| Low ops burden | 5.0 | 1.5 | 11.8 |
| Development speed | 4.0 | 1.0 | 5.9 |
| Realtime fit | 3.0 | 1.2 | 4.7 |
| Learning curve | 5.0 | 0.5 | 3.9 |
| Performance / latency | 3.0 | 1.0 | 3.9 |
| Hiring pool | 5.0 | 0.5 | 3.9 |
| Rich client interactivity | 5.0 | 0.5 | 3.9 |
| Portability (low lock-in) | 5.0 | 0.5 | 3.9 |
| Structure for large teams | 2.0 | 0.3 | 0.6 |
| SEO | 2.0 | 0.2 | 0.4 |

**Alternatives**
- Next.js (React) (stack 87.0, -1.6): Scores 77.7 on its own; its stack is 1.6 stack points behind the pick.
- Angular (stack 86.1, -2.4): Scores 74.2 on its own; its stack is 2.4 stack points behind the pick.

**Why not the others?**
- Why not Next.js (React)? (runner-up) Swapping it in lowers the stack score by 1.6 points. React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0); Next.js (React) is stronger on performance / latency (4.0 vs 3.0), development speed (5.0 vs 4.0); Next.js (React) takes a penalty: No search visibility needed: server rendering adds a Node.js server for pages that React SPA (Vite) serves as static files.

**Excluded by hard constraints**
- React Native (Expo): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Flutter: Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Native iOS + Android (Swift / Kotlin): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)

### Backend: Python + Django (88.6)

Batteries-included Python web framework: ORM, migrations, admin, auth, forms, templates.

Python + Django serves the API at about 69 requests/s at peak (Medium (10k-100k daily users)) for a team of 5. It runs as a long-running Python service, so background jobs, WebSockets and database connection pools live in one deployable process. Python + FastAPI is within 0.6 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

**Why**
- Ecosystem maturity: 5.0/5 vs 4.4 average for this layer - weighted up because: Clinical systems favour proven tech; 99.95% target.
- Development speed: 5.0/5 vs 4.2 average for this layer.
- Learning curve: 5.0/5 vs 3.9 average for this layer.
- Bonus +6: Your team already ships Python + Django (python listed in team skills).
- Team skill match (4.5/5, direct): your team lists Python, a direct match for Python + Django.
- Auto-generated admin UI: an internal tool in days
- Mature security defaults (CSRF, SQL injection, XSS protection)
- Proven at very large scale (Instagram)

**Trade-offs**
- Realtime fit is only 2.0/5 (weight 1.2).
- Realtime needs Django Channels + Redis
- Sync-first ORM; async support is partial

**Versus runner-up:** Python + Django and Python + FastAPI are within 0.6 stack points of each other, inside the 1-point tie margin, so they count as tied. Python + Django is stronger on ecosystem maturity (5.0 vs 4.0), structure for large teams (4.0 vs 2.0); Python + FastAPI is stronger on realtime fit (3.0 vs 2.0), performance / latency (4.0 vs 3.0). Choose Python + FastAPI instead if live updates matters more to you than a mature ecosystem. Python + Django has the higher stack score. Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +40.0
- Team skills: +19.7
- Compliance: +9.4
- Application type: +6.2
- Availability target: +5.5
- Scale (DAU / peak RPS): +2.3

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Ecosystem maturity | 5.0 | 3.0 | 18.8 |
| Team skill match | 4.5 | 2.5 | 13.7 |
| Scalability | 4.0 | 2.0 | 9.4 |
| Low ops burden | 4.0 | 1.5 | 7.0 |
| Cost at your scale | 5.0 | 1.0 | 6.2 |
| Development speed | 5.0 | 1.0 | 6.2 |
| Compliance maturity (audit, isolation) | 5.0 | 1.0 | 6.2 |
| Learning curve | 5.0 | 0.5 | 3.1 |
| Performance / latency | 3.0 | 1.0 | 3.1 |
| Portability (low lock-in) | 5.0 | 0.5 | 3.1 |
| Hiring pool | 4.0 | 0.5 | 2.3 |
| Realtime fit | 2.0 | 1.2 | 1.9 |
| Structure for large teams | 4.0 | 0.3 | 1.4 |
| Adjustment: Your team already ships Python + Django (python listed in team skills) | | | +6.0 |

**Alternatives**
- Python + FastAPI (stack 88.0, -0.6): Scores 86.4 on its own; its stack is 0.6 stack points behind the pick.
- Node.js + Express (stack 87.5, -1.1): Scores 84.1 on its own; its stack is 1.1 stack points behind the pick.

**Why not the others?**
- Why not Python + FastAPI? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.6 points lower; either is defensible. Python + Django is stronger on ecosystem maturity (5.0 vs 4.0), structure for large teams (4.0 vs 2.0); Python + FastAPI is stronger on realtime fit (3.0 vs 2.0), performance / latency (4.0 vs 3.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 1.1 points. Python + Django is stronger on development speed (5.0 vs 4.0), structure for large teams (4.0 vs 1.0); Node.js + Express is stronger on realtime fit (4.0 vs 2.0), hiring pool (5.0 vs 4.0).
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 6.4 points. Python + Django is stronger on team skill match (4.5 vs 1.5), development speed (5.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on scalability (5.0 vs 4.0), realtime fit (3.0 vs 2.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- Firebase (BaaS on Google Cloud): No HIPAA Business Associate Agreement available
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: PostgreSQL (88.7)

Open-source relational database with ACID transactions, JSONB, full-text search and extensions (PostGIS, pgvector, TimescaleDB).

Your data is mainly relational and reaches about 280 GB within 12 months; PostgreSQL fits relational data 5/5. You need strong consistency, and PostgreSQL gives it: a read after a write always sees that write. Its share of the estimated bill is $100-$800 a month, against a total budget of $3,000 a month. MySQL is within 0.8 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

Suggested offering: Amazon RDS / Aurora PostgreSQL (+ RDS Proxy for serverless)

**Why**
- Data-model fit: 4.7/5 vs 4.0 average for this layer.
- Consistency fit: 5.0/5 vs 4.7 average for this layer - weighted up because: Strong consistency required; Health records need integrity.
- Ecosystem maturity: 5.0/5 vs 4.8 average for this layer - weighted up because: Clinical systems favour proven tech; 99.95% target.
- Team skill match (4.5/5, direct): your team lists SQL, a direct match for PostgreSQL.
- Default choice for relational data: constraints, joins, transactions
- Extensions cover JSON, search, geo, time-series and vectors
- Every cloud offers it managed; zero vendor lock-in

**Trade-offs**
- Single-writer primary: write scale-out needs sharding (Citus) or Aurora Limitless
- Connection-per-process model needs PgBouncer/RDS Proxy under serverless

**Versus runner-up:** PostgreSQL and MySQL are within 0.8 stack points of each other, inside the 1-point tie margin, so they count as tied. PostgreSQL is stronger on data-model fit (4.7 vs 4.3), realtime fit (3.0 vs 2.0). PostgreSQL has the higher stack score. Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +49.6
- Team skills: +9.8
- Application type: +9.0
- Consistency need: +6.8
- Availability target: +3.9
- Compliance: +2.2

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.7 | 5.0 | 20.6 |
| Consistency fit | 5.0 | 3.5 | 15.8 |
| Ecosystem maturity | 5.0 | 3.0 | 13.5 |
| Team skill match | 4.5 | 2.5 | 9.8 |
| Scalability | 4.0 | 2.0 | 6.8 |
| Low ops burden | 4.0 | 1.5 | 5.1 |
| Cost at your scale | 4.8 | 1.0 | 4.3 |
| Performance / latency | 4.0 | 1.0 | 3.4 |
| Realtime fit | 3.0 | 1.2 | 2.7 |
| Learning curve | 5.0 | 0.5 | 2.2 |
| Hiring pool | 5.0 | 0.5 | 2.2 |
| Portability (low lock-in) | 5.0 | 0.5 | 2.2 |

**Alternatives**
- MySQL (stack 87.8, -0.8): Scores 85.5 on its own; its stack is 0.8 stack points behind the pick.
- Microsoft SQL Server / Azure SQL Database (stack 87.3, -1.3): Scores 83.6 on its own; its stack is 1.3 stack points behind the pick.

**Why not the others?**
- Why not MySQL? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.8 points lower; either is defensible. PostgreSQL is stronger on data-model fit (4.7 vs 4.3), realtime fit (3.0 vs 2.0).
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 7.6 points. PostgreSQL is stronger on data-model fit (4.7 vs 3.0), consistency fit (5.0 vs 3.5); MongoDB is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 3.0); MongoDB takes a penalty: Only 2/5 fit for your primary 'relational' data.

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5)
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~280 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: not the system of record for HIPAA data (use it beside a durable store)
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (2/5)
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational, document data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational, document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.95% availability
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: AWS ECS on Fargate (93.0)

Serverless containers on AWS: no nodes to manage, integrates with ALB, RDS, IAM, CloudWatch.

AWS ECS on Fargate hosts the stack for users in North America at a 99.95% availability target. It runs the Python + Django API as long-running processes with WebSockets, sized for ~69 requests/s at peak. Under HIPAA it can sign a Business Associate Agreement. Its share of the estimated bill is $240-$800 a month, against a total budget of $3,000 a month. It leads the runner-up, Azure App Service / Container Apps, by 3.0 stack points.

Runs here: the Python + Django API as long-running processes. React SPA is built to static files that are served from Amazon S3 + CloudFront, not from these instances (see Supporting services). The database runs as a separate managed service (see Database).

**Why**
- Realtime fit: 4.0/5 vs 3.4 average for this layer - weighted up because: Some realtime features.
- Ecosystem maturity: 5.0/5 vs 4.8 average for this layer - weighted up because: Clinical systems favour proven tech; 99.95% target.
- Performance / latency: 4.0/5 vs 3.8 average for this layer - weighted up because: p95 target 300 ms.
- Bonus +3.5: Your team already operates AWS (listed in team skills).
- Team skill match (5.0/5, direct): your team lists AWS, Docker, a direct match for AWS ECS on Fargate.
- HIPAA-eligible: AWS signs a BAA
- Containers without Kubernetes complexity

**Trade-offs**
- AWS networking/IAM learning curve
- ALB + NAT gateway base costs even when idle

**Versus runner-up:** AWS ECS on Fargate beats Azure App Service / Container Apps by 3.0 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team skills (+3.4). Azure App Service / Container Apps is stronger on team size (+0.2), general quality (baseline weights) (+0.2).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +37.7
- Team skills: +19.9
- Compliance: +9.9
- Availability target: +6.6
- Application type: +6.6
- Realtime needs: +4.9

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Ecosystem maturity | 5.0 | 3.0 | 19.7 |
| Team skill match | 5.0 | 2.5 | 16.4 |
| Scalability | 5.0 | 2.0 | 13.2 |
| Region coverage | 5.0 | 1.0 | 6.6 |
| Compliance maturity (audit, isolation) | 5.0 | 1.0 | 6.6 |
| Cost at your scale | 4.8 | 1.0 | 6.3 |
| Realtime fit | 4.0 | 1.2 | 5.9 |
| Low ops burden | 3.0 | 1.5 | 4.9 |
| Performance / latency | 4.0 | 1.0 | 4.9 |
| Learning curve | 5.0 | 0.5 | 3.3 |
| Portability (low lock-in) | 3.0 | 0.5 | 1.6 |
| Adjustment: Your team already operates AWS (listed in team skills) | | | +3.5 |

**Alternatives**
- Azure App Service / Container Apps (stack 85.5, -3.0): Scores 80.9 on its own; its stack is 3.0 stack points behind the pick.
- AWS EKS (Kubernetes) (stack 85.0, -3.6): Scores 78.7 on its own; its stack is 3.6 stack points behind the pick.

**Why not the others?**
- Why not Azure App Service / Container Apps? (runner-up) Swapping it in lowers the stack score by 3.0 points. AWS ECS on Fargate is stronger on team skill match (5.0 vs 2.5), learning curve (5.0 vs 4.0); Azure App Service / Container Apps is stronger on low ops burden (4.0 vs 3.0).
- Why not Vercel? (popular choice) Ruled out for your answers: No published SLA, so nothing backs your 99.95% availability target.
- Why not Render? (popular choice) Ruled out for your answers: No published SLA, so nothing backs your 99.95% availability target.

**Excluded by hard constraints**
- Vercel: No published SLA, so nothing backs your 99.95% availability target
- Netlify: No HIPAA Business Associate Agreement available; No published SLA, so nothing backs your 99.95% availability target
- Cloudflare Pages + Workers: No HIPAA Business Associate Agreement available; No published SLA, so nothing backs your 99.95% availability target
- Render: No published SLA, so nothing backs your 99.95% availability target
- Railway: No HIPAA Business Associate Agreement available; No published SLA, so nothing backs your 99.95% availability target
- Fly.io: No published SLA, so nothing backs your 99.95% availability target
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay; The provider's SLA is 99.9% (CloudFront distribution), below your 99.95% availability target
- Google Kubernetes Engine (Autopilot): The provider's SLA is 99.9% (Autopilot Pods in multiple zones (the control plane is 99.95%)), below your 99.95% availability target
- DigitalOcean (App Platform + Managed DBs): No HIPAA Business Associate Agreement available
- Hetzner Cloud / VPS (Docker, Coolify): The provider's SLA is 99.9% (each Cloud Server), below your 99.95% availability target; No HIPAA Business Associate Agreement available; No SOC 2 report available
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud; Docker Compose runs an app's containers on one Docker host and restarts them only on that host; placing and moving containers across several hosts is what Swarm or Kubernetes add: no automatic failover to a second host, so it cannot meet 99.95% availability
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud

## Supporting services

- **Background jobs**: Celery / RQ / Dramatiq (Redis/Valkey broker): Send emails, process uploads and call slow APIs outside the request path. Celery with a Redis broker (or RQ / Dramatiq) keeps its jobs in Redis, so the app needs a Redis/Valkey instance (ElastiCache (Valkey)).
- **Static frontend**: Amazon S3 + CloudFront: React SPA is built to static files (HTML, JavaScript, CSS): a bucket behind the cloud's CDN serves them from the edge, so the Python + Django instances on AWS ECS on Fargate only answer API calls, and a frontend release is an upload plus a cache invalidation.
- **Object storage**: Amazon S3 (a separate bucket for uploaded files, served through the same CloudFront as the static frontend): Media and documents belong in object storage, not the database.
- **Authentication**: Amazon Cognito (HIPAA-eligible): Do not hand-roll password storage, MFA or SSO.
- **Push notifications**: Firebase Cloud Messaging (+ APNs) or Expo Notifications: Standard channel for mobile engagement on Android and iOS. Push services are not covered by a BAA: put no health information in the notification text (e.g. 'You have a new message') and show the content only after the user signs in.
- **Observability**: OpenTelemetry instrumentation -> CloudWatch + X-Ray: Traces, metrics and error tracking from day one; required to defend an availability target.
- **Audit & security**: Encrypted storage (KMS), audit logging, least-privilege IAM, WAF: The HIPAA Security Rule requires access controls, audit trails and encryption.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: AWS ECS on Fargate | 240 | 800 | Medium (10k-100k daily users) price band; x2 for 99.95% availability (redundant instances) |
| Database: PostgreSQL | 100 | 800 | Medium (100 GB-1 TB of data) database tier (~280 GB in 12 months); priced as Amazon RDS / Aurora PostgreSQL (+ RDS Proxy for serverless): HIPAA needs a plan whose vendor signs a BAA, which no free or entry plan of this database does; x2 for 99.95% availability (standby/replicas) |
| Background jobs: Redis / Valkey | 30 | 200 | Medium (10k-100k daily users) price band (the app's scale) |
| Static frontend: AWS S3 + CloudFront (static) | 0 | 15 | Medium (10k-100k daily users) price band (the app's scale) |
| **Total** | **370** | **1,815** | |

About ₹35,520-₹174,240 per month. Budget status: **within**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Realtime becomes core**: backend: Python + Django -> Python + FastAPI
  - Why backend changes: Realtime fit moved the gap 2.5 points toward Python + FastAPI (Python + FastAPI 3.0/5 vs Python + Django 2.0/5, weight 1.2 -> 3.2).
- **SEO becomes critical**: frontend: React SPA (Vite) -> Next.js (React)
  - Why frontend changes: React SPA (Vite) now takes a penalty (Client-side rendering is a liability when organic search is the business), moving the gap 18.0 points toward Next.js (React); SEO moved the gap 17.7 points toward Next.js (React) (Next.js (React) 5.0/5 vs React SPA (Vite) 2.0/5, weight 0.2 -> 4.2).
- **Must run on-premises**: hosting: AWS ECS on Fargate -> On-prem Kubernetes (k3s / RKE2 / OpenShift)
  - Why hosting changes: AWS ECS on Fargate is now ruled out: Public-cloud service; deployment must be on-premises.
- **Team has no relevant prior skills**: backend: Python + Django -> Node.js + Express; hosting: AWS ECS on Fargate -> Azure App Service / Container Apps
  - Why backend changes: Python + Django lost a bonus (Your team already ships Python + Django (python listed in team skills)), moving the gap 6.0 points toward Node.js + Express; hiring pool moved the gap 3.9 points toward Node.js + Express (Node.js + Express 5.0/5 vs Python + Django 4.0/5, weight 0.5 -> 3.0).
  - Why hosting changes: Team skill match moved the gap 10.3 points toward Azure App Service / Container Apps (Azure App Service / Container Apps 3.0/5 vs AWS ECS on Fargate 3.0/5, weight 2.5 -> 0.0, was 2.5 vs 5.0).

## Next-best complete stacks

- React SPA (Vite) + Python + FastAPI + PostgreSQL + AWS ECS on Fargate (88.0, -0.6)
- React SPA (Vite) + Python + Django + MySQL + AWS ECS on Fargate (87.8, -0.8)
- React SPA (Vite) + Node.js + Express + PostgreSQL + AWS ECS on Fargate (87.5, -1.1)

## Sources

- https://react.dev
- https://vite.dev/guide/
- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- https://docs.djangoproject.com/
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- https://channels.readthedocs.io/
- https://www.postgresql.org/docs/current/
- https://github.com/pgvector/pgvector
- https://www.citusdata.com/
- https://www.pgbouncer.org/
- https://supabase.com/pricing
- https://neon.com/docs/introduction/plans
- https://aiven.io/pricing/postgresql
- https://supabase.com/docs/guides/platform/compute-and-disk
- https://neon.com/pricing
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
- https://aws.amazon.com/fargate/pricing/
- https://aws.amazon.com/compliance/hipaa-eligible-services-reference/
- https://aws.amazon.com/compliance/pci-dss-level-1-faqs/
- https://aws.amazon.com/ecs/sla/
