# StackSense recommendation: Invoicely (B2B SaaS MVP)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'B2B / B2C SaaS' project at Hobby (<1k daily users) scale (~4.3 peak req/s) built by 2 engineer(s) in 8 weeks, StackSense recommends Next.js (React) + Supabase (BaaS on Postgres) + PostgreSQL + Cloudflare Pages + Workers (architecture: BaaS-first (managed backend + thin server-side functions)). Estimated infrastructure cost: $26/month (within budget). The stack that would otherwise be chosen (Next.js (React) + Supabase (BaaS on Postgres) + PostgreSQL + Vercel, 86.8) has a minimum of about $66/month, above your budget of $50/month; this stack keeps its backend and database, scores 1.8 stack points lower and fits the budget (about $26/month), so it was chosen (a stack that fits is preferred when it is within 5 points).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Next.js (React)** | 88.0 | 0.4, close call (under 1.5) | React SPA (Vite) (-0.4, tie) |
| Backend | **Supabase (BaaS on Postgres)** | 79.9 | 1.0, close call (under 1.5) | Serverless functions (Node/Python FaaS) (-1.0) |
| Database | **PostgreSQL** | 87.9 | 13.8, clear (4+ points) | MySQL (-13.8) |
| Hosting | **Cloudflare Pages + Workers** | 84.2 | -1.8, close call (under 1.5) | Vercel (+1.8) |

Stack score: **85.0** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**BaaS-first (managed backend + thin server-side functions)**: A backend-as-a-service covers auth, data access and realtime; put custom logic in a few functions until it outgrows them. Sized for ~4.3 requests/s at peak, about 14 GB of data within 12 months and a 99.9% availability target.

Availability approach: Supabase runs the backend on a paid plan; turn on point-in-time recovery and check the plan's uptime commitment

### How the parts fit

1. **Request path**: The browser loads Next.js (React) from Cloudflare Pages + Workers; it calls Supabase's API directly through the client SDK (~4.3 requests/s at peak), and Supabase's access rules decide what each user may read or write.
2. **Sign-in**: Supabase Auth signs users in and issues tokens; its access rules check the token on every read and write.
3. **Data**: PostgreSQL is the system of record (about 14 GB within 12 months), run by Supabase.
4. **Deploy**: A git push builds the app; Cloudflare Pages + Workers deploys it with a preview URL per pull request. Schema changes and access rules ship with the Supabase CLI from the same repository.

## Inputs used

- Scale tier: Hobby (<1k daily users) (peak ~4.3 req/s, derived); database tier: Small (10-100 GB of data) (~14 GB in 12 months)
- Budget: ~$50/month
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Per-layer reasoning

### Frontend: Next.js (React) (88.0)

React meta-framework with server rendering, static generation, React Server Components and file-based routing.

Next.js (React) is the frontend for a B2B / B2C SaaS project with about 500 daily users (~4.3 requests/s at peak), built by a team of 2 in 8 weeks. Search visibility is marked important (landing/product pages), and it serves full HTML from the server or the build (SEO 5.0/5), so crawlers read the content without running JavaScript. React SPA (Vite) is within 0.4 stack points, inside the tie margin (stacks this close count as tied); the tie went to Next.js (React) on your most important inputs (SEO need: 2.7 vs 0.7 stack points, the heaviest answer on which they differ).

**Why**
- Development speed: 5.0/5 vs 4.0 average for this layer - weighted up because: 8-week MVP.
- Ecosystem maturity: 5.0/5 vs 4.0 average for this layer - weighted up because: Regulated workload.
- Learning curve: 5.0/5 vs 4.1 average for this layer - weighted up because: 8-week MVP; Small team (2).
- Team skill match (4.5/5, direct): your team lists React, a direct match for Next.js (React).
- SSR/SSG/ISR give crawlers full HTML (strong SEO, fast LCP)
- Largest React ecosystem and hiring pool
- Same codebase can host API routes / server actions for small apps

