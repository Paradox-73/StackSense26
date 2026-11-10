# StackSense recommendation: Impossible Inc.

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Healthcare / telehealth' project at Hyperscale (>10M daily users) scale (~34,722 peak req/s) built by 1 engineer(s) in 2 weeks, StackSense recommends Next.js (React) + Node.js + Express + PostgreSQL + Azure App Service / Container Apps (architecture: Modular monolith). Estimated infrastructure cost: ₹8,544,000-₹31,680,000/month (over budget). 2 critical issue(s) need attention: HIPAA on a free-tier budget; Budget below estimated cost.

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Next.js (React)** | 81.7 | 1.1, close call (under 1.5) | SvelteKit (-1.1) |
| Backend | **Node.js + Express** | 84.7 | 0.6, close call (under 1.5) | C# + ASP.NET Core (-0.6, tie) |
| Database | **PostgreSQL** | 8.7 | 0.5, close call (under 1.5) | MySQL (-0.5, tie) |
| Hosting | **Azure App Service / Container Apps** | 23.9 | 2.4, solid (1.5-4 points) | AWS ECS on Fargate (-2.4) |

Stack score: **51.2** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Modular monolith**: With 1 engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later. (Your preference 'microservices' was overridden; see warnings.) Sized for ~34,722 requests/s at peak, about 11,000 GB of data within 12 months and a 99.99% availability target.

Availability approach: Multi-AZ everywhere + multi-region failover drills, 24x7 on-call

### How the parts fit

1. **Request path**: The browser loads Next.js (React) from Azure App Service / Container Apps; it sends API calls to the Node.js + Express service on Azure App Service / Container Apps (~34,722 requests/s at peak), which queries PostgreSQL.
2. **Sign-in**: Sign-in uses Microsoft Entra External ID; the Node.js + Express API checks the session or token on every request.
3. **Data**: PostgreSQL is the system of record (about 11,000 GB within 12 months); uploaded files go to Blob Storage + Front Door. PHI (protected health information) stays in the database and object storage, encrypted at rest, on services covered by a signed BAA; keep it out of logs, analytics and push notification text. Every store above is placed in the region your residency rule requires.
4. **Deploy**: CI builds a container image and rolls it out on Azure App Service / Container Apps with health checks and zero-downtime restarts. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Hyperscale (>10M daily users) (peak ~34,722 req/s, max(provided, derived)); database tier: Hyperscale (>10M daily users) (~11,000 GB in 12 months)
- Budget: ~$0/month (INR converted at a fixed planning rate of 96 INR = 1 USD (FBIL reference rate, Sep 2026).)
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Warnings and how they were resolved

