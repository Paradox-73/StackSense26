# StackSense recommendation: PixelArena (multiplayer)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Realtime chat / collaboration / multiplayer' project at Large (100k-1M daily users) scale (~3,472 peak req/s) built by 4 engineer(s) in 16 weeks, StackSense recommends React SPA (Vite) + Go (net/http, chi or Gin) + MongoDB + Fly.io (architecture: Modular monolith). Estimated infrastructure cost: $1,325-$4,800/month (stretch budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **React SPA (Vite)** | 76.2 | 1.4, close call (under 1.5) | Next.js (React) (-1.4) |
| Backend | **Go (net/http, chi or Gin)** | 94.0 | 5.2, clear (4+ points) | Node.js + Express (-5.2) |
| Database | **MongoDB** | 78.3 | no runner-up | - |
| Hosting | **Fly.io** | 88.4 | 4.2, clear (4+ points) | AWS ECS on Fargate (-4.2) |

Stack score: **86.2** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Modular monolith**: With 4 engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later. Sized for ~3,472 requests/s at peak, about 170 GB of data within 12 months and a 99.9% availability target.

Availability approach: 2+ app instances behind a load balancer, managed DB with automated failover

### How the parts fit

1. **Request path**: The browser loads React SPA (Vite) from Fly.io; it sends API calls to the Go service on Fly.io (~3,472 requests/s at peak), which queries MongoDB.
2. **Sign-in**: Sign-in uses Auth0; the Go API checks the session or token on every request.
3. **Data**: MongoDB is the system of record (about 170 GB within 12 months).
4. **Deploy**: CI builds a container image and rolls it out on Fly.io with health checks and zero-downtime restarts. MongoDB keeps no fixed schema: new code reads both the old and the new document shape during a rollout, and backfills that rewrite old documents run as versioned scripts (indexes and validation rules ship the same way).

## Inputs used

- Scale tier: Large (100k-1M daily users) (peak ~3,472 req/s, derived); database tier: Large (100k-1M daily users) (~170 GB in 12 months)
- Budget: ~$2,000/month
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Warnings and how they were resolved