**Trade-offs**
- App Router + Server Components add conceptual load
- Some features (ISR, image optimisation, middleware) are smoothest on Vercel

**Risks**
- Next.js runs on Cloudflare through the OpenNext adapter; some features (e.g. certain ISR/image paths) differ from Vercel.

**Versus runner-up:** Next.js (React) and React SPA (Vite) are within 0.4 stack points of each other, inside the 1-point tie margin, so they count as tied. Next.js (React) is stronger on SEO (5.0 vs 2.0), development speed (5.0 vs 4.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0). Choose React SPA (Vite) instead if less to operate matters more to you than search traffic. The tie went to Next.js (React) on your most important inputs (SEO need: 2.7 vs 0.7 stack points, the heaviest answer on which they differ). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +29.9
- Time to MVP: +13.1
- Team skills: +12.0
- SEO need: +11.0
- Team size: +8.9
- Application type: +5.5

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 4.5 | 3.5 | 16.8 |
| SEO | 5.0 | 2.2 | 12.1 |
| Development speed | 5.0 | 2.0 | 11.0 |
| Low ops burden | 4.0 | 2.5 | 10.3 |
| Learning curve | 5.0 | 1.5 | 8.2 |
| Ecosystem maturity | 5.0 | 1.5 | 8.2 |
| Rich client interactivity | 5.0 | 1.5 | 8.2 |
| Performance / latency | 4.0 | 1.0 | 4.1 |
| Realtime fit | 3.0 | 1.2 | 3.3 |
| Hiring pool | 5.0 | 0.5 | 2.8 |
| Portability (low lock-in) | 4.0 | 0.5 | 2.1 |
| Structure for large teams | 3.0 | 0.3 | 0.8 |

**Alternatives**
- React SPA (Vite) (stack 84.7, -0.4): Note: Static build output is served directly from a global CDN.
- Nuxt (Vue) (stack 84.4, -0.6): Note: Official adapters/presets deploy this framework to the CDN + functions platform with no server to manage.

**Why not the others?**
- Why not React SPA (Vite)? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.4 points lower; either is defensible. Next.js (React) is stronger on SEO (5.0 vs 2.0), development speed (5.0 vs 4.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0).

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

### Backend: Supabase (BaaS on Postgres) (79.9)

Open-source backend-as-a-service: Postgres, auth, row-level security, storage, realtime, edge functions.

Supabase (BaaS on Postgres) serves the API at about 4.3 requests/s at peak (Hobby (<1k daily users)) for a team of 2. As a hosted backend it supplies sign-in, the database API and file storage, so a team of 2 only needs to write the business rules in the 8 weeks available. Its share of the estimated bill is $26 a month, against a total budget of $50 a month. It leads the runner-up, Serverless functions (Node/Python FaaS), by 1.0 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Low ops burden: 5.0/5 vs 4.2 average for this layer - weighted up because: Small team (2).
- Learning curve: 5.0/5 vs 3.9 average for this layer - weighted up because: 8-week MVP; Small team (2).
- Development speed: 5.0/5 vs 4.3 average for this layer - weighted up because: 8-week MVP.
- Stack synergy (+4): Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database.
- Team skill match (3.0/5, related): nobody listed Supabase (BaaS on Postgres), but React, SQL, TypeScript carry over.
- Auth + DB + storage + realtime in one service; MVP in days
- It is plain Postgres: no data lock-in, can self-host or migrate
- Row-level security pushes authorization into the database

**Trade-offs**
- Complex business logic ends up in SQL/edge functions
- Free projects pause after inactivity