- **[WARNING] Peak RPS inconsistent with DAU**: You entered 5 req/s but 10,000,000 DAU of a 'healthcare' app implies about 34,722 req/s (60 req/user/day, peak x5). *Resolution:* Planned for the larger figure (34,722 req/s), the safer choice for capacity.
- **[WARNING] Microservices with 1 engineer(s)**: Microservices pay off when several teams need independent deploys; with a small team they multiply deploy pipelines, network failure modes and on-call load (Fowler, 'MonolithFirst'). *Resolution:* Recommending a modular monolith with clear module boundaries that can be split later.
- **[CRITICAL] HIPAA on a free-tier budget**: HIPAA requires a signed Business Associate Agreement (BAA); vendors offer BAAs only on paid plans or eligible paid services. *Resolution:* Compliance is kept as a hard filter; the budget is treated as soft and the real minimum cost is shown.
- **[WARNING] 99.99% availability with 1 engineer(s)**: 99.99% allows ~4.4 minutes of downtime a month; that needs 24x7 on-call and multi-AZ/multi-region failover. A sustainable on-call rotation needs about 6 people; 1 cannot staff it. *Resolution:* Weighted towards fully managed services; consider 99.9% as a realistic SLO.
- **[WARNING] 99.99% availability with a zero budget**: Your budget is ₹0/month, but the cheapest stack that meets your requirements costs about ₹8,544,000/month (see Cost). Only free plans fit a zero budget, and free plans carry no uptime guarantee (no SLA); many pause or throttle idle projects. *Resolution:* Budget for the paid plans in the estimate to get a written SLA, or treat the target as a goal.
- **[WARNING] Compliance on a very short timeline**: BAAs, risk assessments, audit logging and access reviews typically take longer than a few weeks. *Resolution:* Recommending managed, pre-certified services to shorten the path.
- **[WARNING] 20 ms target across regions**: Light in fibre needs roughly 70+ ms for an intercontinental round trip; a single origin cannot meet this globally. *Resolution:* Favouring edge/multi-region platforms; treat the target as per-region latency.
- **[WARNING] Very large scale with a tiny team**: Hyperscale (>10M daily users) traffic is usually run by dedicated platform engineers. *Resolution:* Strongly favouring managed/serverless services with low ops burden.
- **[CRITICAL] Budget below estimated cost**: Estimated minimum spend ₹8,544,000/month exceeds your budget of ₹0/month at Hyperscale (>10M daily users) scale. *Resolution:* No feasible combination fits: the cheapest compliant hosting + database alone costs about ₹2,400,000/month. Cost was weighted up; the stack shown is the cheapest that still meets the hard constraints. Raise the budget or reduce scale/compliance scope.
- **[WARNING] 11 TB on one PostgreSQL primary**: PostgreSQL writes through one primary server; at ~11,000 GB within 12 months, backups, restores, index builds and vacuum take hours, and managed instances stop at 64 TiB (Amazon RDS: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Storage.html). *Resolution:* Plan sharding before you need it: pick a shard key (tenant or customer id), then use Citus for PostgreSQL (https://docs.citusdata.com/en/stable/get_started/what_is_citus.html) or Vitess for MySQL (https://vitess.io/docs/overview/), or a distributed SQL database (CockroachDB, YugabyteDB, Spanner; not scored by StackSense). Move old rows to cheaper storage if they are rarely read.

## Per-layer reasoning

### Frontend: Next.js (React) (81.7)

React meta-framework with server rendering, static generation, React Server Components and file-based routing.

Next.js (React) is the frontend for a Healthcare / telehealth project with about 10,000,000 daily users (~34,722 requests/s at peak), built by a solo developer in 2 weeks. Search visibility is marked critical (organic traffic is the business), and it serves full HTML from the server or the build (SEO 5.0/5), so crawlers read the content without running JavaScript. It leads the runner-up, SvelteKit, by 1.1 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Hiring pool: 5.0/5 vs 3.6 average for this layer - weighted up because: No team skills listed: you will hire for this stack, so the hiring pool counts.
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer - weighted up because: 99.99% target; Clinical systems favour proven tech.
- Development speed: 5.0/5 vs 4.0 average for this layer - weighted up because: 2-week MVP: speed dominates.
- Stack synergy (+6): One language across the stack: shared types, shared validation, any developer can work on any layer.
- SSR/SSG/ISR give crawlers full HTML (strong SEO, fast LCP)
- Largest React ecosystem and hiring pool
- Same codebase can host API routes / server actions for small apps

**Trade-offs**
- App Router + Server Components add conceptual load
- Some features (ISR, image optimisation, middleware) are smoothest on Vercel

**Versus runner-up:** Next.js (React) beats SvelteKit by 1.1 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team skills (+1.0), general quality (baseline weights) (+0.5), application type (+0.4). SvelteKit is stronger on latency target (+0.5), lock-in tolerance (+0.4). Close call: either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +15.9
- SEO need: +12.2
- Realtime needs: +8.8
- Time to MVP: +8.4
- Team skills: +7.7
- Team size: +7.3

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| SEO | 5.0 | 4.2 | 12.8 |
| Ecosystem maturity | 5.0 | 3.5 | 10.7 |
| Performance / latency | 4.0 | 4.5 | 10.3 |
| Low ops burden | 4.0 | 4.0 | 9.2 |
| Development speed | 5.0 | 3.0 | 9.2 |
| Hiring pool | 5.0 | 3.0 | 9.2 |
| Portability (low lock-in) | 4.0 | 2.5 | 5.7 |
| Realtime fit | 3.0 | 3.2 | 4.9 |
| Learning curve | 3.0 | 3.0 | 4.6 |
| Rich client interactivity | 5.0 | 1.5 | 4.6 |
| Structure for large teams | 3.0 | 0.3 | 0.5 |

**Alternatives**
- SvelteKit (stack 50.1, -1.1): Scores 77.1 on its own; its stack is 1.1 stack points behind the pick.
- Nuxt (Vue) (stack 49.9, -1.3): Scores 76.3 on its own; its stack is 1.3 stack points behind the pick.

**Why not the others?**
- Why not SvelteKit? (runner-up) Swapping it in lowers the stack score by 1.1 points. Next.js (React) is stronger on ecosystem maturity (5.0 vs 3.0), hiring pool (5.0 vs 3.0); SvelteKit is stronger on performance / latency (5.0 vs 4.0), learning curve (4.0 vs 3.0).
- Why not React SPA (Vite)? (popular choice) Swapping it in lowers the stack score by 4.6 points. Next.js (React) is stronger on SEO (5.0 vs 2.0), performance / latency (4.0 vs 3.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), learning curve (4.0 vs 3.0); React SPA (Vite) takes a penalty: Client-side rendering is a liability when organic search is the business.

**Excluded by hard constraints**
- React Native (Expo): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Flutter: Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Native iOS + Android (Swift / Kotlin): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)