- **[WARNING] 50 ms target for users worldwide**: The stack as shown runs its API and MongoDB in one region. A round trip between continents alone takes ~85 ms (US East - West Europe) to ~170-225 ms (Southeast Asia - Europe or US East), measured between cloud regions (https://learn.microsoft.com/en-us/azure/networking/azure-network-latency), so users far from that region miss a 50 ms target before any work is done. *Resolution:* Deploy the API in a region per continent with read replicas (or a multi-region database for writes), cache reads at the edge (CDN or edge functions), or treat the target as per-region.
- **[INFO] Fly.io publishes no uptime SLA**: Your 99.9% target rests on the app alone: Fly.io commits to no uptime figure and owes no credit when it is down. *Resolution:* Alert on an external uptime check and keep a fallback ready (a second region or provider); pick a host with a published SLA if the target is contractual.

## Per-layer reasoning

### Frontend: React SPA (Vite) (76.2)

Client-rendered single-page React app built with Vite; deploys as static files to any CDN.

React SPA (Vite) is the frontend for a Realtime chat / collaboration / multiplayer project with about 200,000 daily users (~3,472 requests/s at peak), built by a team of 4 in 16 weeks. Search visibility is marked not needed (behind login), so rendering in the browser is acceptable, and it scores 5.0/5 for rich, app-like interaction. It leads the runner-up, Next.js (React), by 1.4 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Rich client interactivity: 5.0/5 vs 4.1 average for this layer - weighted up because: App-like realtime UI; Realtime UIs update without page loads.
- Realtime fit: 3.0/5 vs 2.6 average for this layer - weighted up because: Realtime is core to the product; Collaboration/multiplayer.
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer.
- Team skill match (4.5/5, direct): your team lists React, a direct match for React SPA (Vite).
- Static build: cheapest and simplest hosting
- Huge component ecosystem (dashboards, charts, admin UIs)
- No server to operate for the UI

**Trade-offs**
- Client-side rendering hurts SEO and first paint on slow phones
- Routing, data fetching and state are your own architecture decisions

**Versus runner-up:** React SPA (Vite) beats Next.js (React) by 1.4 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on seo need (+2.0), lock-in tolerance (+0.6), team size (+0.1). Next.js (React) is stronger on latency target (+0.7), general quality (baseline weights) (+0.3). Close call: either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +24.6
- Realtime needs: +13.0
- Team skills: +10.3
- Application type: +9.4
- Lock-in tolerance: +9.4
- Latency target: +5.9

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Rich client interactivity | 5.0 | 3.0 | 14.2 |
| Portability (low lock-in) | 5.0 | 2.5 | 11.8 |
| Team skill match | 4.5 | 2.5 | 10.3 |
| Realtime fit | 3.0 | 4.2 | 9.9 |
| Performance / latency | 3.0 | 4.0 | 9.4 |
| Low ops burden | 5.0 | 1.5 | 7.1 |
| Ecosystem maturity | 5.0 | 1.0 | 4.7 |
| Development speed | 4.0 | 1.0 | 3.5 |
| Learning curve | 5.0 | 0.5 | 2.4 |
| Hiring pool | 5.0 | 0.5 | 2.4 |
| Structure for large teams | 2.0 | 0.3 | 0.3 |
| SEO | 2.0 | 0.2 | 0.2 |

**Alternatives**
- Next.js (React) (stack 84.8, -1.4): Scores 70.5 on its own; its stack is 1.4 stack points behind the pick.
- SvelteKit (stack 84.6, -1.6): Scores 69.9 on its own; its stack is 1.6 stack points behind the pick.

**Why not the others?**
- Why not Next.js (React)? (runner-up) Swapping it in lowers the stack score by 1.4 points. React SPA (Vite) is stronger on portability (low lock-in) (5.0 vs 4.0), low ops burden (5.0 vs 4.0); Next.js (React) is stronger on performance / latency (4.0 vs 3.0), development speed (5.0 vs 4.0); Next.js (React) takes a penalty: No search visibility needed: server rendering adds a Node.js server for pages that React SPA (Vite) serves as static files.

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

### Backend: Go (net/http, chi or Gin) (94.0)

Compiled, statically typed language with built-in concurrency; ships as a single static binary.

Go (net/http, chi or Gin) serves the API at about 3,472 requests/s at peak (Large (100k-1M daily users)) for a team of 4. The team lists Go, so it needs no new server language (team skill match 4.5/5). It runs as a long-running Go service, so background jobs, WebSockets and database connection pools live in one deployable process. Realtime is core, and it scores 4.0/5 on realtime fit. It leads the runner-up, Node.js + Express, by 5.2 stack points.

**Why**
- Performance / latency: 5.0/5 vs 3.7 average for this layer - weighted up because: p95 target 50 ms; Large (100k-1M daily users).
- Realtime fit: 4.0/5 vs 3.3 average for this layer - weighted up because: Realtime is core to the product; Collaboration/multiplayer.
- Scalability: 5.0/5 vs 4.2 average for this layer - weighted up because: Large (100k-1M daily users).
- Bonus +6: Your team already ships Go (net/http, chi or Gin) (go listed in team skills).
- Stack synergy (+4): Tiny static binaries give near-instant cold starts on scale-to-zero platforms.
- Team skill match (4.5/5, direct): your team lists Go, a direct match for Go (net/http, chi or Gin).
- High throughput per core and low memory means fewer servers
- Goroutines handle many concurrent connections (telemetry, websockets)
- Single binary, tiny container images, fast cold starts

**Trade-offs**
- More code for CRUD than Rails/Django
- Smaller web-framework ecosystem

**Versus runner-up:** Go (net/http, chi or Gin) beats Node.js + Express by 5.2 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team skills (+1.5), latency target (+1.4), stack compatibility (+1.0).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +28.9
- Team skills: +16.2
- Realtime needs: +12.8
- Latency target: +11.6
- Scale (DAU / peak RPS): +9.3
- Lock-in tolerance: +9.3

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Performance / latency | 5.0 | 4.0 | 18.6 |
| Realtime fit | 4.0 | 4.2 | 14.7 |
| Scalability | 5.0 | 2.5 | 11.6 |
| Portability (low lock-in) | 5.0 | 2.5 | 11.6 |
| Team skill match | 4.5 | 2.5 | 10.2 |
| Low ops burden | 5.0 | 1.5 | 7.0 |
| Cost at your scale | 5.0 | 1.0 | 4.7 |
| Ecosystem maturity | 4.0 | 1.0 | 3.5 |
| Learning curve | 5.0 | 0.5 | 2.3 |
| Development speed | 3.0 | 1.0 | 2.3 |
| Hiring pool | 3.0 | 0.5 | 1.2 |
| Structure for large teams | 2.0 | 0.3 | 0.3 |
| Adjustment: Your team already ships Go (net/http, chi or Gin) (go listed in team skills) | | | +6.0 |

**Alternatives**
- Node.js + Express (stack 81.0, -5.2): Loses: Tiny static binaries give near-instant cold starts on scale-to-zero platforms.
- Node.js + NestJS (stack 80.9, -5.3): Loses: Tiny static binaries give near-instant cold starts on scale-to-zero platforms.

**Why not the others?**
- Why not Node.js + Express? (runner-up) Swapping it in lowers the stack score by 5.2 points. Go (net/http, chi or Gin) is stronger on performance / latency (5.0 vs 3.0), scalability (5.0 vs 4.0); Node.js + Express is stronger on hiring pool (5.0 vs 3.0), ecosystem maturity (5.0 vs 4.0). 1.0 of the 5.2 points come from a stack compatibility rule: Tiny static binaries give near-instant cold starts on scale-to-zero platforms.
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 11.6 points. Go (net/http, chi or Gin) is stronger on realtime fit (4.0 vs 2.0), performance / latency (5.0 vs 3.0); Python + Django is stronger on development speed (5.0 vs 3.0), ecosystem maturity (5.0 vs 4.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn. 1.0 of the 11.6 points come from a stack compatibility rule: Tiny static binaries give near-instant cold starts on scale-to-zero platforms.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 9.5 points. Go (net/http, chi or Gin) is stronger on team skill match (4.5 vs 1.5), realtime fit (4.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on hiring pool (5.0 vs 3.0), ecosystem maturity (5.0 vs 4.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn. 1.0 of the 9.5 points come from a stack compatibility rule: Tiny static binaries give near-instant cold starts on scale-to-zero platforms.

**Excluded by hard constraints**
- Firebase (BaaS on Google Cloud): Proprietary API with the highest lock-in; you asked for low lock-in
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: MongoDB (78.3)

Document database with flexible schemas, multi-document transactions, change streams and built-in sharding.

Your data is mainly key-value and reaches about 170 GB within 12 months; MongoDB fits key-value data 4/5. The workload is write-heavy, and its write scaling scores 4/5. Realtime is core, and it can push changes to clients (realtime fit 4.0/5). Its share of the estimated bill is $750-$1,500 a month, against a total budget of $2,000 a month.

Suggested offering: MongoDB Atlas (runs on AWS, GCP or Azure in the same region as your compute)

**Why**
- Realtime fit: 4.0/5 vs 2.4 average for this layer - weighted up because: Realtime is core to the product; Collaboration/multiplayer.
- Data-model fit: 4.2/5 vs 3.6 average for this layer - weighted up because: Write-heavy: the storage engine must match the workload.
- Scalability: 5.0/5 vs 4.5 average for this layer - weighted up because: Large (100k-1M daily users).
- Team skill match (3.5/5, related): nobody listed MongoDB, but TypeScript carries over.
- Flexible schema for catalogues, user-generated content, varied payloads
- Native horizontal sharding and time-series collections
- Change streams for realtime feeds

**Trade-offs**
- Joins and cross-entity reporting are weaker than SQL
- Schema discipline moves into application code

**Risks**
- MongoDB Atlas (runs on AWS, GCP or Azure in the same region as your compute) is a separate service from Fly.io: create it in the cloud region where Fly.io runs your app, or every query crosses between regions.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +36.5
- Realtime needs: +9.7
- Scale (DAU / peak RPS): +6.9
- Latency target: +6.9
- Team skills: +5.7
- Lock-in tolerance: +5.5

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.2 | 6.0 | 17.8 |
| Realtime fit | 4.0 | 4.2 | 11.6 |
| Performance / latency | 4.0 | 4.0 | 11.0 |
| Scalability | 5.0 | 2.5 | 9.2 |
| Portability (low lock-in) | 4.0 | 2.5 | 6.9 |
| Team skill match | 3.5 | 2.5 | 5.7 |
| Low ops burden | 4.0 | 1.5 | 4.1 |
| Ecosystem maturity | 5.0 | 1.0 | 3.7 |
| Consistency fit | 4.5 | 1.0 | 3.2 |
| Cost at your scale | 3.4 | 1.0 | 2.2 |
| Learning curve | 4.0 | 0.5 | 1.4 |
| Hiring pool | 4.0 | 0.5 | 1.4 |

**Why not the others?**
- Why not PostgreSQL? (popular choice) Swapping it in lowers the stack score by 2.8 points. MongoDB is stronger on team skill match (3.5 vs 1.5), realtime fit (4.0 vs 3.0); PostgreSQL is stronger on portability (low lock-in) (5.0 vs 4.0), hiring pool (5.0 vs 4.0).
- Why not MySQL? (popular choice) Swapping it in lowers the stack score by 4.3 points. MongoDB is stronger on realtime fit (4.0 vs 2.0), team skill match (3.5 vs 1.5); MySQL is stronger on portability (low lock-in) (5.0 vs 4.0), hiring pool (5.0 vs 4.0).

**Excluded by hard constraints**
- Amazon DynamoDB: Proprietary API with the highest lock-in; you asked for low lock-in
- Redis / Valkey: In-memory store: ~170 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your document data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- OpenSearch / Elasticsearch: Write-heavy load at Large (100k-1M daily users) on a store that fits 'key_value' data 2/5 with write scaling 4/5; Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your key value, document data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Poor fit for 'key_value' data as the primary store (1/5); Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your key value, document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Write-heavy load at Large (100k-1M daily users) on a store that fits 'key_value' data 4/5 with write scaling 1/5; Single-node file database: no failover, so it cannot meet 99.9% availability; One writer at a time for the whole file: 30.0M+ requests a day at Large (100k-1M daily users) is past the 1M a day SQLite's own guide says it has been shown to handle
- Cloud Firestore: Write-heavy load at Large (100k-1M daily users) on a store that fits 'key_value' data 4/5 with write scaling 2/5; Proprietary API with the highest lock-in; you asked for low lock-in
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Write-heavy load at Large (100k-1M daily users) on a store that fits 'key_value' data 4/5 with write scaling 1/5

### Hosting: Fly.io (88.4)

Runs Docker images as Firecracker micro-VMs close to users in many regions, with Anycast networking.

Fly.io hosts the stack for users worldwide at a 99.9% availability target. It runs the Go API as long-running processes with WebSockets, sized for ~3,472 requests/s at peak. Its share of the estimated bill is $375-$1,800 a month, against a total budget of $2,000 a month. It leads the runner-up, AWS ECS on Fargate, by 4.2 stack points.

Runs here: React SPA (static files), the Go API as long-running processes. The database runs as a separate managed service (see Database).

**Why**
- Realtime fit: 5.0/5 vs 3.5 average for this layer - weighted up because: Realtime is core to the product; Collaboration/multiplayer.
- Performance / latency: 5.0/5 vs 4.0 average for this layer - weighted up because: p95 target 50 ms; Large (100k-1M daily users).
- Region coverage: 5.0/5 vs 4.1 average for this layer - weighted up because: 50 ms target: servers must sit near users; Core realtime: every round trip is felt.
- Stack synergy (+4): Anycast + multi-region VMs keep websocket round-trips short for global users.
- Stack synergy (+4): Tiny static binaries give near-instant cold starts on scale-to-zero platforms.
- Team skill match (4.5/5, direct): your team lists Docker, a direct match for Fly.io.
- Multi-region deploys with one command; great for realtime/websockets

**Trade-offs**
- No India region (Singapore is closest); the region list has none in India
- More hands-on than Render/Railway

**Versus runner-up:** Fly.io beats AWS ECS on Fargate by 4.2 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+2.0), realtime needs (+1.0), latency target (+0.7). AWS ECS on Fargate is stronger on scale (dau / peak rps) (+0.3), general quality (baseline weights) (+0.1).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +24.5
- Realtime needs: +15.8
- Latency target: +15.8
- Team skills: +9.8
- Scale (DAU / peak RPS): +7.3
- Lock-in tolerance: +6.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Realtime fit | 5.0 | 4.2 | 18.9 |
| Performance / latency | 5.0 | 4.0 | 18.0 |
| Region coverage | 5.0 | 2.5 | 11.3 |
| Team skill match | 4.5 | 2.5 | 9.8 |
| Scalability | 4.0 | 2.5 | 8.4 |
| Portability (low lock-in) | 4.0 | 2.5 | 8.4 |
| Low ops burden | 4.0 | 1.5 | 5.1 |
| Cost at your scale | 4.5 | 1.0 | 3.9 |
| Learning curve | 5.0 | 0.5 | 2.2 |
| Ecosystem maturity | 3.0 | 1.0 | 2.2 |

**Alternatives**
- AWS ECS on Fargate (stack 82.0, -4.2): Loses: Anycast + multi-region VMs keep websocket round-trips short for global users.
- Azure App Service (stack 81.5, -4.7): Loses: Anycast + multi-region VMs keep websocket round-trips short for global users.

**Why not the others?**
- Why not AWS ECS on Fargate? (runner-up) Swapping it in lowers the stack score by 4.2 points. Fly.io is stronger on realtime fit (5.0 vs 4.0), performance / latency (5.0 vs 4.0); AWS ECS on Fargate is stronger on scalability (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0). 2.0 of the 4.2 points come from a stack compatibility rule: Anycast + multi-region VMs keep websocket round-trips short for global users.
- Why not Vercel? (popular choice) Swapping it in lowers the stack score by 8.3 points. Fly.io is stronger on realtime fit (5.0 vs 2.0), portability (low lock-in) (4.0 vs 3.0); Vercel is stronger on scalability (5.0 vs 4.0), low ops burden (5.0 vs 4.0). 5.0 of the 8.3 points come from a stack compatibility rule: This framework can be adapted to serverless functions, but you lose in-memory state, background jobs and WebSockets.
- Why not Render? (popular choice) Swapping it in lowers the stack score by 7.2 points. Fly.io is stronger on performance / latency (5.0 vs 3.0), region coverage (5.0 vs 2.0); Render is stronger on low ops burden (5.0 vs 4.0). 2.0 of the 7.2 points come from a stack compatibility rule: Anycast + multi-region VMs keep websocket round-trips short for global users.

**Excluded by hard constraints**
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay
- Firebase Hosting (static): Only for read-only sites; your users sign in, post or pay
- Google Cloud Storage + Cloud CDN (static): Only for read-only sites; your users sign in, post or pay
- Azure Static Web Apps: Only for read-only sites; your users sign in, post or pay
- Azure Blob Storage + Front Door (static): Only for read-only sites; your users sign in, post or pay
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs

## Stack compatibility checks

- (synergy, +4) Anycast + multi-region VMs keep websocket round-trips short for global users.
- (synergy, +4) Tiny static binaries give near-instant cold starts on scale-to-zero platforms.

## Supporting services

- **Cache**: Redis/Valkey (Upstash Redis on Fly): Read-heavy traffic, a tight latency target or hot key-value data: keep hot reads and sessions in memory in front of a durable primary database.
- **Realtime**: Redis pub/sub for cross-instance fan-out (Upstash Redis on Fly): With several app instances, a message published on one must reach sockets on all others.
- **Collaboration sync**: Yjs shared documents (CRDTs) synced over the WebSocket connection, with Hocuspocus or y-websocket as the sync server: Many people editing one document at once need conflict-free merging; CRDTs merge concurrent edits without locks, and the server stores snapshots, not every stroke.
- **Ingestion buffer**: Redpanda/Kafka or NATS JetStream: A durable log absorbs write bursts and keeps device ingestion separate from database writes, and lets you replay messages.
- **Authentication**: Auth0: Do not hand-roll password storage, MFA or SSO.
- **Observability**: OpenTelemetry instrumentation -> Grafana Cloud: Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: Fly.io | 375 | 1,800 | Large (100k-1M daily users) price band; x1.5 for 99.9% availability (redundant instances) |
| Database: MongoDB | 750 | 1,500 | Large (100k-1M daily users) database tier (~170 GB in 12 months); upper end for ~170 GB of data: the band's top is priced for the largest data of the tier; x1.5 for 99.9% availability (standby/replicas) |
| Cache: Redis / Valkey | 200 | 1,500 | Large (100k-1M daily users) price band (the app's scale) |
| **Total** | **1,325** | **4,800** | |

About ₹127,200-₹460,800 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **SEO becomes critical**: frontend: React SPA (Vite) -> Next.js (React)
  - Why frontend changes: React SPA (Vite) now takes a penalty (Client-side rendering is a liability when organic search is the business), moving the gap 18.0 points toward Next.js (React); SEO moved the gap 11.8 points toward Next.js (React) (Next.js (React) 5.0/5 vs React SPA (Vite) 2.0/5, weight 0.2 -> 4.2).
- **Must run on-premises**: hosting: Fly.io -> On-prem VMs + Docker Compose
  - Why hosting changes: Fly.io is now ruled out: Public-cloud service; deployment must be on-premises.
- **Data must stay in India**: hosting: Fly.io -> AWS ECS on Fargate
  - Why hosting changes: Fly.io is now ruled out: No India region; data must stay in India.
- **Team has no relevant prior skills**: backend: Go (net/http, chi or Gin) -> C# + ASP.NET Core
  - Why backend changes: C# + ASP.NET Core no longer takes a penalty (Nobody on the team listed C# or a closely related skill: a new server language to learn), moving the gap 14.0 points toward C# + ASP.NET Core; team skill match moved the gap 8.7 points toward C# + ASP.NET Core (C# + ASP.NET Core 3.0/5 vs Go (net/http, chi or Gin) 3.0/5, weight 2.5 -> 0.0, was 1.5 vs 4.5).

## Next-best complete stacks

- Next.js (React) + Go (net/http, chi or Gin) + MongoDB + Fly.io (84.8, -1.4)
- SvelteKit + Go (net/http, chi or Gin) + MongoDB + Fly.io (84.6, -1.6)
- Angular + Go (net/http, chi or Gin) + MongoDB + Fly.io (84.2, -2.0)

## Sources

- https://react.dev
- https://vite.dev/guide/
- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- https://go.dev/doc/
- https://go.dev/doc/effective_go#concurrency
- https://pkg.go.dev/net/http
- https://www.mongodb.com/docs/manual/
- https://www.mongodb.com/docs/manual/core/transactions/
- https://www.mongodb.com/pricing
- https://www.mongodb.com/docs/manual/core/timeseries-collections/
- https://fly.io/docs/
- https://docs.fly.io/about/pricing
- https://fly.io/docs/reference/regions/
- https://fly.io/docs/elixir/
- https://fly.io/docs/laravel/
- https://fly.io/docs/networking/
- https://cloud.google.com/run/docs/tips/general