**Versus runner-up:** Supabase (BaaS on Postgres) beats Serverless functions (Node/Python FaaS) by 1.0 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on realtime needs (+1.1), general quality (baseline weights) (+0.6), time to mvp (+0.4). Serverless functions (Node/Python FaaS) is stronger on stack compatibility (+1.0), team skills (+0.5). Close call: either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +35.3
- Time to MVP: +11.4
- Team size: +11.4
- Monthly budget: +8.2
- Team skills: +7.1
- Realtime needs: +4.3

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Low ops burden | 5.0 | 2.5 | 14.3 |
| Cost at your scale | 4.8 | 2.5 | 13.6 |
| Development speed | 5.0 | 2.0 | 11.4 |
| Team skill match | 3.0 | 3.5 | 10.0 |
| Learning curve | 5.0 | 1.5 | 8.6 |
| Ecosystem maturity | 4.0 | 1.5 | 6.4 |
| Realtime fit | 4.0 | 1.2 | 5.1 |
| Performance / latency | 4.0 | 1.0 | 4.3 |
| Scalability | 4.0 | 0.5 | 2.1 |
| Portability (low lock-in) | 4.0 | 0.5 | 2.1 |
| Hiring pool | 3.0 | 0.5 | 1.4 |
| Structure for large teams | 2.0 | 0.3 | 0.4 |

**Alternatives**
- Serverless functions (Node/Python FaaS) (stack 84.0, -1.0): Loses: Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database. Note: Serverless functions need a pooled/HTTP driver (Neon serverless driver, Supabase pooler, PlanetScale) to avoid connection exhaustion.
- Node.js + Express (stack 83.6, -1.5): Loses: Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database. Note: Serverless functions need a pooled/HTTP driver (Neon serverless driver, Supabase pooler, PlanetScale) to avoid connection exhaustion.