### Backend: Node.js + Express (84.7)

Minimal, unopinionated HTTP framework on Node.js.

Node.js + Express serves the API at about 34,722 requests/s at peak (Hyperscale (>10M daily users)) for a solo developer. It runs as a long-running Node.js service, so background jobs, WebSockets and database connection pools live in one deployable process. Realtime is core, and it scores 4.0/5 on realtime fit. C# + ASP.NET Core is within 0.6 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

**Why**
- Hiring pool: 5.0/5 vs 3.6 average for this layer - weighted up because: No team skills listed: you will hire for this stack, so the hiring pool counts.
- Learning curve: 5.0/5 vs 3.7 average for this layer - weighted up because: 2-week MVP: no time to learn new tools; Solo developer.
- Realtime fit: 4.0/5 vs 3.3 average for this layer - weighted up because: Realtime is core to the product.
- Stack synergy (+6): One language across the stack: shared types, shared validation, any developer can work on any layer.
- Same language as the frontend (full-stack TypeScript)
- Largest npm ecosystem; Socket.IO for realtime
- Runs anywhere: containers, PaaS, functions

**Trade-offs**
- No structure: large codebases drift without conventions
- CPU-heavy work blocks the event loop

**Versus runner-up:** Node.js + Express and C# + ASP.NET Core are within 0.6 stack points of each other, inside the 1-point tie margin, so they count as tied. Node.js + Express is stronger on learning curve (5.0 vs 3.0), hiring pool (5.0 vs 4.0); C# + ASP.NET Core is stronger on performance / latency (5.0 vs 3.0), scalability (5.0 vs 4.0). Choose C# + ASP.NET Core instead if raw speed matters more to you than a gentler learning curve. The tie went to Node.js + Express on hiring pool (18 vs 17, summed across layers). Either is defensible.

**Inputs that drove this score** (points out of 100)
- Scale (DAU / peak RPS): +15.1
- General quality (baseline weights): +14.8
- Monthly budget: +9.6
- Time to MVP: +7.2
- Team size: +6.9
- Realtime needs: +6.0

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 5.0 | 12.1 |
| Compliance maturity (audit, isolation) | 5.0 | 4.5 | 10.8 |
| Scalability | 4.0 | 5.0 | 9.0 |
| Ecosystem maturity | 5.0 | 3.5 | 8.4 |
| Learning curve | 5.0 | 3.0 | 7.2 |
| Low ops burden | 4.0 | 4.0 | 7.2 |
| Hiring pool | 5.0 | 3.0 | 7.2 |
| Portability (low lock-in) | 5.0 | 2.5 | 6.0 |
| Realtime fit | 4.0 | 3.2 | 5.8 |
| Performance / latency | 3.0 | 4.5 | 5.4 |
| Development speed | 4.0 | 3.0 | 5.4 |
| Structure for large teams | 1.0 | 0.3 | 0.0 |

