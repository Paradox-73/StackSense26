# StackSense recommendation: BazaarKart (e-commerce)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For an 'E-commerce / marketplace' project at Very large (1M-10M daily users) scale (~25,000 peak req/s) built by 25 engineer(s) in 26 weeks, StackSense recommends Next.js (React) + Java/Kotlin + Spring Boot + MySQL + AWS EKS (Kubernetes) (architecture: Service-oriented (a few coarse services, one per team)). Estimated infrastructure cost: ₹1,036,800-₹7,491,264/month (stretch budget). The highest-scoring stack (Next.js (React) + Java/Kotlin + Spring Boot + PostgreSQL + AWS EKS (Kubernetes), 93.9) is only 0.3 stack points ahead, inside the 1-point tie margin, so StackSense treats it as a tie and chose this stack on adjacent team skills (19.5 vs 19, summed skill fit).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Next.js (React)** | 86.3 | 1.9, solid (1.5-4 points) | Angular (-1.9) |
| Backend | **Java/Kotlin + Spring Boot** | 97.1 | 3.9, solid (1.5-4 points) | Node.js + NestJS (-3.9) |
| Database | **MySQL** | 85.3 | -0.3, close call (under 1.5) | PostgreSQL (+0.3, tie) |
| Hosting | **AWS EKS (Kubernetes)** | 100.0 | 1.5, solid (1.5-4 points) | AWS ECS on Fargate (-1.5) |
| Mobile app (iOS/Android) | React Native (Expo) | 56.3 | - | - |

Stack score: **93.7** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Service-oriented (a few coarse services, one per team)**: 25 engineers at Very large (1M-10M daily users) benefit from independently deployable services, one per team. Sized for ~25,000 requests/s at peak, about 1,520 GB of data within 12 months and a 99.95% availability target.

Availability approach: Multi-AZ app and database, health checks, zero-downtime deploys

### How the parts fit

