# StackSense recommendation: ThaliGo (food delivery)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For an 'E-commerce / marketplace' project at Very large (1M-10M daily users) scale (~6,944 peak req/s) built by 20 engineer(s) in 30 weeks, StackSense recommends Next.js (React) + Node.js + NestJS + PostgreSQL + AWS EKS (Kubernetes) (architecture: Service-oriented (a few coarse services, one per team)). Estimated infrastructure cost: ₹2,352,000-₹12,000,000/month (stretch budget). The highest-scoring stack (Next.js (React) + Go (net/http, chi or Gin) + PostgreSQL + AWS ECS on Fargate, 89.0) is only 0.4 stack points ahead, inside the 1-point tie margin, so StackSense treats it as a tie and chose this stack on lower vendor lock-in (6 vs 7, summed lock-in).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Next.js (React)** | 82.5 | 1.2, close call (under 1.5) | Angular (-1.2) |
| Backend | **Node.js + NestJS** | 88.4 | -0.4, close call (under 1.5) | Go (net/http, chi or Gin) (+0.4, tie) |
| Database | **PostgreSQL** | 83.5 | 2.0, solid (1.5-4 points) | MySQL (-2.0) |
| Hosting | **AWS EKS (Kubernetes)** | 100.0 | 0.0, close call (under 1.5) | AWS ECS on Fargate (-0.0, tie) |
| Mobile app (iOS/Android) | React Native (Expo) | 66.3 | - | - |

Stack score: **88.6** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Service-oriented (a few coarse services, one per team)**: 20 engineers at Very large (1M-10M daily users) benefit from independently deployable services, one per team. Sized for ~6,944 requests/s at peak, about 2,800 GB of data within 12 months and a 99.95% availability target.

Availability approach: Multi-AZ app and database, health checks, zero-downtime deploys

### How the parts fit

1. **Request path**: The browser loads Next.js (React) from AWS EKS (Kubernetes); it sends API calls to the Node.js + NestJS service on AWS EKS (Kubernetes) (~6,944 requests/s at peak), which queries PostgreSQL.
2. **Sign-in**: Sign-in uses Clerk / Auth0 / framework built-in auth; the Node.js + NestJS API checks the session or token on every request.
3. **Data**: PostgreSQL is the system of record (about 2,800 GB within 12 months); uploaded files go to Amazon S3 + CloudFront. Card and bank details never reach your servers: the payment provider's hosted checkout or SDK collects them, and you store only its tokens.
4. **Deploy**: CI builds container images and rolls them out on AWS EKS (Kubernetes) (manifests or Helm), one service at a time. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Very large (1M-10M daily users) (peak ~6,944 req/s, derived); database tier: Very large (1M-10M daily users) (~2,800 GB in 12 months)
- Budget: ~$41,667/month (INR converted at a fixed planning rate of 96 INR = 1 USD (FBIL reference rate, Sep 2026).)
- Assumption: compliance = dpdp: DPDP Act 2023 (in force through the DPDP Rules 2025, notified November 2025 and phased in over 18 months) allows cross-border transfer except to notified countries, so it adds consent/breach-notice duties but not an India-region filter. Add 'Data must stay in India' if a sector rule (e.g. RBI) applies.

## Per-layer reasoning

### Frontend: Next.js (React) (82.5)

React meta-framework with server rendering, static generation, React Server Components and file-based routing.

Next.js (React) is the frontend for an E-commerce / marketplace project with about 1,000,000 daily users (~6,944 requests/s at peak), built by a team of 20 in 30 weeks. Search visibility is marked important (landing/product pages), and it serves full HTML from the server or the build (SEO 5.0/5), so crawlers read the content without running JavaScript. It leads the runner-up, Angular, by 1.2 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer - weighted up because: 99.95% target; Regulated workload.
- Hiring pool: 5.0/5 vs 3.6 average for this layer - weighted up because: 20 engineers: hiring pool matters.
- Rich client interactivity: 5.0/5 vs 4.1 average for this layer - weighted up because: Realtime UIs update without page loads; Cart, filters and checkout flows.
- Team skill match (4.5/5, direct): your team lists React, a direct match for Next.js (React).
- SSR/SSG/ISR give crawlers full HTML (strong SEO, fast LCP)
- Largest React ecosystem and hiring pool
- Same codebase can host API routes / server actions for small apps