**Alternatives**
- C# + ASP.NET Core (stack 50.7, -0.6): Loses: One language across the stack: shared types, shared validation, any developer can work on any layer.
- Go (net/http, chi or Gin) (stack 49.7, -1.5): Loses: One language across the stack: shared types, shared validation, any developer can work on any layer.

**Why not the others?**
- Why not C# + ASP.NET Core? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.6 points lower; either is defensible. Node.js + Express is stronger on learning curve (5.0 vs 3.0), hiring pool (5.0 vs 4.0); C# + ASP.NET Core is stronger on performance / latency (5.0 vs 3.0), scalability (5.0 vs 4.0).
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 2.8 points. Node.js + Express is stronger on realtime fit (4.0 vs 2.0), hiring pool (5.0 vs 4.0); Python + Django is stronger on development speed (5.0 vs 4.0), structure for large teams (4.0 vs 1.0).
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 2.8 points. Node.js + Express is stronger on learning curve (5.0 vs 2.0), low ops burden (4.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on scalability (5.0 vs 4.0), performance / latency (4.0 vs 3.0).

**Excluded by hard constraints**
- Firebase (BaaS on Google Cloud): No HIPAA Business Associate Agreement available; Proprietary API with the highest lock-in; you asked for low lock-in
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: PostgreSQL (8.7)

Open-source relational database with ACID transactions, JSONB, full-text search and extensions (PostGIS, pgvector, TimescaleDB).

Your data is mainly relational and reaches about 11,000 GB within 12 months; PostgreSQL fits relational data 5/5. You need strong consistency, and PostgreSQL gives it: a read after a write always sees that write. Its share of the estimated bill is ₹4,320,000-₹8,640,000 a month, against a total budget of ₹0 a month. MySQL is within 0.5 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

Suggested offering: Azure Database for PostgreSQL Flexible Server

**Why**
- Data-model fit: 5.0/5 vs 4.2 average for this layer.
- Portability (low lock-in): 5.0/5 vs 4.2 average for this layer - weighted up because: Low lock-in tolerance.
- Hiring pool: 5.0/5 vs 4.4 average for this layer - weighted up because: No team skills listed: you will hire for this stack, so the hiring pool counts.
- Default choice for relational data: constraints, joins, transactions
- Extensions cover JSON, search, geo, time-series and vectors
- Every cloud offers it managed; zero vendor lock-in

**Trade-offs**
- Cost at your scale is only 1.0/5 (weight 5.0).
- Single-writer primary: write scale-out needs sharding (Citus) or Aurora Limitless
- Connection-per-process model needs PgBouncer/RDS Proxy under serverless

**Risks**
- Near its practical scale ceiling at your traffic/data size (needs sharding or re-architecture) (-12).
- No free option at your scale (from ~$15,000/month) (-53.9).
- PostgreSQL has one writable primary: across regions at 99.99% with strong consistency, a region failover loses or delays writes. If writes must survive a region outage, evaluate a distributed SQL database (Google Spanner, CockroachDB or YugabyteDB; not scored by StackSense).

**Versus runner-up:** PostgreSQL and MySQL are within 0.5 stack points of each other, inside the 1-point tie margin, so they count as tied. PostgreSQL is stronger on realtime fit (3.0 vs 2.0). PostgreSQL has the higher stack score. Either is defensible.

**Inputs that drove this score** (points out of 100)
- Monthly budget: -53.9
- General quality (baseline weights): +24.5
- Team size: +6.2
- Team skills: +5.9
- Availability target: +5.0
- Scale (DAU / peak RPS): -4.9

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 5.0 | 5.0 | 11.8 |
| Scalability | 4.0 | 5.0 | 8.9 |
| Ecosystem maturity | 5.0 | 3.5 | 8.3 |
| Consistency fit | 5.0 | 3.5 | 8.3 |
| Performance / latency | 4.0 | 4.5 | 8.0 |
| Low ops burden | 4.0 | 4.0 | 7.1 |
| Hiring pool | 5.0 | 3.0 | 7.1 |
| Portability (low lock-in) | 5.0 | 2.5 | 5.9 |
| Learning curve | 4.0 | 3.0 | 5.3 |
| Realtime fit | 3.0 | 3.2 | 3.8 |
| Cost at your scale | 1.0 | 5.0 | 0.0 |
| Adjustment: Near its practical scale ceiling at your traffic/data size (needs sharding or re-architecture) | | | -12.0 |
| Adjustment: No free option at your scale (from ~$15,000/month) | | | -53.9 |

**Alternatives**
- MySQL (stack 50.8, -0.5): Scores 6.8 on its own; its stack is 0.5 stack points behind the pick.
- Microsoft SQL Server / Azure SQL Database (stack 49.0, -2.2): Scores 0.0 on its own; its stack is 2.2 stack points behind the pick.

**Why not the others?**
- Why not MySQL? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.5 points lower; either is defensible. PostgreSQL is stronger on realtime fit (3.0 vs 2.0); MySQL takes a penalty: Near its practical scale ceiling at your traffic/data size (needs sharding or re-architecture).
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 2.2 points. PostgreSQL is stronger on data-model fit (5.0 vs 2.0), consistency fit (5.0 vs 3.5); MongoDB is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 3.0); MongoDB takes a penalty: No free option at your scale (from ~$20,000/month).

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5); Proprietary API with the highest lock-in; you asked for low lock-in
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~11,000 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: not the system of record for HIPAA data (use it beside a durable store)
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store; Scale ceiling far below Hyperscale (>10M daily users)
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.99% availability; One writer at a time for the whole file: 600.0M+ requests a day at Hyperscale (>10M daily users) is past the 1M a day SQLite's own guide says it has been shown to handle; Scale ceiling far below Hyperscale (>10M daily users)
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5); Proprietary API with the highest lock-in; you asked for low lock-in
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: Azure App Service / Container Apps (23.9)

