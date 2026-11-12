# StackSense recommendation: PayKaro (UPI payments)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Fintech / payments / ledger' project at Large (100k-1M daily users) scale (~2,315 peak req/s) built by 12 engineer(s) in 24 weeks, StackSense recommends Native iOS + Android (Swift / Kotlin) + Java/Kotlin + Spring Boot + PostgreSQL + AWS EKS (Kubernetes) (architecture: Modular monolith). Estimated infrastructure cost: ₹355,200-₹1,767,744/month (stretch budget). The highest-scoring stack (Native iOS + Android (Swift / Kotlin) + Java/Kotlin + Spring Boot + PostgreSQL + AWS ECS on Fargate, 92.4) is only less than 0.05 stack points ahead, inside the 1-point tie margin, so StackSense treats it as a tie and chose this stack on lower vendor lock-in (5 vs 6, summed lock-in).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Native iOS + Android (Swift / Kotlin)** | 81.4 | 3.6, solid (1.5-4 points) | Flutter (-3.6) |
| Backend | **Java/Kotlin + Spring Boot** | 95.9 | 5.4, clear (4+ points) | Node.js + NestJS (-5.4) |
| Database | **PostgreSQL** | 92.2 | 0.7, close call (under 1.5) | MySQL (-0.7, tie) |
| Hosting | **AWS EKS (Kubernetes)** | 100.0 | 0.0, close call (under 1.5) | AWS ECS on Fargate (-0.0, tie) |

Stack score: **92.4** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Modular monolith**: With 12 engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later. Sized for ~2,315 requests/s at peak, about 1,460 GB of data within 12 months and a 99.95% availability target.

Availability approach: Multi-AZ app and database, health checks, zero-downtime deploys

### How the parts fit