**Trade-offs**
- App Router + Server Components add conceptual load
- Some features (ISR, image optimisation, middleware) are smoothest on Vercel

**Versus runner-up:** Next.js (React) beats Angular by 1.2 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on general quality (baseline weights) (+1.1), seo need (+0.5), team skills (+0.3). Angular is stronger on stack compatibility (+1.0), team size (+0.4). Close call: either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +23.5
- Realtime needs: +12.4
- Team size: +11.3
- Team skills: +9.4
- SEO need: +8.6
- Application type: +8.1

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 4.5 | 3.5 | 13.2 |
| Ecosystem maturity | 5.0 | 2.5 | 10.8 |
| Rich client interactivity | 5.0 | 2.5 | 10.8 |
| Performance / latency | 4.0 | 3.0 | 9.7 |
| SEO | 5.0 | 2.2 | 9.5 |
| Realtime fit | 3.0 | 3.2 | 6.9 |
| Hiring pool | 5.0 | 1.5 | 6.5 |
| Development speed | 5.0 | 1.0 | 4.3 |
| Structure for large teams | 3.0 | 1.8 | 3.9 |
| Low ops burden | 4.0 | 1.0 | 3.2 |
| Learning curve | 5.0 | 0.5 | 2.2 |
| Portability (low lock-in) | 4.0 | 0.5 | 1.6 |

**Alternatives**
- Angular (stack 87.4, -1.2): Note: Same architectural style (modules, DI) on both sides; common in enterprise teams.
- SvelteKit (stack 86.0, -2.6): Scores 72.2 on its own; its stack is 2.6 stack points behind the pick.

**Why not the others?**
- Why not Angular? (runner-up) Swapping it in lowers the stack score by 1.2 points. Next.js (React) is stronger on performance / latency (4.0 vs 3.0), SEO (5.0 vs 4.0); Angular is stronger on structure for large teams (5.0 vs 3.0).
- Why not React SPA (Vite)? (popular choice) Swapping it in lowers the stack score by 2.9 points. Next.js (React) is stronger on SEO (5.0 vs 2.0), performance / latency (4.0 vs 3.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0).

**Excluded by hard constraints**
- React Native (Expo): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Flutter: Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Native iOS + Android (Swift / Kotlin): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- No frontend (API only): You target a user interface, so a frontend is needed

### Backend: Node.js + NestJS (88.4)

Opinionated TypeScript framework (modules, DI, decorators) on top of Express/Fastify.

Node.js + NestJS serves the API at about 6,944 requests/s at peak (Very large (1M-10M daily users)) for a team of 20. It runs as a few long-running Node.js services, one per team, each deployed on its own with its own background jobs, WebSockets and database connection pool. Realtime is core, and it scores 4.0/5 on realtime fit. Go (net/http, chi or Gin) is within 0.4 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

**Why**
- Structure for large teams: 5.0/5 vs 3.2 average for this layer - weighted up because: 20 engineers need enforced conventions.
- Compliance maturity (audit, isolation): 5.0/5 vs 4.6 average for this layer - weighted up because: PCI-DSS at Very large (1M-10M daily users): auditors expect dedicated tenancy and immutable audit trails; PCI-DSS at Very large (1M-10M daily users): more records in scope and larger breach impact.
- Realtime fit: 4.0/5 vs 3.5 average for this layer - weighted up because: Realtime is core to the product.
- Bonus +6: Your team already ships Node.js + NestJS (nestjs, node listed in team skills).
- Team skill match (5.0/5, direct): your team lists nestjs, Node.js, TypeScript, a direct match for Node.js + NestJS.
- Enforced module boundaries suit growing teams and modular monoliths
- First-class WebSockets, queues, microservice transports
- Full-stack TypeScript