Microsoft's managed web hosting and serverless containers, integrated with Entra ID and Azure SQL/Postgres.

Azure App Service / Container Apps hosts the stack for users in North America and India at a 99.99% availability target. It runs the Node.js + Express API as long-running processes with WebSockets, sized for ~34,722 requests/s at peak. Under HIPAA it can sign a Business Associate Agreement. Its share of the estimated bill is ₹3,456,000-₹20,160,000 a month, against a total budget of ₹0 a month. It leads the runner-up, AWS ECS on Fargate, by 2.4 stack points.

Runs here: Next.js (server rendering + static files), the Node.js + Express API as long-running processes. The database runs as a separate managed service (see Database).

**Why**
- Low ops burden: 4.0/5 vs 3.2 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product; 99.99% target.
- Learning curve: 4.0/5 vs 3.2 average for this layer - weighted up because: 2-week MVP: no time to learn new tools; Solo developer.
- Compliance maturity (audit, isolation): 5.0/5 vs 4.5 average for this layer - weighted up because: HIPAA at Hyperscale (>10M daily users): auditors expect dedicated tenancy and immutable audit trails; HIPAA at Hyperscale (>10M daily users): more records in scope and larger breach impact.
- Bonus +2: Simple long-running deploy suits a monolith.
- Natural home for .NET and Microsoft-centric enterprises
- Three India regions
- Broad compliance portfolio

**Trade-offs**
- Cost at your scale is only 1.0/5 (weight 5.0).
- Portal/config complexity; pricing tiers are confusing

**Risks**
- No free option at your scale (from ~$12,000/month) (-52.5).

**Versus runner-up:** Azure App Service / Container Apps beats AWS ECS on Fargate by 2.4 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team size (+2.1), general quality (baseline weights) (+0.2), time to mvp (+0.2). AWS ECS on Fargate is stronger on monthly budget (+0.3).