1. **Request path**: The browser loads Next.js (React) from AWS EKS (Kubernetes); it sends API calls to the Java/Kotlin + Spring Boot service on AWS EKS (Kubernetes) (~25,000 requests/s at peak), which queries MySQL.
2. **Sign-in**: Sign-in uses Spring Security's one-time token login in your API, with the users in your database in your Indian region: Amazon Cognito would cost about $149,850 a month at ~10,000,000 monthly users; the Java/Kotlin + Spring Boot API checks the session or token on every request.
3. **Data**: MySQL is the system of record (about 1,520 GB within 12 months); uploaded files go to Amazon S3, a private bucket in your required region (short-lived signed URLs, no public CDN). Card and bank details never reach your servers: the payment provider's hosted checkout or SDK collects them, and you store only its tokens. Every store above is placed in the region your residency rule requires.
4. **Deploy**: CI builds container images and rolls them out on AWS EKS (Kubernetes) (manifests or Helm), one service at a time. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Very large (1M-10M daily users) (peak ~25,000 req/s, provided); database tier: Large (1-10 TB of data) (~1,520 GB in 12 months)
- Budget: ~$26,042/month (INR converted at a fixed planning rate of 96 INR = 1 USD (an assumption; check the FBIL reference rate for today's value).)
- Assumption: compliance = dpdp: DPDP Act 2023 (in force through the DPDP Rules 2025, notified November 2025 and phased in over 18 months) allows cross-border transfer except to notified countries, so it adds consent/breach-notice duties but not an India-region filter. Add 'Data must stay in India' if a sector rule (e.g. RBI) applies.
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Warnings and how they were resolved

- **[WARNING] Budget below the top of the estimate**: ₹1,036,800-₹7,491,264/month against ₹2,500,000/month: the top (~3x today's load) and the middle are over, most of the rise in AWS EKS and ClickHouse. *Resolution:* Raise the budget before the load grows.

## Per-layer reasoning

### Frontend: Next.js (React) (86.3)

React meta-framework with server rendering, static generation, React Server Components and file-based routing.

Next.js (React) is the frontend for an E-commerce / marketplace project with about 2,000,000 daily users (~25,000 requests/s at peak), built by a team of 25 in 26 weeks. Search visibility is marked critical (organic traffic is the business), and it serves full HTML from the server or the build (SEO 5.0/5), so crawlers read the content without running JavaScript. It leads the runner-up, Angular, by 1.9 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer - weighted up because: 99.95% target; Regulated workload.
- SEO: 5.0/5 vs 4.4 average for this layer - weighted up because: SEO critical.
- Hiring pool: 5.0/5 vs 3.6 average for this layer - weighted up because: 25 engineers: hiring pool matters.
- Team skill match (4.5/5, direct): your team lists React, a direct match for Next.js (React).
- SSR/SSG/ISR give crawlers full HTML (strong SEO, fast LCP)
- Largest React ecosystem and hiring pool
- Same codebase can host API routes / server actions for small apps

**Trade-offs**
- App Router + Server Components add conceptual load
- Some features (ISR, image optimisation, middleware) are smoothest on Vercel

**Versus runner-up:** Next.js (React) beats Angular by 1.9 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on general quality (baseline weights) (+1.2), seo need (+1.1), team skills (+0.4). Angular is stronger on stack compatibility (+1.0), team size (+0.4).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +24.8
- SEO need: +18.2
- Team size: +11.9
- Team skills: +9.9
- Application type: +8.5
- Scale (DAU / peak RPS): +3.4

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| SEO | 5.0 | 4.2 | 19.1 |
| Team skill match | 4.5 | 3.5 | 13.9 |
| Ecosystem maturity | 5.0 | 2.5 | 11.4 |
| Performance / latency | 4.0 | 2.8 | 9.6 |
| Hiring pool | 5.0 | 1.5 | 6.8 |
| Rich client interactivity | 5.0 | 1.5 | 6.8 |
| Development speed | 5.0 | 1.0 | 4.5 |
| Structure for large teams | 3.0 | 1.8 | 4.1 |
| Low ops burden | 4.0 | 1.0 | 3.4 |
| Realtime fit | 3.0 | 1.2 | 2.7 |
| Learning curve | 5.0 | 0.5 | 2.3 |
| Portability (low lock-in) | 4.0 | 0.5 | 1.7 |

**Alternatives**
- Angular (stack 91.8, -1.9): Note: Same architectural style (modules, DI) on both sides; common in enterprise teams.
- SvelteKit (stack 90.9, -2.8): Scores 75.3 on its own; its stack is 2.8 stack points behind the pick.

**Why not the others?**
- Why not Angular? (runner-up) Swapping it in lowers the stack score by 1.9 points. Next.js (React) is stronger on SEO (5.0 vs 4.0), performance / latency (4.0 vs 3.0); Angular is stronger on structure for large teams (5.0 vs 3.0).
- Why not React SPA (Vite)? (popular choice) Swapping it in lowers the stack score by 7.2 points. Next.js (React) is stronger on SEO (5.0 vs 2.0), performance / latency (4.0 vs 3.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0); React SPA (Vite) takes a penalty: Client-side rendering is a liability when organic search is the business.

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

### Backend: Java/Kotlin + Spring Boot (97.1)

Enterprise JVM framework: DI, Spring Data, Spring Security, transactions, observability.

Java/Kotlin + Spring Boot serves the API at about 25,000 requests/s at peak (Very large (1M-10M daily users)) for a team of 25. The team lists Java and Spring, so it needs no new server language (team skill match 5.0/5). It runs as a few long-running Java/Kotlin services, one per team, each deployed on its own with its own background jobs, WebSockets and database connection pools. It leads the runner-up, Node.js + NestJS, by 3.9 stack points.

**Why**
- Structure for large teams: 5.0/5 vs 3.2 average for this layer - weighted up because: 25 engineers need enforced conventions.
- Scalability: 5.0/5 vs 4.3 average for this layer - weighted up because: Very large (1M-10M daily users); 99.95% target.
- Hiring pool: 5.0/5 vs 3.6 average for this layer - weighted up because: 25 engineers: hiring pool matters.
- Bonus +6: Your team already ships Java/Kotlin + Spring Boot (java, spring listed in team skills).
- Team skill match (5.0/5, direct): your team lists Java, Spring, a direct match for Java/Kotlin + Spring Boot.
- Declarative transactions and Spring Security suit fintech/banking
- Largest enterprise hiring pool (very strong in India)
- Mature observability and resilience libraries

**Trade-offs**
- Higher memory footprint, slow JVM cold starts (mitigated by GraalVM/SnapStart)
- Verbose for small MVPs

**Versus runner-up:** Java/Kotlin + Spring Boot beats Node.js + NestJS by 3.9 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team skills (+1.8), scale (dau / peak rps) (+1.0), team size (+0.4). Node.js + NestJS is stronger on realtime needs (+0.2).

**Inputs that drove this score** (points out of 100)
- Scale (DAU / peak RPS): +28.1
- General quality (baseline weights): +24.3
- Team skills: +15.7
- Team size: +13.6
- Compliance: +5.8
- Availability target: +3.9

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Scalability | 5.0 | 4.5 | 17.4 |
| Compliance maturity (audit, isolation) | 5.0 | 4.5 | 17.4 |
| Team skill match | 5.0 | 3.5 | 13.6 |
| Ecosystem maturity | 5.0 | 2.5 | 9.7 |
| Performance / latency | 4.0 | 2.8 | 8.1 |
| Structure for large teams | 5.0 | 1.8 | 7.0 |
| Hiring pool | 5.0 | 1.5 | 5.8 |
| Realtime fit | 3.0 | 1.2 | 2.3 |
| Cost at your scale | 5.0 | 0.5 | 1.9 |
| Learning curve | 5.0 | 0.5 | 1.9 |
| Low ops burden | 3.0 | 1.0 | 1.9 |
| Development speed | 3.0 | 1.0 | 1.9 |
| Portability (low lock-in) | 5.0 | 0.5 | 1.9 |
| Adjustment: Your team already ships Java/Kotlin + Spring Boot (java, spring listed in team skills) | | | +6.0 |

**Alternatives**
- Node.js + NestJS (stack 89.8, -3.9): Scores 81.5 on its own; its stack is 3.9 stack points behind the pick.
- Go (net/http, chi or Gin) (stack 89.5, -4.2): Scores 80.3 on its own; its stack is 4.2 stack points behind the pick.

**Why not the others?**
- Why not Node.js + NestJS? (runner-up) Swapping it in lowers the stack score by 3.9 points. Java/Kotlin + Spring Boot is stronger on scalability (5.0 vs 4.0), performance / latency (4.0 vs 3.0); Node.js + NestJS is stronger on realtime fit (4.0 vs 3.0), low ops burden (4.0 vs 3.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 4.7 points. Java/Kotlin + Spring Boot is stronger on structure for large teams (5.0 vs 1.0), scalability (5.0 vs 4.0); Node.js + Express is stronger on realtime fit (4.0 vs 3.0), low ops burden (4.0 vs 3.0).
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 8.7 points. Java/Kotlin + Spring Boot is stronger on team skill match (5.0 vs 1.5), scalability (5.0 vs 4.0); Python + Django is stronger on development speed (5.0 vs 3.0), low ops burden (4.0 vs 3.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: MySQL (85.3)

Widely deployed relational database; horizontally shardable with Vitess.

Your data is mainly relational and reaches about 1,520 GB within 12 months; MySQL fits relational data 5/5. You need strong consistency, and MySQL gives it: a read after a write always sees that write. Its share of the estimated bill is ₹76,800-₹793,440 a month, against a total budget of ₹2,500,000 a month. PostgreSQL is within 0.3 stack points, inside the tie margin (stacks this close count as tied); the tie went to MySQL on adjacent team skills (19.5 vs 19, summed skill fit).

Suggested offering: Amazon RDS / Aurora MySQL

**Why**
- Data-model fit: 4.3/5 vs 4.0 average for this layer.
- Hiring pool: 5.0/5 vs 4.4 average for this layer - weighted up because: 25 engineers: hiring pool matters.
- Consistency fit: 5.0/5 vs 4.7 average for this layer - weighted up because: Strong consistency required.
- Team skill match (5.0/5, direct): your team lists mysql, SQL, a direct match for MySQL.
- Huge talent pool and hosting availability (default for PHP/Laravel)
- Vitess path to sharding proven at YouTube/Slack scale
- Read replicas are simple

**Trade-offs**
- Realtime fit is only 2.0/5 (weight 1.2).
- Fewer advanced types and extensions than Postgres
- Weaker JSON and analytical query support

**Versus runner-up:** MySQL and PostgreSQL are within 0.3 stack points of each other, inside the 1-point tie margin, so they count as tied; PostgreSQL is stronger on data-model fit (4.7 vs 4.3), realtime fit (3.0 vs 2.0). Choose PostgreSQL instead if data-model fit matters more to you. The tie went to MySQL on adjacent team skills (19.5 vs 19, summed skill fit). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +40.6
- Scale (DAU / peak RPS): +11.5
- Team skills: +9.6
- Team size: +7.7
- Consistency need: +5.8
- Availability target: +3.4

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.3 | 5.0 | 16.0 |
| Team skill match | 5.0 | 3.5 | 13.5 |
| Scalability | 4.0 | 4.5 | 13.0 |
| Ecosystem maturity | 5.0 | 2.5 | 9.6 |
| Consistency fit | 5.0 | 2.5 | 9.6 |
| Performance / latency | 4.0 | 2.8 | 8.1 |
| Hiring pool | 5.0 | 1.5 | 5.8 |
| Low ops burden | 4.0 | 1.0 | 2.9 |
| Learning curve | 5.0 | 0.5 | 1.9 |
| Portability (low lock-in) | 5.0 | 0.5 | 1.9 |
| Cost at your scale | 4.8 | 0.5 | 1.8 |
| Realtime fit | 2.0 | 1.2 | 1.1 |

**Alternatives**
- PostgreSQL (stack 93.9, +0.3): Scores 86.3 on its own; its stack is 0.3 stack points ahead of the pick.
- Microsoft SQL Server (stack 92.6, -1.0): Scores 81.1 on its own; its stack is 1.0 stack points behind the pick.

**Why not the others?**
- Why not PostgreSQL? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.3 points higher; the tie went to MySQL on adjacent team skills (19.5 vs 19, summed skill fit); either is defensible. MySQL is stronger on team skill match (5.0 vs 4.5); PostgreSQL is stronger on data-model fit (4.7 vs 4.3), realtime fit (3.0 vs 2.0).
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 6.2 points. MySQL is stronger on data-model fit (4.3 vs 3.0), team skill match (5.0 vs 3.5); MongoDB is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 2.0); MongoDB takes a penalty: Only 2/5 fit for your primary 'relational' data.

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5)
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~1,520 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: not the system of record for PCI DSS data (use it beside a durable store)
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (2/5)
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational, document data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational, document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.95% availability; One writer at a time for the whole file: 60.0M+ requests a day at Very large (1M-10M daily users) is past the 1M a day SQLite's own guide says it has been shown to handle
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: AWS EKS (Kubernetes) (100.0)

Managed Kubernetes control plane on AWS.

AWS EKS (Kubernetes) hosts the stack for users in India at a 99.95% availability target. It runs the Java/Kotlin + Spring Boot API as long-running processes with WebSockets, sized for ~25,000 requests/s at peak. For PCI DSS it is a validated service provider, so card-handling infrastructure can sit on it. Its share of the estimated bill is ₹480,000-₹3,272,448 a month, against a total budget of ₹2,500,000 a month. It leads the runner-up, AWS ECS on Fargate, by 1.5 stack points.

Runs here: Next.js (server rendering + static files), the Java/Kotlin + Spring Boot API as long-running processes. The database runs as a separate managed service (see Database).

**Why**
- Realtime fit: 4.0/5 vs 3.4 average for this layer - weighted up because: Some realtime features.
- Performance / latency: 4.0/5 vs 3.8 average for this layer - weighted up because: Very large (1M-10M daily users); p95 target 200 ms.
- Ecosystem maturity: 5.0/5 vs 4.8 average for this layer - weighted up because: 99.95% target; Regulated workload.
- Bonus +12.0: Runs on your preferred cloud (AWS).
- Bonus +3: Container orchestration suits microservices.
- Stack synergy (+6): Kubernetes earns its complexity when running many independently deployed services.
- Team skill match (5.0/5, direct): your team lists AWS, Kubernetes, a direct match for AWS EKS (Kubernetes).
- Portable Kubernetes workloads with the AWS ecosystem
- Fine-grained autoscaling for many services

**Trade-offs**
- Low ops burden is only 1.0/5 (weight 1.0).
- Control-plane fee (~$73/mo) plus nodes
- Needs dedicated platform/DevOps skills

**Versus runner-up:** AWS EKS (Kubernetes) beats AWS ECS on Fargate by 1.5 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+1.5), score limit (scores stop at 0 and 100) (+0.4). AWS ECS on Fargate is stronger on general quality (baseline weights) (+0.4).

**Inputs that drove this score** (points out of 100)
- Scale (DAU / peak RPS): +30.9
- General quality (baseline weights): +22.5
- Cloud preference: +12.0
- Compliance: +10.6
- Team skills: +10.6
- Score limit (scores stop at 0 and 100): -5.7

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Scalability | 5.0 | 4.5 | 19.1 |
| Compliance maturity (audit, isolation) | 5.0 | 4.5 | 19.1 |
| Team skill match | 5.0 | 3.5 | 14.9 |
| Ecosystem maturity | 5.0 | 2.5 | 10.6 |
| Performance / latency | 4.0 | 2.8 | 8.9 |
| Region coverage | 5.0 | 2.0 | 8.5 |
| Realtime fit | 4.0 | 1.2 | 3.8 |
| Learning curve | 5.0 | 0.5 | 2.1 |
| Cost at your scale | 4.6 | 0.5 | 1.9 |
| Portability (low lock-in) | 4.0 | 0.5 | 1.6 |
| Low ops burden | 1.0 | 1.0 | 0.0 |
| Adjustment: Runs on your preferred cloud (AWS) | | | +12.0 |
| Adjustment: Container orchestration suits microservices | | | +3.0 |

**Alternatives**
- AWS ECS on Fargate (stack 92.2, -1.5): Loses: Kubernetes earns its complexity when running many independently deployed services.
- Azure App Service (stack 88.8, -4.9): Loses: Kubernetes earns its complexity when running many independently deployed services.

**Why not the others?**
- Why not AWS ECS on Fargate? (runner-up) Swapping it in lowers the stack score by 1.5 points. AWS EKS (Kubernetes) is stronger on portability (low lock-in) (4.0 vs 3.0); AWS ECS on Fargate is stronger on low ops burden (3.0 vs 1.0). 1.5 of the 1.5 points come from a stack compatibility rule: Kubernetes earns its complexity when running many independently deployed services.
- Why not Vercel? (popular choice) Ruled out for your answers: No published SLA, so nothing backs your 99.95% availability target.
- Why not Render? (popular choice) Ruled out for your answers: No PCI-DSS attestation published.

**Excluded by hard constraints**
- Vercel: No published SLA, so nothing backs your 99.95% availability target
- Netlify: No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- Cloudflare Pages + Workers: Keeping data and TLS termination inside India or the EU needs the Data Localization Suite, an Enterprise add-on; treated as not meeting a residency rule.; No published SLA, so nothing backs your 99.95% availability target
- Render: No PCI-DSS attestation published; No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- Railway: No PCI-DSS attestation published; No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- Fly.io: No PCI-DSS attestation published; No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay
- Firebase Hosting (static): Only for read-only sites; your users sign in, post or pay
- Google Cloud Storage + Cloud CDN (static): Only for read-only sites; your users sign in, post or pay
- Azure Static Web Apps: Only for read-only sites; your users sign in, post or pay; No PCI-DSS attestation published
- Azure Blob Storage + Front Door (static): Only for read-only sites; your users sign in, post or pay; No PCI-DSS attestation published
- Google Kubernetes Engine (Autopilot): The provider's SLA is 99.9% (Autopilot Pods in multiple zones (the control plane is 99.95%)), below your 99.95% availability target
- DigitalOcean (App Platform + Managed DBs): No PCI-DSS attestation published
- Hetzner Cloud / VPS (Docker, Coolify): The provider's SLA is 99.9% (each Cloud Server), below your 99.95% availability target; No PCI-DSS attestation published; No India region; data must stay in India
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud; Docker Compose runs an app's containers on one Docker host and restarts them only on that host; placing and moving containers across several hosts is what Swarm or Kubernetes add: no automatic failover to a second host, so it cannot meet 99.95% availability
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs

## Stack compatibility checks

- (synergy, +6) Kubernetes earns its complexity when running many independently deployed services.

## Supporting services

- **Cache**: Redis/Valkey (ElastiCache (Valkey)): Read-heavy traffic, a tight latency target or hot key-value data: keep hot reads and sessions in memory in front of a durable primary database.
- **Realtime**: WebSockets in the Java/Kotlin + Spring Boot app (Spring WebSocket with STOMP): Chat and live updates for a part of the product: the app server holds the connections itself; add Redis pub/sub only when a second instance must reach the same users.
- **Secondary store (document)**: MongoDB (MongoDB Atlas (runs on AWS, GCP or Azure in the same region as your compute)): Your primary database fits your data less well than MongoDB: 'document' 3/5 against 5/5.
- **Analytics**: ClickHouse Cloud (AWS/GCP/Azure) fed by a continuous copy of database changes: Run heavy aggregations on a columnar store instead of the transactional database.
- **Background jobs**: Amazon SQS with Spring Cloud AWS listeners: Send emails, process uploads and call slow APIs outside the request path.
- **Search**: Amazon OpenSearch Service: Search across ~507 GB of documents (an estimate: the document share of your ~1,520 GB total, from your 2 data shapes) needs an inverted index with relevance ranking, highlighting and filters; database text indexes slow down and rank poorly at this size.
- **Payments**: Razorpay with hosted checkout (card tokens): Card data never touches your servers, which keeps your PCI-DSS audit scope to the smallest self-assessment form (SAQ A). Stripe accepts new businesses in India by invitation only, so an Indian gateway leads.
- **Object storage**: Amazon S3, a private bucket in your required region (short-lived signed URLs, no public CDN): Media and documents belong in object storage, not the database.
- **Authentication**: Spring Security's one-time token login in your API, with the users in your database in your Indian region: Amazon Cognito would cost about $149,850 a month at ~10,000,000 monthly users: Do not hand-roll password storage, MFA or SSO.
- **Push notifications**: Firebase Cloud Messaging (+ APNs): Standard channel for mobile engagement on Android and iOS. Notification text leaves your residency region: Firebase Cloud Messaging may process messages anywhere Google has facilities, so send only an ID and let the app fetch the content from your servers in the region.
- **Observability**: OpenTelemetry instrumentation -> CloudWatch + X-Ray: Traces, metrics and error tracking from day one; required to defend an availability target.
- **Audit & security**: Encrypted storage (KMS), audit logging, least-privilege IAM, WAF: PCI-DSS requires access controls, audit trails and encryption.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: AWS EKS (Kubernetes) | 5,000 | 34,088 | Very large (1M-10M daily users) price band, from the band's floor up to its price at ~3x the load, for 25,000 req/s at peak (70% of the way up the tier, log scale); x2 for 99.95% availability (redundant instances) |
| Database: MySQL | 800 | 8,265 | Large (1-10 TB of data) database tier (~1,520 GB in 12 months), from the band's floor up to its price at ~3x the load, for 25,000 req/s at peak (70% of the way up the tier, log scale); x2 for 99.95% availability (standby/replicas) |
| Cache: Redis / Valkey | 1,500 | 10,407 | Very large (1M-10M daily users) price band (the app's scale), from the band's floor up to its price at ~3x the load, for 25,000 req/s at peak (70% of the way up the tier, log scale) |
| Secondary store (document): MongoDB | 500 | 5,510 | Large (1-10 TB of data) price band (the app's scale), from the band's floor up to its price at ~3x the load, for 25,000 req/s at peak (70% of the way up the tier, log scale) |
| Analytics: ClickHouse | 3,000 | 19,764 | Very large (1M-10M daily users) price band (the app's scale), from the band's floor up to its price at ~3x the load, for 25,000 req/s at peak (70% of the way up the tier, log scale); a copy of data that MySQL also stores (fed by a continuous copy of changes), so that data is paid for in both stores |
| **Total** | **10,800** | **78,034** | |

About ₹1,036,800-₹7,491,264 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, each read where the project sits inside its tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **A solo developer**: hosting: AWS EKS (Kubernetes) -> AWS ECS on Fargate
  - Why hosting changes: AWS EKS (Kubernetes) now takes a penalty (Usually needs a team of 4+ to operate), moving the gap 14.0 points toward AWS ECS on Fargate; low ops burden moved the gap 4.6 points toward AWS ECS on Fargate (AWS ECS on Fargate 3.0/5 vs AWS EKS (Kubernetes) 1.0/5, weight 1.0 -> 3.5).
- **4-week deadline**: frontend: Next.js (React) -> React Native (Expo)
  - Why frontend changes: Next.js (React) is now ruled out: Does not build android, ios: the timeline leaves room for one codebase that builds every platform.
- **Must run on-premises**: hosting: AWS EKS (Kubernetes) -> On-prem Kubernetes (k3s / RKE2 / OpenShift)
  - Why hosting changes: AWS EKS (Kubernetes) is now ruled out: Public-cloud service; deployment must be on-premises.
- **Team has no relevant prior skills**: database: MySQL -> PostgreSQL
  - Why database changes: Team skill match moved the gap 1.7 points toward PostgreSQL (PostgreSQL 3.0/5 vs MySQL 3.0/5, weight 3.5 -> 0.0, was 4.5 vs 5.0).

## Next-best complete stacks

- Next.js (React) + Java/Kotlin + Spring Boot + PostgreSQL + AWS EKS (Kubernetes) (93.9, +0.3)
- Next.js (React) + Java/Kotlin + Spring Boot + Microsoft SQL Server + AWS EKS (Kubernetes) (92.6, -1.0)
- Next.js (React) + Java/Kotlin + Spring Boot + PostgreSQL + AWS ECS on Fargate (92.4, -1.2)

## Sources

- https://nextjs.org/docs
- https://react.dev
- https://survey.stackoverflow.co/2025/technology
- https://web.dev/articles/rendering-on-the-web
- https://nextjs.org/docs/app/getting-started/deploying
- https://docs.spring.io/spring-boot/index.html
- https://docs.spring.io/spring-framework/reference/data-access/transaction.html
- https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html
- https://dev.mysql.com/doc/
- https://vitess.io/docs/
- https://planetscale.com/docs
- https://aiven.io/free-mysql-database
- https://aiven.io/pricing/mysql
- https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html
- https://aws.amazon.com/eks/pricing/
- https://aws.amazon.com/eks/sla/
- https://aws.amazon.com/compute/sla/
- https://kubernetes.io/docs/concepts/overview/