**Trade-offs**
- More boilerplate than Express/FastAPI
- Decorator/DI concepts slow down beginners

**Versus runner-up:** Node.js + NestJS and Go (net/http, chi or Gin) are within 0.4 stack points of each other, inside the 1-point tie margin, so they count as tied. Node.js + NestJS is stronger on structure for large teams (5.0 vs 2.0), hiring pool (4.0 vs 3.0); Go (net/http, chi or Gin) is stronger on performance / latency (5.0 vs 3.0), scalability (5.0 vs 4.0). Choose Go (net/http, chi or Gin) instead if raw speed matters more to you than structure for a growing team. The tie went to Node.js + NestJS on adjacent team skills (19 vs 18.5, summed skill fit). Either is defensible.

**Inputs that drove this score** (points out of 100)
- Scale (DAU / peak RPS): +22.3
- General quality (baseline weights): +21.7
- Team skills: +14.9
- Team size: +11.6
- Realtime needs: +8.9
- Compliance: +4.9

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Compliance maturity (audit, isolation) | 5.0 | 4.5 | 16.1 |
| Team skill match | 5.0 | 3.5 | 12.5 |
| Scalability | 4.0 | 4.5 | 12.1 |
| Realtime fit | 4.0 | 3.2 | 8.6 |
| Ecosystem maturity | 4.0 | 2.5 | 6.7 |
| Structure for large teams | 5.0 | 1.8 | 6.4 |
| Performance / latency | 3.0 | 3.0 | 5.4 |
| Hiring pool | 4.0 | 1.5 | 4.0 |
| Low ops burden | 4.0 | 1.0 | 2.7 |
| Development speed | 4.0 | 1.0 | 2.7 |
| Cost at your scale | 5.0 | 0.5 | 1.8 |
| Learning curve | 5.0 | 0.5 | 1.8 |
| Portability (low lock-in) | 5.0 | 0.5 | 1.8 |
| Adjustment: Your team already ships Node.js + NestJS (nestjs, node listed in team skills) | | | +6.0 |

**Alternatives**
- Go (net/http, chi or Gin) (stack 89.0, +0.4): Scores 90.1 on its own; its stack is 0.4 stack points ahead of the pick.
- Node.js + Express (stack 87.9, -0.7): Scores 85.5 on its own; its stack is 0.7 stack points behind the pick.