**Inputs that drove this score** (points out of 100)
- Monthly budget: -52.5
- Scale (DAU / peak RPS): +18.7
- General quality (baseline weights): +12.7
- Latency target: +7.4
- Team size: +6.8
- Realtime needs: +6.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Scalability | 5.0 | 5.0 | 12.9 |
| Compliance maturity (audit, isolation) | 5.0 | 4.5 | 11.6 |
| Ecosystem maturity | 5.0 | 3.5 | 9.0 |
| Region coverage | 5.0 | 3.5 | 9.0 |
| Performance / latency | 4.0 | 4.5 | 8.7 |
| Low ops burden | 4.0 | 4.0 | 7.8 |
| Realtime fit | 4.0 | 3.2 | 6.2 |
| Learning curve | 4.0 | 3.0 | 5.8 |
| Portability (low lock-in) | 3.0 | 2.5 | 3.2 |
| Cost at your scale | 1.0 | 5.0 | 0.0 |
| Adjustment: Simple long-running deploy suits a monolith | | | +2.0 |
| Adjustment: No free option at your scale (from ~$12,000/month) | | | -52.5 |

**Alternatives**
- AWS ECS on Fargate (stack 48.9, -2.4): Scores 14.4 on its own; its stack is 2.4 stack points behind the pick.
- AWS EKS (Kubernetes) (stack 45.3, -6.0): Scores 0.0 on its own; its stack is 6.0 stack points behind the pick.

**Why not the others?**
- Why not AWS ECS on Fargate? (runner-up) Swapping it in lowers the stack score by 2.4 points. Azure App Service / Container Apps is stronger on low ops burden (4.0 vs 3.0), learning curve (4.0 vs 3.0); AWS ECS on Fargate takes a penalty: Usually needs a team of 2+ to operate.
- Why not Vercel? (popular choice) Swapping it in lowers the stack score by 7.4 points. Azure App Service / Container Apps is stronger on compliance maturity (audit, isolation) (5.0 vs 3.0), realtime fit (4.0 vs 2.0); Vercel is stronger on performance / latency (5.0 vs 4.0), low ops burden (5.0 vs 4.0); Vercel takes a penalty: No free option at your scale (from ~$12,000/month).
- Why not Render? (popular choice) Ruled out for your answers: No India region; data must stay in India.

**Excluded by hard constraints**
- Netlify: No HIPAA Business Associate Agreement available; No India region; data must stay in India
- Cloudflare Pages + Workers: No HIPAA Business Associate Agreement available; Keeping data and TLS termination inside India or the EU needs the Data Localization Suite, an Enterprise add-on; treated as not meeting a residency rule.
- Render: No India region; data must stay in India
- Railway: No HIPAA Business Associate Agreement available; No India region; data must stay in India; Scale ceiling far below Hyperscale (>10M daily users)
- Fly.io: No India region; data must stay in India
- AWS Lambda + API Gateway: The provider's SLA is 99.95% (per region), below your 99.99% availability target
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay; The provider's SLA is 99.9% (CloudFront distribution), below your 99.99% availability target
- Google Cloud Run: The provider's SLA is 99.95% (Cloud Run services in most regions), below your 99.99% availability target
- Google Kubernetes Engine (Autopilot): The provider's SLA is 99.9% (Autopilot Pods in multiple zones (the control plane is 99.95%)), below your 99.99% availability target
- DigitalOcean (App Platform + Managed DBs): The provider's SLA is 99.95% (each App Platform component), below your 99.99% availability target; No HIPAA Business Associate Agreement available
- Hetzner Cloud / VPS (Docker, Coolify): The provider's SLA is 99.9% (each Cloud Server), below your 99.99% availability target; No HIPAA Business Associate Agreement available; No India region; data must stay in India
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud; Docker Compose runs an app's containers on one Docker host and restarts them only on that host; placing and moving containers across several hosts is what Swarm or Kubernetes add: no automatic failover to a second host, so it cannot meet 99.99% availability; Scale ceiling far below Hyperscale (>10M daily users)
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud

## Stack compatibility checks