1. **Request path**: The iOS/Android app, installed from the app stores, sends API calls to the Java/Kotlin + Spring Boot service on AWS EKS (Kubernetes) (~2,315 requests/s at peak), which queries PostgreSQL.
2. **Sign-in**: Sign-in uses Amazon Cognito in the Mumbai region (ap-south-1); the Java/Kotlin + Spring Boot API checks the session or token on every request.
3. **Data**: PostgreSQL is the system of record (about 1,460 GB within 12 months); uploaded files go to Amazon S3, a private bucket in your required region (short-lived signed URLs, no public CDN). Card and bank details never reach your servers: the payment provider's hosted checkout or SDK collects them, and you store only its tokens. Every store above is placed in the region your residency rule requires.
4. **Deploy**: CI builds container images and rolls them out on AWS EKS (Kubernetes) (manifests or Helm), one service at a time. App releases go through App Store and Google Play review. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Large (100k-1M daily users) (peak ~2,315 req/s, derived); database tier: Large (1-10 TB of data) (~1,460 GB in 12 months)
- Budget: ~$15,625/month (INR converted at a fixed planning rate of 96 INR = 1 USD (an assumption; check the FBIL reference rate for today's value).)
- Assumption: compliance = dpdp: DPDP Act 2023 (in force through the DPDP Rules 2025, notified November 2025 and phased in over 18 months) allows cross-border transfer except to notified countries, so it adds consent/breach-notice duties but not an India-region filter. Add 'Data must stay in India' if a sector rule (e.g. RBI) applies.

## Warnings and how they were resolved

- **[WARNING] Budget below the top of the estimate**: ₹355,200-₹1,767,744/month against ₹1,500,000/month: the top (~3x today's load) is over, most of the rise in PostgreSQL and AWS EKS. *Resolution:* Raise the budget before the load grows.

## Per-layer reasoning

### Frontend: Native iOS + Android (Swift / Kotlin) (81.4)

Two native codebases using SwiftUI and Jetpack Compose.

Native iOS + Android (Swift / Kotlin) is the app for a Fintech / payments / ledger project with about 500,000 daily users (~2,315 requests/s at peak), built by a team of 12 in 24 weeks. Native Swift and Kotlin apps give full platform APIs and the best performance, at the cost of two codebases. It leads the runner-up, Flutter, by 3.6 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Ecosystem maturity: 5.0/5 vs 4.3 average for this layer - weighted up because: Financial systems favour proven tech; 99.95% target.
- Performance / latency: 5.0/5 vs 4.0 average for this layer - weighted up because: Large (100k-1M daily users); p95 target 300 ms.
- Structure for large teams: 4.0/5 vs 3.3 average for this layer - weighted up because: 12 engineers need enforced conventions.
- Team skill match (4.5/5, direct): your team lists Kotlin, a direct match for Native iOS + Android (Swift / Kotlin).
- Best performance, platform APIs and offline/background capabilities
- Day-one access to new OS features

**Trade-offs**
- Development speed is only 2.0/5 (weight 1.0).
- Two codebases, roughly double the effort
- Needs at least one specialist per platform

**Versus runner-up:** Native iOS + Android (Swift / Kotlin) beats Flutter by 3.6 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team size (+1.2), team skills (+0.5), general quality (baseline weights) (+0.4).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +27.8
- Team size: +17.0
- Team skills: +13.5
- Application type: +6.2
- Realtime needs: +4.6
- Availability target: +3.1

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 4.5 | 3.5 | 18.9 |
| Ecosystem maturity | 5.0 | 3.0 | 18.5 |
| Performance / latency | 5.0 | 1.5 | 9.3 |
| Structure for large teams | 4.0 | 1.8 | 8.3 |
| Hiring pool | 4.0 | 1.5 | 6.9 |
| Realtime fit | 4.0 | 1.2 | 5.6 |
| Learning curve | 5.0 | 0.5 | 3.1 |
| Low ops burden | 3.0 | 1.0 | 3.1 |
| Rich client interactivity | 5.0 | 0.5 | 3.1 |
| Portability (low lock-in) | 5.0 | 0.5 | 3.1 |
| Development speed | 2.0 | 1.0 | 1.5 |
| SEO | 1.0 | 0.2 | 0.0 |

**Alternatives**
- Flutter (stack 88.8, -3.6): Scores 67.1 on its own; its stack is 3.6 stack points behind the pick.
- React Native (Expo) (stack 85.4, -7.0): Scores 53.6 on its own; its stack is 7.0 stack points behind the pick.

**Why not the others?**
- Why not Flutter? (runner-up) Swapping it in lowers the stack score by 3.6 points. Native iOS + Android (Swift / Kotlin) is stronger on ecosystem maturity (5.0 vs 4.0), structure for large teams (4.0 vs 3.0); Flutter is stronger on development speed (4.0 vs 2.0), low ops burden (4.0 vs 3.0).
- Why not React Native (Expo)? (popular choice) Swapping it in lowers the stack score by 7.0 points. Native iOS + Android (Swift / Kotlin) is stronger on team skill match (4.5 vs 1.5), performance / latency (5.0 vs 3.0); React Native (Expo) is stronger on development speed (4.0 vs 2.0), low ops burden (4.0 vs 3.0).

**Excluded by hard constraints**
- Next.js (React): Web-only framework; you target iOS/Android only
- React SPA (Vite): Web-only framework; you target iOS/Android only
- Nuxt (Vue): Web-only framework; you target iOS/Android only
- SvelteKit: Web-only framework; you target iOS/Android only
- Angular: Web-only framework; you target iOS/Android only
- Astro: Web-only framework; you target iOS/Android only
- Server-rendered HTML + HTMX: Web-only framework; you target iOS/Android only
- No frontend (API only): You target a user interface, so a frontend is needed
- Qt (C++): Desktop toolkit; you do not target desktop
- Tauri (Rust): Desktop toolkit; you do not target desktop
- .NET MAUI (C#): Desktop toolkit; you do not target desktop
- Electron (JavaScript): Desktop toolkit; you do not target desktop
- Unity (C#): Game engine; the project is not a game
- Unreal Engine (C++): Game engine; the project is not a game

### Backend: Java/Kotlin + Spring Boot (95.9)

Enterprise JVM framework: DI, Spring Data, Spring Security, transactions, observability.

Java/Kotlin + Spring Boot serves the API at about 2,315 requests/s at peak (Large (100k-1M daily users)) for a team of 12. The team lists Java and Kotlin and Spring, so it needs no new server language (team skill match 5.0/5). It runs as a long-running Java/Kotlin service, so background jobs, WebSockets and database connection pools live in one deployable process. It leads the runner-up, Node.js + NestJS, by 5.4 stack points.

**Why**
- Structure for large teams: 5.0/5 vs 3.2 average for this layer - weighted up because: 12 engineers need enforced conventions.
- Hiring pool: 5.0/5 vs 3.6 average for this layer - weighted up because: 12 engineers: hiring pool matters.
- Scalability: 5.0/5 vs 4.3 average for this layer - weighted up because: Large (100k-1M daily users); 99.95% target.
- Bonus +6: Your team already ships Java/Kotlin + Spring Boot (java, kotlin, spring listed in team skills).
- Team skill match (5.0/5, direct): your team lists Java, Kotlin, Spring, a direct match for Java/Kotlin + Spring Boot.
- Declarative transactions and Spring Security suit fintech/banking
- Largest enterprise hiring pool (very strong in India)
- Mature observability and resilience libraries

**Trade-offs**
- Higher memory footprint, slow JVM cold starts (mitigated by GraalVM/SnapStart)
- Verbose for small MVPs

**Versus runner-up:** Java/Kotlin + Spring Boot beats Node.js + NestJS by 5.4 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team skills (+2.7), team size (+0.8), scale (dau / peak rps) (+0.6). Node.js + NestJS is stronger on realtime needs (+0.3).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +32.2
- Team skills: +18.8
- Team size: +17.9
- Scale (DAU / peak RPS): +9.6
- Availability target: +5.1
- Application type: +5.1

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 5.0 | 3.5 | 17.9 |
| Scalability | 5.0 | 3.0 | 15.4 |
| Ecosystem maturity | 5.0 | 3.0 | 15.4 |
| Structure for large teams | 5.0 | 1.8 | 9.2 |
| Hiring pool | 5.0 | 1.5 | 7.7 |
| Performance / latency | 4.0 | 1.5 | 5.8 |
| Cost at your scale | 5.0 | 1.0 | 5.1 |
| Realtime fit | 3.0 | 1.2 | 3.1 |
| Learning curve | 5.0 | 0.5 | 2.6 |
| Low ops burden | 3.0 | 1.0 | 2.6 |
| Development speed | 3.0 | 1.0 | 2.6 |
| Portability (low lock-in) | 5.0 | 0.5 | 2.6 |
| Adjustment: Your team already ships Java/Kotlin + Spring Boot (java, kotlin, spring listed in team skills) | | | +6.0 |

**Alternatives**
- Node.js + NestJS (stack 87.0, -5.4): Scores 74.4 on its own; its stack is 5.4 stack points behind the pick.
- Go (net/http, chi or Gin) (stack 86.7, -5.7): Scores 73.3 on its own; its stack is 5.7 stack points behind the pick.

**Why not the others?**
- Why not Node.js + NestJS? (runner-up) Swapping it in lowers the stack score by 5.4 points. Java/Kotlin + Spring Boot is stronger on team skill match (5.0 vs 3.5), scalability (5.0 vs 4.0); Node.js + NestJS is stronger on realtime fit (4.0 vs 3.0), low ops burden (4.0 vs 3.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 10.2 points. Java/Kotlin + Spring Boot is stronger on team skill match (5.0 vs 1.5), structure for large teams (5.0 vs 1.0); Node.js + Express is stronger on realtime fit (4.0 vs 3.0), low ops burden (4.0 vs 3.0); Node.js + Express takes a penalty: Nobody on the team listed Node.js or a closely related skill: a new server language to learn.
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 9.5 points. Java/Kotlin + Spring Boot is stronger on team skill match (5.0 vs 1.5), scalability (5.0 vs 4.0); Python + Django is stronger on development speed (5.0 vs 3.0), low ops burden (4.0 vs 3.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: PostgreSQL (92.2)

Open-source relational database with ACID transactions, JSONB, full-text search and extensions (PostGIS, pgvector, TimescaleDB).

Your data is mainly relational and reaches about 1,460 GB within 12 months; PostgreSQL fits relational data 5/5. You need strong consistency, and PostgreSQL gives it: a read after a write always sees that write. Its share of the estimated bill is ₹76,800-₹751,872 a month, against a total budget of ₹1,500,000 a month. MySQL is within 0.7 stack points, inside the tie margin (stacks this close count as tied); the tie went to PostgreSQL on adjacent team skills (19.5 vs 19, summed skill fit).

Suggested offering: Amazon RDS / Aurora PostgreSQL (+ RDS Proxy for serverless)

**Why**
- Data-model fit: 5.0/5 vs 4.2 average for this layer.
- Consistency fit: 5.0/5 vs 4.7 average for this layer - weighted up because: Ledgers need ACID; Strong consistency required.
- Hiring pool: 5.0/5 vs 4.4 average for this layer - weighted up because: 12 engineers: hiring pool matters.
- Team skill match (5.0/5, direct): your team lists PostgreSQL, SQL, a direct match for PostgreSQL.
- Default choice for relational data: constraints, joins, transactions
- Extensions cover JSON, search, geo, time-series and vectors
- Every cloud offers it managed; zero vendor lock-in

**Trade-offs**
- Single-writer primary: write scale-out needs sharding (Citus) or Aurora Limitless
- Connection-per-process model needs PgBouncer/RDS Proxy under serverless

**Versus runner-up:** PostgreSQL and MySQL are within 0.7 stack points of each other, inside the 1-point tie margin, so they count as tied. PostgreSQL is stronger on realtime fit (3.0 vs 2.0). The tie went to PostgreSQL on adjacent team skills (19.5 vs 19, summed skill fit). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +43.5
- Application type: +11.4
- Team skills: +9.5
- Team size: +7.6
- Scale (DAU / peak RPS): +5.7
- Consistency need: +5.7

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 5.0 | 5.0 | 19.1 |
| Consistency fit | 5.0 | 4.5 | 17.2 |
| Team skill match | 5.0 | 3.5 | 13.4 |
| Ecosystem maturity | 5.0 | 3.0 | 11.4 |
| Scalability | 4.0 | 3.0 | 8.6 |
| Hiring pool | 5.0 | 1.5 | 5.7 |
| Performance / latency | 4.0 | 1.5 | 4.3 |
| Cost at your scale | 4.7 | 1.0 | 3.5 |
| Low ops burden | 4.0 | 1.0 | 2.9 |
| Realtime fit | 3.0 | 1.2 | 2.3 |
| Learning curve | 5.0 | 0.5 | 1.9 |
| Portability (low lock-in) | 5.0 | 0.5 | 1.9 |

**Alternatives**
- MySQL (stack 91.7, -0.7): Scores 89.4 on its own; its stack is 0.7 stack points behind the pick.
- Microsoft SQL Server (stack 91.0, -1.3): Scores 86.8 on its own; its stack is 1.3 stack points behind the pick.

**Why not the others?**
- Why not MySQL? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.7 points lower; either is defensible. PostgreSQL is stronger on team skill match (5.0 vs 4.5), realtime fit (3.0 vs 2.0).
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 11.2 points. PostgreSQL is stronger on data-model fit (5.0 vs 2.0), team skill match (5.0 vs 1.5); MongoDB is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 3.0); MongoDB takes a penalty: Only 2/5 fit for your primary 'relational' data.

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5)
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~1,460 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your relational data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.95% availability; One writer at a time for the whole file: 8.0M+ requests a day at Large (100k-1M daily users) is past the 1M a day SQLite's own guide says it has been shown to handle
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: AWS EKS (Kubernetes) (100.0)

Managed Kubernetes control plane on AWS.

AWS EKS (Kubernetes) hosts the stack for users in India at a 99.95% availability target. It runs the Java/Kotlin + Spring Boot API as long-running processes with WebSockets, sized for ~2,315 requests/s at peak. It has a region in India, so data can stay in the country. Its share of the estimated bill is ₹134,400-₹655,872 a month, against a total budget of ₹1,500,000 a month. AWS ECS on Fargate is within less than 0.05 stack points, inside the tie margin (stacks this close count as tied); the tie went to AWS EKS (Kubernetes) on lower vendor lock-in (5 vs 6, summed lock-in).

Runs here: the Java/Kotlin + Spring Boot API as long-running processes. The database runs as a separate managed service (see Database).

**Why**
- Ecosystem maturity: 5.0/5 vs 4.7 average for this layer - weighted up because: Financial systems favour proven tech; 99.95% target.
- Realtime fit: 4.0/5 vs 3.5 average for this layer - weighted up because: Some realtime features.
- Scalability: 5.0/5 vs 4.8 average for this layer - weighted up because: Large (100k-1M daily users); 99.95% target.
- Bonus +12.0: Runs on your preferred cloud (AWS).
- Team skill match (5.0/5, direct): your team lists AWS, Kubernetes, a direct match for AWS EKS (Kubernetes).
- Portable Kubernetes workloads with the AWS ecosystem
- Fine-grained autoscaling for many services

**Trade-offs**
- Low ops burden is only 1.0/5 (weight 1.0).
- Control-plane fee (~$73/mo) plus nodes
- Needs dedicated platform/DevOps skills

**Versus runner-up:** AWS EKS (Kubernetes) and AWS ECS on Fargate score the same (less than 0.05 stack points apart), inside the 1-point tie margin, so they count as tied. AWS EKS (Kubernetes) is stronger on portability (low lock-in) (4.0 vs 3.0); AWS ECS on Fargate is stronger on low ops burden (3.0 vs 1.0). Choose AWS ECS on Fargate instead if less to operate matters more to you than low lock-in. The tie went to AWS EKS (Kubernetes) on lower vendor lock-in (5 vs 6, summed lock-in). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +31.1
- Team skills: +14.5
- Cloud preference: +12.0
- Scale (DAU / peak RPS): +10.9
- Compliance: +8.7
- Availability target: +5.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 5.0 | 3.5 | 20.4 |
| Scalability | 5.0 | 3.0 | 17.4 |
| Ecosystem maturity | 5.0 | 3.0 | 17.4 |
| Region coverage | 5.0 | 2.0 | 11.6 |
| Performance / latency | 4.0 | 1.5 | 6.5 |
| Cost at your scale | 4.8 | 1.0 | 5.5 |
| Realtime fit | 4.0 | 1.2 | 5.2 |
| Learning curve | 5.0 | 0.5 | 2.9 |
| Portability (low lock-in) | 4.0 | 0.5 | 2.2 |
| Low ops burden | 1.0 | 1.0 | 0.0 |
| Adjustment: Runs on your preferred cloud (AWS) | | | +12.0 |

**Alternatives**
- AWS ECS on Fargate (stack 92.4, -0.0): Scores 100.0 on its own; its stack is less than 0.05 stack points behind the pick.
- DigitalOcean (App Platform + Managed DBs) (stack 87.8, -4.6): Scores 81.8 on its own; its stack is 4.6 stack points behind the pick.

**Why not the others?**
- Why not AWS ECS on Fargate? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores the same (less than 0.05 points apart); either is defensible. AWS EKS (Kubernetes) is stronger on portability (low lock-in) (4.0 vs 3.0); AWS ECS on Fargate is stronger on low ops burden (3.0 vs 1.0).
- Why not Vercel? (popular choice) Ruled out for your answers: No published SLA, so nothing backs your 99.95% availability target.
- Why not Render? (popular choice) Ruled out for your answers: No India region; data must stay in India.

**Excluded by hard constraints**
- Vercel: No published SLA, so nothing backs your 99.95% availability target
- Netlify: No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- Cloudflare Pages + Workers: Keeping data and TLS termination inside India or the EU needs the Data Localization Suite, an Enterprise add-on; treated as not meeting a residency rule.; No published SLA, so nothing backs your 99.95% availability target
- Render: No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- Railway: No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- Fly.io: No India region; data must stay in India; No published SLA, so nothing backs your 99.95% availability target
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay
- Firebase Hosting (static): Only for read-only sites; your users sign in, post or pay
- Google Cloud Storage + Cloud CDN (static): Only for read-only sites; your users sign in, post or pay
- Azure Static Web Apps: Only for read-only sites; your users sign in, post or pay
- Azure Blob Storage + Front Door (static): Only for read-only sites; your users sign in, post or pay
- Google Kubernetes Engine (Autopilot): The provider's SLA is 99.9% (Autopilot Pods in multiple zones (the control plane is 99.95%)), below your 99.95% availability target
- Hetzner Cloud / VPS (Docker, Coolify): The provider's SLA is 99.9% (each Cloud Server), below your 99.95% availability target; No India region; data must stay in India
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud; Docker Compose runs an app's containers on one Docker host and restarts them only on that host; placing and moving containers across several hosts is what Swarm or Kubernetes add: no automatic failover to a second host, so it cannot meet 99.95% availability
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs

## Supporting services

- **Realtime**: WebSockets in the Java/Kotlin + Spring Boot app (Spring WebSocket with STOMP): Chat and live updates for a part of the product: the app server holds the connections itself; add Redis pub/sub only when a second instance must reach the same users.
- **Background jobs**: Amazon SQS with Spring Cloud AWS listeners: Send emails, process uploads and call slow APIs outside the request path.
- **Phone login (SMS OTP)**: MSG91, with DLT-registered SMS templates: One-time codes need an SMS gateway with rate limits against SMS-pumping fraud; Indian operators deliver only DLT-registered templates. MSG91 stores its data only in India (Google Cloud, Mumbai) according to its 2024 data-localisation audit, which notes some processing in Singapore with the data brought back to India; Twilio Verify runs in Twilio's US region (twilio.com/docs/global-infrastructure), so codes and phone numbers would be processed and stored outside India.
- **Payments**: Razorpay with hosted checkout (card tokens): Card data never touches your servers, which keeps your PCI-DSS audit scope to the smallest self-assessment form (SAQ A). Stripe accepts new businesses in India by invitation only, so an Indian gateway leads.
- **Object storage**: Amazon S3, a private bucket in your required region (short-lived signed URLs, no public CDN): Media and documents belong in object storage, not the database.
- **Authentication**: Amazon Cognito in the Mumbai region (ap-south-1): Do not hand-roll password storage, MFA or SSO.
- **Push notifications**: Firebase Cloud Messaging (+ APNs): Standard channel for mobile engagement on Android and iOS. Notification text leaves your residency region: Firebase Cloud Messaging may process messages anywhere Google has facilities, so send only an ID and let the app fetch the content from your servers in the region.
- **Observability**: OpenTelemetry instrumentation -> CloudWatch + X-Ray: Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: AWS EKS (Kubernetes) | 1,400 | 6,832 | Large (100k-1M daily users) price band, from the band's floor up to its price at ~3x the load, for 500,000 daily users (70% of the way up the tier, log scale); x2 for 99.95% availability (redundant instances) |
| Database: PostgreSQL | 800 | 7,832 | Large (1-10 TB of data) database tier (~1,460 GB in 12 months), from the band's floor up to its price at ~3x the load, for 2,315 req/s at peak (67% of the way up the tier, log scale); x2 for 99.95% availability (standby/replicas) |
| Phone login (SMS OTP) | 1,500 | 3,750 | ~750,000 SMS a month (one login every ~20 days per active user) at $0.002-0.005 each |
| **Total** | **3,700** | **18,414** | |

About ₹355,200-₹1,767,744 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, each read where the project sits inside its tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Budget cut to ₹300,000/month (x0.2)**: hosting: AWS EKS (Kubernetes) -> AWS ECS on Fargate
  - Why hosting changes: Cost at your scale moved the gap 0.2 points toward AWS ECS on Fargate (AWS ECS on Fargate 4.4/5 vs AWS EKS (Kubernetes) 4.3/5, was 4.9 vs 4.8); on its own AWS EKS (Kubernetes) still scores 0.0 higher, so AWS ECS on Fargate wins as part of the whole stack (the other layers changed, and the stack-level compatibility rules or tie-break favour it).
- **A solo developer**: hosting: AWS EKS (Kubernetes) -> AWS ECS on Fargate
  - Why hosting changes: AWS EKS (Kubernetes) now takes a penalty (Usually needs a team of 4+ to operate), moving the gap 12.0 points toward AWS ECS on Fargate; low ops burden moved the gap 6.0 points toward AWS ECS on Fargate (AWS ECS on Fargate 3.0/5 vs AWS EKS (Kubernetes) 1.0/5, weight 1.0 -> 3.5).
- **Must run on-premises**: hosting: AWS EKS (Kubernetes) -> On-prem Kubernetes (k3s / RKE2 / OpenShift)
  - Why hosting changes: AWS EKS (Kubernetes) is now ruled out: Public-cloud service; deployment must be on-premises.
- **Team has no relevant prior skills**: hosting: AWS EKS (Kubernetes) -> AWS ECS on Fargate
  - Why hosting changes: AWS EKS (Kubernetes) now takes a penalty (Requires platform/DevOps skills your team did not list), moving the gap 8.0 points toward AWS ECS on Fargate; learning curve moved the gap 1.8 points toward AWS ECS on Fargate (AWS ECS on Fargate 3.0/5 vs AWS EKS (Kubernetes) 1.0/5, was 5.0 vs 5.0).

## Next-best complete stacks

- Native iOS + Android (Swift / Kotlin) + Java/Kotlin + Spring Boot + PostgreSQL + AWS ECS on Fargate (92.4, +0.0)
- Native iOS + Android (Swift / Kotlin) + Java/Kotlin + Spring Boot + MySQL + AWS ECS on Fargate (91.7, -0.7)
- Native iOS + Android (Swift / Kotlin) + Java/Kotlin + Spring Boot + MySQL + AWS EKS (Kubernetes) (91.7, -0.7)

## Sources

- https://developer.apple.com/swiftui/
- https://developer.android.com/compose
- https://developer.android.com/kotlin
- https://developer.apple.com/swift/
- https://docs.spring.io/spring-boot/index.html
- https://docs.spring.io/spring-framework/reference/data-access/transaction.html
- https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html
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
- https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html
- https://aws.amazon.com/eks/pricing/
- https://aws.amazon.com/eks/sla/
- https://aws.amazon.com/compute/sla/