**Why not the others?**
- Why not Go (net/http, chi or Gin)? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.4 points higher; either is defensible. Node.js + NestJS is stronger on structure for large teams (5.0 vs 2.0), team skill match (5.0 vs 4.5); Go (net/http, chi or Gin) is stronger on performance / latency (5.0 vs 3.0), scalability (5.0 vs 4.0).
- Why not Node.js + Express? (popular choice) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.7 points lower; either is defensible. Node.js + NestJS is stronger on structure for large teams (5.0 vs 1.0); Node.js + Express is stronger on ecosystem maturity (5.0 vs 4.0), hiring pool (5.0 vs 4.0).
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 7.4 points. Node.js + NestJS is stronger on team skill match (5.0 vs 1.5), realtime fit (4.0 vs 2.0); Python + Django is stronger on ecosystem maturity (5.0 vs 4.0), development speed (5.0 vs 4.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 5.2 points. Node.js + NestJS is stronger on team skill match (5.0 vs 1.5), realtime fit (4.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on scalability (5.0 vs 4.0), performance / latency (4.0 vs 3.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: PostgreSQL (83.5)

Open-source relational database with ACID transactions, JSONB, full-text search and extensions (PostGIS, pgvector, TimescaleDB).

Your data is mainly relational and reaches about 2,800 GB within 12 months; PostgreSQL fits relational data 5/5. You need strong consistency, and PostgreSQL gives it: a read after a write always sees that write. Its share of the estimated bill is ₹576,000-₹1,152,000 a month, against a total budget of ₹4,000,000 a month. It leads the runner-up, MySQL, by 2.0 stack points.

Suggested offering: Amazon RDS / Aurora PostgreSQL (+ RDS Proxy for serverless)

**Why**
- Data-model fit: 4.7/5 vs 4.0 average for this layer.
- Realtime fit: 3.0/5 vs 2.6 average for this layer - weighted up because: Realtime is core to the product.
- Hiring pool: 5.0/5 vs 4.4 average for this layer - weighted up because: 20 engineers: hiring pool matters.
- Team skill match (4.5/5, direct): your team lists PostgreSQL, a direct match for PostgreSQL.
- Default choice for relational data: constraints, joins, transactions
- Extensions cover JSON, search, geo, time-series and vectors
- Every cloud offers it managed; zero vendor lock-in

**Trade-offs**
- Single-writer primary: write scale-out needs sharding (Citus) or Aurora Limitless
- Connection-per-process model needs PgBouncer/RDS Proxy under serverless

**Versus runner-up:** PostgreSQL beats MySQL by 2.0 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on realtime needs (+0.7), team skills (+0.6), general quality (baseline weights) (+0.5).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +38.8
- Scale (DAU / peak RPS): +10.6
- Team skills: +7.8
- Realtime needs: +6.7
- Team size: +6.7
- Consistency need: +5.3

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.7 | 5.0 | 16.2 |
| Scalability | 4.0 | 4.5 | 12.0 |
| Team skill match | 4.5 | 3.5 | 10.9 |
| Ecosystem maturity | 5.0 | 2.5 | 8.9 |
| Consistency fit | 5.0 | 2.5 | 8.9 |
| Performance / latency | 4.0 | 3.0 | 8.0 |
| Realtime fit | 3.0 | 3.2 | 5.7 |
| Hiring pool | 5.0 | 1.5 | 5.3 |
| Low ops burden | 4.0 | 1.0 | 2.7 |
| Learning curve | 5.0 | 0.5 | 1.8 |
| Portability (low lock-in) | 5.0 | 0.5 | 1.8 |
| Cost at your scale | 4.5 | 0.5 | 1.6 |

**Alternatives**
- MySQL (stack 86.6, -2.0): Scores 75.7 on its own; its stack is 2.0 stack points behind the pick.
- Microsoft SQL Server / Azure SQL Database (stack 86.0, -2.7): Scores 72.9 on its own; its stack is 2.7 stack points behind the pick.

**Why not the others?**
- Why not MySQL? (runner-up) Swapping it in lowers the stack score by 2.0 points. PostgreSQL is stronger on team skill match (4.5 vs 3.5), realtime fit (3.0 vs 2.0).
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 5.4 points. PostgreSQL is stronger on data-model fit (4.7 vs 3.0), consistency fit (5.0 vs 3.5); MongoDB is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 3.0); MongoDB takes a penalty: Only 2/5 fit for your primary 'relational' data.

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5)
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~2,800 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: not the system of record for PCI DSS data (use it beside a durable store)
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (2/5)
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational, document data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational, document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.95% availability; One writer at a time for the whole file: 60.0M+ requests a day at Very large (1M-10M daily users) is past the 1M a day SQLite's own guide says it has been shown to handle; Scale ceiling far below Very large (1M-10M daily users)
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: AWS EKS (Kubernetes) (100.0)

Managed Kubernetes control plane on AWS.

AWS EKS (Kubernetes) hosts the stack for users in India at a 99.95% availability target. It runs the Node.js + NestJS API as long-running processes with WebSockets, sized for ~6,944 requests/s at peak. For PCI DSS it is a validated service provider, so card-handling infrastructure can sit on it. Its share of the estimated bill is ₹480,000-₹2,304,000 a month, against a total budget of ₹4,000,000 a month. AWS ECS on Fargate is within less than 0.05 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

Runs here: Next.js (server rendering + static files), the Node.js + NestJS API as long-running processes. The database runs as a separate managed service (see Database).

**Why**
- Realtime fit: 4.0/5 vs 3.4 average for this layer - weighted up because: Realtime is core to the product.
- Performance / latency: 4.0/5 vs 3.8 average for this layer - weighted up because: Very large (1M-10M daily users); Realtime is core to the product.
- Ecosystem maturity: 5.0/5 vs 4.8 average for this layer - weighted up because: 99.95% target; Regulated workload.
- Bonus +12.0: Runs on your preferred cloud (AWS).
- Team skill match (5.0/5, direct): your team lists AWS, Kubernetes, a direct match for AWS EKS (Kubernetes).
- Portable Kubernetes workloads with the AWS ecosystem
- Fine-grained autoscaling for many services

**Trade-offs**
- Low ops burden is only 1.0/5 (weight 1.0).
- Control-plane fee (~$73/mo) plus nodes
- Needs dedicated platform/DevOps skills

**Versus runner-up:** AWS EKS (Kubernetes) and AWS ECS on Fargate score the same (less than 0.05 stack points apart), inside the 1-point tie margin, so they count as tied. AWS EKS (Kubernetes) is stronger on portability (low lock-in) (4.0 vs 3.0); AWS ECS on Fargate is stronger on low ops burden (3.0 vs 1.0). Choose AWS ECS on Fargate instead if less to operate matters more to you than low lock-in. The tie went to AWS EKS (Kubernetes) on lower vendor lock-in (6 vs 7, summed lock-in). Either is defensible.

**Inputs that drove this score** (points out of 100)
- Scale (DAU / peak RPS): +28.8
- General quality (baseline weights): +21.1
- Cloud preference: +12.0
- Realtime needs: +10.4
- Team skills: +9.9
- Compliance: +6.0

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Scalability | 5.0 | 4.5 | 17.9 |
| Compliance maturity (audit, isolation) | 5.0 | 4.5 | 17.9 |
| Team skill match | 5.0 | 3.5 | 13.9 |
| Ecosystem maturity | 5.0 | 2.5 | 9.9 |
| Realtime fit | 4.0 | 3.2 | 9.5 |
| Performance / latency | 4.0 | 3.0 | 8.9 |
| Region coverage | 5.0 | 1.5 | 6.0 |
| Learning curve | 5.0 | 0.5 | 2.0 |
| Cost at your scale | 4.7 | 0.5 | 1.8 |
| Portability (low lock-in) | 4.0 | 0.5 | 1.5 |
| Low ops burden | 1.0 | 1.0 | 0.0 |
| Adjustment: Runs on your preferred cloud (AWS) | | | +12.0 |

**Alternatives**
- AWS ECS on Fargate (stack 88.6, +0.0): Scores 100.0 on its own; its stack is less than 0.05 stack points behind the pick.
- Azure App Service / Container Apps (stack 84.2, -4.4): Scores 82.5 on its own; its stack is 4.4 stack points behind the pick.

**Why not the others?**
- Why not AWS ECS on Fargate? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores the same (less than 0.05 points apart); either is defensible. AWS EKS (Kubernetes) is stronger on portability (low lock-in) (4.0 vs 3.0); AWS ECS on Fargate is stronger on low ops burden (3.0 vs 1.0).
- Why not Vercel? (popular choice) Ruled out for your answers: No published SLA, so nothing backs your 99.95% availability target.
- Why not Render? (popular choice) Ruled out for your answers: No PCI-DSS attestation published.

**Excluded by hard constraints**
- Vercel: No published SLA, so nothing backs your 99.95% availability target
- Netlify: No published SLA, so nothing backs your 99.95% availability target
- Cloudflare Pages + Workers: No published SLA, so nothing backs your 99.95% availability target
- Render: No PCI-DSS attestation published; No published SLA, so nothing backs your 99.95% availability target
- Railway: No PCI-DSS attestation published; No published SLA, so nothing backs your 99.95% availability target
- Fly.io: No PCI-DSS attestation published; No published SLA, so nothing backs your 99.95% availability target
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay; The provider's SLA is 99.9% (CloudFront distribution), below your 99.95% availability target
- Google Kubernetes Engine (Autopilot): The provider's SLA is 99.9% (Autopilot Pods in multiple zones (the control plane is 99.95%)), below your 99.95% availability target
- DigitalOcean (App Platform + Managed DBs): No PCI-DSS attestation published
- Hetzner Cloud / VPS (Docker, Coolify): The provider's SLA is 99.9% (each Cloud Server), below your 99.95% availability target; No PCI-DSS attestation published
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud; Docker Compose runs an app's containers on one Docker host and restarts them only on that host; placing and moving containers across several hosts is what Swarm or Kubernetes add: no automatic failover to a second host, so it cannot meet 99.95% availability
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs

## Supporting services

- **Realtime**: Redis pub/sub for cross-instance fan-out (ElastiCache (Valkey)): With several app instances, a message published on one must reach sockets on all others.
- **Analytics**: ClickHouse Cloud (AWS/GCP/Azure) fed by a continuous copy of database changes: Run heavy aggregations on a columnar store instead of the transactional database.
- **Background jobs**: BullMQ (Redis): Send emails, process uploads and call slow APIs outside the request path. BullMQ keeps its jobs in Redis, so the app needs a Redis/Valkey instance (the one already listed above).
- **Search**: Amazon OpenSearch Service: Search across ~933 GB of documents (an estimate: the document share of your ~2,800 GB total, from your 2 data shapes) needs an inverted index with relevance ranking, highlighting and filters; database text indexes slow down and rank poorly at this size.
- **Object storage**: Amazon S3 + CloudFront: Uploaded files and video belong in object storage, not the database.
- **Media delivery**: CDN in front of the object storage, with image resizing at the edge: Serve uploads from the CDN, not the app server; resize images on the fly instead of storing every size.
- **Maps & live location**: Google Maps Platform, Mapbox or Ola Maps + location updates over the realtime channel: Send position updates every few seconds over WebSockets (not polling) and keep only the latest point per device in a fast store; map tiles and routing come from a maps provider.
- **Phone login (SMS OTP)**: MSG91 or Twilio Verify, with DLT-registered SMS templates: One-time codes need an SMS gateway with rate limits against SMS-pumping fraud; Indian operators deliver only DLT-registered templates.
- **Payments**: Razorpay / Cashfree (India) or Stripe with hosted checkout (card tokens): Card data never touches your servers, which keeps your PCI-DSS audit scope to the smallest self-assessment form (SAQ A).
- **Authentication**: Clerk / Auth0 / framework built-in auth: Do not hand-roll password storage, MFA or SSO.
- **Push notifications**: Firebase Cloud Messaging (+ APNs) or Expo Notifications: Standard channel for mobile engagement on Android and iOS.
- **Observability**: OpenTelemetry instrumentation -> CloudWatch + X-Ray: Traces, metrics and error tracking from day one; required to defend an availability target.
- **Audit & security**: Encrypted storage (KMS), audit logging, least-privilege IAM, WAF: PCI-DSS requires access controls, audit trails and encryption.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: AWS EKS (Kubernetes) | 5,000 | 24,000 | Very large (1M-10M daily users) price band; x2 for 99.95% availability (redundant instances) |
| Database: PostgreSQL | 6,000 | 12,000 | Very large (1M-10M daily users) database tier (~2,800 GB in 12 months); upper end for ~2,800 GB of data: the band's top is priced for the largest data of the tier; x2 for 99.95% availability (standby/replicas) |
| Realtime: Redis / Valkey | 1,500 | 8,000 | Very large (1M-10M daily users) price band (the app's scale) |
| Analytics: ClickHouse | 3,000 | 15,000 | Very large (1M-10M daily users) price band (the app's scale); a copy of data that PostgreSQL also stores (fed by a continuous copy of changes), so that data is paid for in both stores |
| Media delivery | 1,500 | 13,500 | ~150,000 GB served a month (5 MB per active user a day) at $0.01-0.09/GB |
| Maps & live location | 4,500 | 45,000 | ~9.0M map loads a month (0.3 per active user a day) at $0.0005-0.005 each |
| Phone login (SMS OTP) | 3,000 | 7,500 | ~1,500,000 SMS a month (one login every ~20 days per active user) at $0.002-0.005 each |
| **Total** | **24,500** | **125,000** | |

About ₹2,352,000-₹12,000,000 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **A solo developer**: backend: Node.js + NestJS -> Go (net/http, chi or Gin); hosting: AWS EKS (Kubernetes) -> AWS ECS on Fargate
  - Why backend changes: Low ops burden moved the gap 2.2 points toward Go (net/http, chi or Gin) (Go (net/http, chi or Gin) 5.0/5 vs Node.js + NestJS 4.0/5, weight 1.0 -> 3.5).
  - Why hosting changes: AWS EKS (Kubernetes) now takes a penalty (Usually needs a team of 4+ to operate), moving the gap 12.0 points toward AWS ECS on Fargate; low ops burden moved the gap 4.3 points toward AWS ECS on Fargate (AWS ECS on Fargate 3.0/5 vs AWS EKS (Kubernetes) 1.0/5, weight 1.0 -> 3.5).
- **Must run on-premises**: hosting: AWS EKS (Kubernetes) -> On-prem Kubernetes (k3s / RKE2 / OpenShift)
  - Why hosting changes: AWS EKS (Kubernetes) is now ruled out: Public-cloud service; deployment must be on-premises.
- **Team has no relevant prior skills**: backend: Node.js + NestJS -> Java/Kotlin + Spring Boot; hosting: AWS EKS (Kubernetes) -> AWS ECS on Fargate
  - Why backend changes: Java/Kotlin + Spring Boot no longer takes a penalty (Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn), moving the gap 14.0 points toward Java/Kotlin + Spring Boot; team skill match moved the gap 10.9 points toward Java/Kotlin + Spring Boot (Java/Kotlin + Spring Boot 3.0/5 vs Node.js + NestJS 3.0/5, weight 3.5 -> 0.0, was 1.5 vs 5.0).
  - Why hosting changes: AWS EKS (Kubernetes) now takes a penalty (Requires platform/DevOps skills your team did not list), moving the gap 8.0 points toward AWS ECS on Fargate; learning curve moved the gap 1.1 points toward AWS ECS on Fargate (AWS ECS on Fargate 3.0/5 vs AWS EKS (Kubernetes) 1.0/5, was 5.0 vs 5.0).

## Next-best complete stacks

- Next.js (React) + Go (net/http, chi or Gin) + PostgreSQL + AWS ECS on Fargate (89.0, +0.4)
- Next.js (React) + Go (net/http, chi or Gin) + PostgreSQL + AWS EKS (Kubernetes) (89.0, +0.4)
- Next.js (React) + Node.js + NestJS + PostgreSQL + AWS ECS on Fargate (88.6, +0.0)

## Sources

- https://nextjs.org/docs
- https://react.dev
- https://survey.stackoverflow.co/2025/technology
- https://web.dev/articles/rendering-on-the-web
- https://nextjs.org/docs/app/getting-started/deploying
- https://docs.nestjs.com/
- https://docs.nestjs.com/websockets/gateways
- https://docs.nestjs.com/microservices/basics
- https://www.postgresql.org/docs/current/
- https://github.com/pgvector/pgvector
- https://www.citusdata.com/
- https://www.pgbouncer.org/
- https://supabase.com/pricing
- https://neon.com/docs/introduction/plans
- https://aiven.io/pricing/postgresql
- https://supabase.com/docs/guides/platform/compute-and-disk
- https://neon.com/pricing
- https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html
- https://aws.amazon.com/eks/pricing/
- https://aws.amazon.com/eks/sla/
- https://aws.amazon.com/compute/sla/