- (synergy, +6) One language across the stack: shared types, shared validation, any developer can work on any layer.

## Supporting services

- **Cache**: Redis/Valkey (Azure Cache for Redis): Read-heavy traffic, a tight latency target or hot key-value data: keep hot reads and sessions in memory in front of a durable primary database.
- **Realtime**: Redis pub/sub for cross-instance fan-out (Azure Cache for Redis): With several app instances, a message published on one must reach sockets on all others.
- **Background jobs**: BullMQ (Redis): Send emails, process uploads and call slow APIs outside the request path. BullMQ keeps its jobs in Redis, so the app needs a Redis/Valkey instance (the one already listed above).
- **Object storage**: Blob Storage + Front Door: Media and documents belong in object storage, not the database.
- **Authentication**: Microsoft Entra External ID: Do not hand-roll password storage, MFA or SSO.
- **Observability**: OpenTelemetry instrumentation -> Azure Monitor / App Insights: Traces, metrics and error tracking from day one; required to defend an availability target.
- **Audit & security**: Encrypted storage (KMS), audit logging, least-privilege IAM, WAF: The HIPAA Security Rule requires access controls, audit trails and encryption.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: Azure App Service / Container Apps | 36,000 | 210,000 | Hyperscale (>10M daily users) price band; x3 for 99.99% availability (redundant instances) |
| Database: PostgreSQL | 45,000 | 90,000 | Hyperscale (>10M daily users) database tier (~11,000 GB in 12 months); upper end for ~11,000 GB of data: the band's top is priced for the largest data of the tier; x3 for 99.99% availability (standby/replicas) |
| Cache: Redis / Valkey | 8,000 | 30,000 | Hyperscale (>10M daily users) price band (the app's scale) |
| **Total** | **89,000** | **330,000** | |

About ₹8,544,000-₹31,680,000 per month. Budget status: **over**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **A team of 15 engineers**: backend: Node.js + Express -> C# + ASP.NET Core
  - Why backend changes: Structure for large teams moved the gap 3.6 points toward C# + ASP.NET Core (C# + ASP.NET Core 5.0/5 vs Node.js + Express 1.0/5, weight 0.3 -> 1.8).
- **Must run on-premises**: hosting: Azure App Service / Container Apps -> On-prem Kubernetes (k3s / RKE2 / OpenShift)
  - Why hosting changes: Azure App Service / Container Apps is now ruled out: Public-cloud service; deployment must be on-premises.

## Next-best complete stacks

- Next.js (React) + Node.js + Express + MySQL + Azure App Service / Container Apps (50.8, -0.5)
- Next.js (React) + C# + ASP.NET Core + PostgreSQL + Azure App Service / Container Apps (50.7, -0.6)
- Next.js (React) + C# + ASP.NET Core + MySQL + Azure App Service / Container Apps (50.2, -1.0)

## Sources

- https://nextjs.org/docs
- https://react.dev
- https://survey.stackoverflow.co/2025/technology
- https://web.dev/articles/rendering-on-the-web
- https://nextjs.org/docs/app/getting-started/deploying
- https://expressjs.com/
- https://nodejs.org/en/learn/asynchronous-work/dont-block-the-event-loop
- https://socket.io/docs/v4/
- https://www.postgresql.org/docs/current/
- https://github.com/pgvector/pgvector
- https://www.citusdata.com/
- https://www.pgbouncer.org/
- https://supabase.com/pricing
- https://neon.com/docs/introduction/plans
- https://aiven.io/pricing/postgresql
- https://supabase.com/docs/guides/platform/compute-and-disk
- https://neon.com/pricing
- https://learn.microsoft.com/azure/app-service/overview
- https://learn.microsoft.com/azure/container-apps/overview
- https://learn.microsoft.com/azure/compliance/offerings/offering-hipaa-us
- https://learn.microsoft.com/en-us/azure/app-service/quickstart-php
- https://www.microsoft.com/licensing/docs/view/Service-Level-Agreements-SLA-for-Online-Services
- https://www.typescriptlang.org/docs/