**Why not the others?**
- Why not Serverless functions (Node/Python FaaS)? (runner-up) Swapping it in lowers the stack score by 1.0 points. Supabase (BaaS on Postgres) is stronger on realtime fit (4.0 vs 1.0), development speed (5.0 vs 4.0); Serverless functions (Node/Python FaaS) is stronger on team skill match (3.5 vs 3.0), hiring pool (4.0 vs 3.0).
- Why not Node.js + Express? (highest score in this layer) Swapping it in lowers the stack score by 1.5 points. Supabase (BaaS on Postgres) is stronger on low ops burden (5.0 vs 4.0), development speed (5.0 vs 4.0); Node.js + Express is stronger on team skill match (4.5 vs 3.0), ecosystem maturity (5.0 vs 4.0). A stack compatibility rule costs it 2.5 points, more than the whole gap, while on this layer's own criteria it is 1.0 points ahead: This framework can be adapted to serverless functions, but you lose in-memory state, background jobs and WebSockets.
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 12.8 points. Supabase (BaaS on Postgres) is stronger on team skill match (3.0 vs 1.5), low ops burden (5.0 vs 4.0); Python + Django is stronger on ecosystem maturity (5.0 vs 4.0), structure for large teams (4.0 vs 2.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn. 7.5 of the 12.8 points come from a stack compatibility rule: Frontend platforms run code only as short-lived functions; this framework expects a long-running server. Host the API on a container/PaaS service instead.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 33.9 points. Supabase (BaaS on Postgres) is stronger on team skill match (3.0 vs 1.5), low ops burden (5.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on ecosystem maturity (5.0 vs 4.0), hiring pool (5.0 vs 3.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn. 26.5 of the 33.9 points come from a stack compatibility rule: Cloudflare Workers run JavaScript, TypeScript, Python and Rust; other languages, Go among them, run only compiled to WebAssembly, so a Go (net/http, chi or Gin), Java, .NET, PHP, Elixir or Ruby server needs Cloudflare Containers instead, a separate product on the Workers Paid plan without autoscaling yet.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: PostgreSQL (87.9)

Open-source relational database with ACID transactions, JSONB, full-text search and extensions (PostGIS, pgvector, TimescaleDB).

Your data is mainly relational and reaches about 14 GB within 12 months; PostgreSQL fits relational data 5/5. You need strong consistency, and PostgreSQL gives it: a read after a write always sees that write. It leads the runner-up, MySQL, by 13.8 stack points.

Suggested offering: Included with Supabase (BaaS on Postgres)

**Why**
- Data-model fit: 5.0/5 vs 4.2 average for this layer.
- Consistency fit: 5.0/5 vs 4.7 average for this layer - weighted up because: Strong consistency required.
- Cost at your scale: 3.9/5 vs 3.6 average for this layer - weighted up because: Modest budget (~$50/month).
- Stack synergy (+4): Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database.
- Team skill match (4.5/5, direct): your team lists SQL, a direct match for PostgreSQL.
- Default choice for relational data: constraints, joins, transactions
- Extensions cover JSON, search, geo, time-series and vectors
- Every cloud offers it managed; zero vendor lock-in

**Trade-offs**
- Single-writer primary: write scale-out needs sharding (Citus) or Aurora Limitless
- Connection-per-process model needs PgBouncer/RDS Proxy under serverless

**Versus runner-up:** PostgreSQL beats MySQL by 13.8 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+13.5), realtime needs (+0.3).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +49.3
- Team skills: +9.6
- Team size: +7.2
- Consistency need: +6.6
- Time to MVP: +6.1
- Monthly budget: +4.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 5.0 | 5.0 | 22.0 |
| Team skill match | 4.5 | 3.5 | 13.5 |
| Consistency fit | 5.0 | 2.5 | 11.0 |
| Low ops burden | 4.0 | 2.5 | 8.3 |
| Cost at your scale | 3.9 | 2.5 | 7.9 |
| Learning curve | 5.0 | 1.5 | 6.6 |
| Ecosystem maturity | 5.0 | 1.5 | 6.6 |
| Performance / latency | 4.0 | 1.0 | 3.3 |
| Realtime fit | 3.0 | 1.2 | 2.6 |
| Hiring pool | 5.0 | 0.5 | 2.2 |
| Portability (low lock-in) | 5.0 | 0.5 | 2.2 |
| Scalability | 4.0 | 0.5 | 1.6 |

**Alternatives**
- MySQL (stack 71.2, -13.8): Loses: Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database. Note: Supabase's value comes from its bundled Postgres; a different primary database removes most of its benefits.
- Microsoft SQL Server (stack 70.2, -14.8): Loses: Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database. Note: Supabase's value comes from its bundled Postgres; a different primary database removes most of its benefits.

**Why not the others?**
- Why not MySQL? (runner-up) Swapping it in lowers the stack score by 13.8 points. PostgreSQL is stronger on realtime fit (3.0 vs 2.0). 13.5 of the 13.8 points come from a stack compatibility rule: Supabase's value comes from its bundled Postgres; a different primary database removes most of its benefits.
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 23.4 points. PostgreSQL is stronger on data-model fit (5.0 vs 2.0), consistency fit (5.0 vs 3.5); MongoDB is stronger on realtime fit (4.0 vs 3.0), scalability (5.0 vs 4.0); MongoDB takes a penalty: Only 2/5 fit for your primary 'relational' data. 13.5 of the 23.4 points come from a stack compatibility rule: Supabase's value comes from its bundled Postgres; a different primary database removes most of its benefits.

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5)
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~14 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your relational data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.9% availability
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: Cloudflare Pages + Workers (84.2)

Edge platform: static hosting with unmetered bandwidth, Workers (V8 isolates) at 300+ locations, Durable Objects for stateful/WebSocket workloads.

Cloudflare Pages + Workers hosts the stack for users in North America and Europe at a 99.9% availability target. It serves the pages from a global CDN and runs server code as functions, which covers ~4.3 requests/s at peak without servers to manage. Its share of the estimated bill is $0 a month, against a total budget of $50 a month. It leads the runner-up, Vercel, by 1.8 stack points.

Runs here: Next.js (server rendering + static files). Supabase runs the API, auth and database as its own managed service.

**Why**
- Low ops burden: 5.0/5 vs 4.0 average for this layer - weighted up because: Small team (2).
- Cost at your scale: 5.0/5 vs 4.5 average for this layer - weighted up because: Modest budget (~$50/month).
- Performance / latency: 5.0/5 vs 4.0 average for this layer - weighted up because: p95 target 300 ms.
- Team skill match (4.0/5, related): nobody listed Cloudflare Pages + Workers, but React, TypeScript carry over.
- Static assets with no bandwidth charges: cheapest way to serve high-traffic content
- Edge compute close to users everywhere
- Durable Objects give WebSockets/stateful coordination at the edge

**Trade-offs**
- Workers runtime is not full Node.js (some npm packages need polyfills)
- Next.js needs the OpenNext adapter; not every feature is supported

**Risks**
- Next.js runs on Cloudflare through the OpenNext adapter; some features (e.g. certain ISR/image paths) differ from Vercel.

**Versus runner-up:** Vercel would give a stack 1.8 stack points higher (stack points: points on the 0-100 stack score), but Cloudflare Pages + Workers was kept as part of the stack chosen by the budget rule (a stack whose minimum bill fits your budget is preferred when it scores only a few points lower), mainly on realtime needs (+0.4), monthly budget (+0.4), general quality (baseline weights) (+0.1). Vercel is stronger on stack compatibility (+2.2), team size (+0.2). Close call: either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +38.1
- Team size: +11.9
- Team skills: +11.9
- Monthly budget: +9.6
- Time to MVP: +7.2
- Scale (DAU / peak RPS): -3.2

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 4.0 | 3.5 | 16.7 |
| Cost at your scale | 5.0 | 2.5 | 15.9 |
| Low ops burden | 5.0 | 2.5 | 15.9 |
| Learning curve | 4.0 | 1.5 | 7.2 |
| Ecosystem maturity | 4.0 | 1.5 | 7.2 |
| Performance / latency | 5.0 | 1.0 | 6.4 |
| Region coverage | 5.0 | 1.0 | 6.4 |
| Realtime fit | 3.0 | 1.2 | 3.8 |
| Scalability | 5.0 | 0.5 | 3.2 |
| Portability (low lock-in) | 3.0 | 0.5 | 1.6 |

**Alternatives**
- Vercel (stack 86.8, +1.8): Note: Vercel builds Next.js: ISR, image optimisation, middleware and preview deploys work with zero configuration.
- Netlify (stack 85.0, -0.1): Scores 80.0 on its own; its stack is 0.1 stack points behind the pick.

**Why not the others?**
- Why not Vercel? (runner-up) Swapped into this stack it scores 1.8 points higher, but Cloudflare Pages + Workers stays as part of the stack chosen by the budget rule (a stack whose minimum bill fits your budget is preferred when it scores only a few points lower). Cloudflare Pages + Workers is stronger on cost at your scale (5.0 vs 4.4), realtime fit (3.0 vs 2.0); Vercel is stronger on learning curve (5.0 vs 4.0).
- Why not AWS ECS on Fargate? (popular choice) Swapping it in lowers the stack score by 5.3 points. Cloudflare Pages + Workers is stronger on team skill match (4.0 vs 1.5), low ops burden (5.0 vs 3.0); AWS ECS on Fargate is stronger on ecosystem maturity (5.0 vs 4.0), realtime fit (4.0 vs 3.0).
- Why not Render? (popular choice) Swapping it in lowers the stack score by 2.9 points. Cloudflare Pages + Workers is stronger on team skill match (4.0 vs 1.5), performance / latency (5.0 vs 3.0); Render is stronger on learning curve (5.0 vs 4.0), realtime fit (4.0 vs 3.0).

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

- (synergy, +4) Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database.
- (caveat, -4) Next.js runs on Cloudflare through the OpenNext adapter; some features (e.g. certain ISR/image paths) differ from Vercel.

## Supporting services

- **Realtime**: Built-in realtime of Supabase (BaaS on Postgres): Subscriptions/listeners are provided by the BaaS; no socket server needed.
- **Observability**: OpenTelemetry instrumentation -> Grafana Cloud / Sentry: Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: Cloudflare Pages + Workers | 0 | 0 | Hobby (<1k daily users) price band |
| Backend: Supabase (BaaS on Postgres) (includes its database) | 26 | 26 | plan sized for the larger of traffic (Hobby (<1k daily users)) and ~14 GB of data in 12 months; disk beyond the plan's allowance billed per GB |
| **Total** | **26** | **26** | |

About ₹2,496-₹2,496 per month. Budget status: **within**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Budget cut to $10/month (x0.2)**: backend: Supabase (BaaS on Postgres) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> Render
  - Why backend changes: Supabase (BaaS on Postgres) now takes a penalty (Minimum ~$10/month uses most of the budget), moving the gap 3.1 points toward Node.js + Express; cost at your scale moved the gap 3.1 points toward Node.js + Express (Node.js + Express 5.0/5 vs Supabase (BaaS on Postgres) 4.3/5, weight 2.5 -> 4.0, was 5.0 vs 4.8).
  - Why hosting changes: Team skill match, where Cloudflare Pages + Workers leads (4.0/5 vs 1.5/5), counts for less now (share of the total weight fell; gap 1.2 points toward Render); on its own Cloudflare Pages + Workers still scores 17.0 higher, so Render wins as part of the whole stack (a stack rule now applies: Git-push deploys with managed database add-ons are the shortest path to production for a monolith).
- **Budget raised to $250/month (x5)**: hosting: Cloudflare Pages + Workers -> Vercel
  - Why hosting changes: Cost at your scale, where Cloudflare Pages + Workers leads (5.0/5 vs 4.8/5), counts for less now (share of the total weight fell; gap 1.8 points toward Vercel); on its own Cloudflare Pages + Workers still scores 0.1 higher, so Vercel wins as part of the whole stack (a stack rule now applies: Vercel builds Next.js: ISR, image optimisation, middleware and preview deploys work with zero configuration).
- **A solo developer**: hosting: Cloudflare Pages + Workers -> Vercel
  - Why hosting changes: Learning curve moved the gap 0.5 points toward Vercel (Vercel 5.0/5 vs Cloudflare Pages + Workers 4.0/5, weight 1.5 -> 2.0); on its own Cloudflare Pages + Workers still scores 1.0 higher, so Vercel wins as part of the whole stack (a stack rule now applies: Vercel builds Next.js: ISR, image optimisation, middleware and preview deploys work with zero configuration).
- **A team of 15 engineers**: backend: Supabase (BaaS on Postgres) -> Node.js + NestJS
  - Why backend changes: Supabase (BaaS on Postgres) now takes a penalty (Large teams outgrow BaaS for complex domain logic), moving the gap 6.0 points toward Node.js + NestJS; structure for large teams moved the gap 5.8 points toward Node.js + NestJS (Node.js + NestJS 5.0/5 vs Supabase (BaaS on Postgres) 2.0/5, weight 0.3 -> 1.8).
- **4-week deadline**: hosting: Cloudflare Pages + Workers -> Netlify
  - Why hosting changes: Learning curve moved the gap 1.4 points toward Netlify (Netlify 5.0/5 vs Cloudflare Pages + Workers 4.0/5, weight 1.5 -> 2.5); on its own Cloudflare Pages + Workers still scores 2.5 higher, so Netlify wins as part of the whole stack (the other layers changed, and the stack-level compatibility rules or tie-break favour it).
- **Realtime becomes core**: backend: Supabase (BaaS on Postgres) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> Fly.io
  - Why backend changes: Low ops burden, where Supabase (BaaS on Postgres) leads (5.0/5 vs 4.0/5), counts for less now (share of the total weight fell; gap 0.5 points toward Node.js + Express).
  - Why hosting changes: Realtime fit moved the gap 4.7 points toward Fly.io (Fly.io 5.0/5 vs Cloudflare Pages + Workers 3.0/5, weight 1.2 -> 3.2); on its own Cloudflare Pages + Workers still scores 10.9 higher, so Fly.io wins as part of the whole stack (a stack rule now applies: Anycast + multi-region VMs keep websocket round-trips short for global users).
- **Must run on-premises**: backend: Supabase (BaaS on Postgres) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> On-prem VMs + Docker Compose
  - Why backend changes: Low ops burden moved the gap 10.7 points toward Node.js + Express (Node.js + Express 4.0/5 vs Supabase (BaaS on Postgres) 2.0/5, was 4.0 vs 5.0).
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: Public-cloud service; deployment must be on-premises.
- **Low tolerance for vendor lock-in**: backend: Supabase (BaaS on Postgres) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> Google Cloud Run
  - Why backend changes: Portability (low lock-in) moved the gap 2.5 points toward Node.js + Express (Node.js + Express 5.0/5 vs Supabase (BaaS on Postgres) 4.0/5, weight 0.5 -> 2.5).
  - Why hosting changes: Portability (low lock-in) moved the gap 2.7 points toward Google Cloud Run (Google Cloud Run 4.0/5 vs Cloudflare Pages + Workers 3.0/5, weight 0.5 -> 2.5); on its own Cloudflare Pages + Workers still scores 10.9 higher, so Google Cloud Run wins as part of the whole stack (the other layers changed, and the stack-level compatibility rules or tie-break favour it).
- **HIPAA compliance required**: backend: Supabase (BaaS on Postgres) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> Google Cloud Run
  - Why backend changes: Supabase (BaaS on Postgres) now takes a penalty (Minimum ~$584/month is 11.7x the whole budget), moving the gap 17.8 points toward Node.js + Express; cost at your scale moved the gap 11.1 points toward Node.js + Express (Node.js + Express 5.0/5 vs Supabase (BaaS on Postgres) 1.5/5, was 5.0 vs 4.8).
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: No HIPAA Business Associate Agreement available.
- **Data must stay in India**: hosting: Cloudflare Pages + Workers -> AWS Lambda + API Gateway
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: Keeping data and TLS termination inside India or the EU needs the Data Localization Suite, an Enterprise add-on; treated as not meeting a residency rule.
- **Team has no relevant prior skills**: backend: Supabase (BaaS on Postgres) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> Render
  - Why backend changes: Hiring pool moved the gap 7.7 points toward Node.js + Express (Node.js + Express 5.0/5 vs Supabase (BaaS on Postgres) 3.0/5, weight 0.5 -> 3.0).
  - Why hosting changes: Team skill match moved the gap 13.9 points toward Render (Render 3.0/5 vs Cloudflare Pages + Workers 3.0/5, weight 3.5 -> 0.0, was 1.5 vs 4.0); on its own Cloudflare Pages + Workers still scores 2.3 higher, so Render wins as part of the whole stack (a stack rule now applies: Git-push deploys with managed database add-ons are the shortest path to production for a monolith).

## Next-best complete stacks

- Next.js (React) + Supabase (BaaS on Postgres) + PostgreSQL + Vercel (86.8, +1.8)
- Next.js (React) + Serverless functions (Node/Python FaaS) + PostgreSQL + Vercel (85.8, +0.7)
- Next.js (React) + Serverless functions (Node/Python FaaS) + MySQL + Vercel (85.4, +0.4)

## Sources

- https://nextjs.org/docs
- https://react.dev
- https://survey.stackoverflow.co/2025/technology
- https://web.dev/articles/rendering-on-the-web
- https://nextjs.org/docs/app/getting-started/deploying
- https://supabase.com/docs
- https://supabase.com/pricing
- https://supabase.com/docs/guides/security/hipaa-compliance
- https://supabase.com/docs/guides/self-hosting
- https://www.postgresql.org/docs/current/
- https://github.com/pgvector/pgvector
- https://www.citusdata.com/
- https://www.pgbouncer.org/
- https://neon.com/docs/introduction/plans
- https://aiven.io/pricing/postgresql
- https://supabase.com/docs/guides/platform/compute-and-disk
- https://neon.com/pricing
- https://developers.cloudflare.com/pages/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/durable-objects/
- https://www.cloudflare.com/trust-hub/compliance-resources/
- https://developers.cloudflare.com/data-localization/region-support/
- https://supabase.com/docs/guides/database/overview
- https://opennext.js.org/cloudflare
