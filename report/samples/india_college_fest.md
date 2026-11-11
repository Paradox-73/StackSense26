# StackSense recommendation: Synapse Fest (college fest)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Content / blog / marketing (SEO)' project at Small (1k-10k daily users) scale (~2.2 peak req/s) built by 3 engineer(s) in 4 weeks, StackSense recommends Next.js (React) + Serverless functions (Node/Python FaaS) + PostgreSQL + Cloudflare Pages + Workers (architecture: Serverless, event-driven). Estimated infrastructure cost: ₹1,440-₹5,280/month (stretch budget). The highest-scoring stack (Next.js (React) + Supabase (BaaS on Postgres) + PostgreSQL + Vercel, 85.7) is only 0.8 stack points ahead, inside the 1-point tie margin, so StackSense treats it as a tie and chose this stack on a minimum bill that fits your budget.

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Next.js (React)** | 90.8 | 0.4, close call (under 1.5) | Astro (-0.4, tie) |
| Backend | **Serverless functions (Node/Python FaaS)** | 77.4 | -0.2, close call (under 1.5) | Supabase (BaaS on Postgres) (+0.2, tie) |
| Database | **PostgreSQL** | 80.2 | 0.5, close call (under 1.5) | MySQL (-0.5, tie) |
| Hosting | **Cloudflare Pages + Workers** | 87.2 | -0.7, close call (under 1.5) | Vercel (+0.7, tie) |

Stack score: **84.9** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Serverless, event-driven**: Request-scoped functions scale to zero and remove server management; keep functions small and stateless. Sized for ~2.2 requests/s at peak, about 14 GB of data within 12 months and a 99% availability target.

Availability approach: The platform runs the functions across zones, with no instances for you to run; daily database backups

### How the parts fit

1. **Request path**: The browser loads Next.js (React) from Cloudflare Pages + Workers; it sends API calls to functions on Cloudflare Pages + Workers, one invocation per request (~2.2 requests/s at peak).
2. **Sign-in**: Sign-in uses Clerk / Auth0 / framework built-in auth; each function checks the token on every request.
3. **Data**: PostgreSQL is the system of record (about 14 GB within 12 months); uploaded files go to Cloudflare R2 (+ Cloudflare CDN). Card and bank details never reach your servers: the payment provider's hosted checkout or SDK collects them, and you store only its tokens.
4. **Deploy**: A git push builds the app; Cloudflare Pages + Workers deploys it with a preview URL per pull request. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Small (1k-10k daily users) (peak ~2.2 req/s, derived); database tier: Small (10-100 GB of data) (~14 GB in 12 months)
- Budget: ~$21/month (INR converted at a fixed planning rate of 96 INR = 1 USD (an assumption; check the FBIL reference rate for today's value).)
- Assumption: compliance = dpdp: DPDP Act 2023 (in force through the DPDP Rules 2025, notified November 2025 and phased in over 18 months) allows cross-border transfer except to notified countries, so it adds consent/breach-notice duties but not an India-region filter. Add 'Data must stay in India' if a sector rule (e.g. RBI) applies.

## Per-layer reasoning

### Frontend: Next.js (React) (90.8)

React meta-framework with server rendering, static generation, React Server Components and file-based routing.

Next.js (React) is the frontend for a Content / blog / marketing (SEO) project with about 8,000 daily users (~2.2 requests/s at peak), built by a team of 3 in 4 weeks. Search visibility is marked important (landing/product pages), and it serves full HTML from the server or the build (SEO 5.0/5), so crawlers read the content without running JavaScript. Astro is within 0.4 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

**Why**
- Development speed: 5.0/5 vs 4.0 average for this layer - weighted up because: 4-week MVP: speed dominates.
- Learning curve: 5.0/5 vs 4.1 average for this layer - weighted up because: 4-week MVP: no time to learn new tools; Small team (3).
- SEO: 5.0/5 vs 4.4 average for this layer - weighted up because: SEO important; Content sites live on search.
- Stack synergy (+6): One language across the stack: shared types, shared validation, any developer can work on any layer.
- Team skill match (4.5/5, direct): your team lists React, a direct match for Next.js (React).
- SSR/SSG/ISR give crawlers full HTML (strong SEO, fast LCP)
- Largest React ecosystem and hiring pool
- Same codebase can host API routes / server actions for small apps

**Trade-offs**
- App Router + Server Components add conceptual load
- Some features (ISR, image optimisation, middleware) are smoothest on Vercel

**Risks**
- Next.js runs on Cloudflare through the OpenNext adapter; some features (e.g. certain ISR/image paths) differ from Vercel.

**Versus runner-up:** Next.js (React) and Astro are within 0.4 stack points of each other, inside the 1-point tie margin, so they count as tied. Next.js (React) is stronger on development speed (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0); Astro is stronger on low ops burden (5.0 vs 4.0), performance / latency (5.0 vs 4.0). Choose Astro instead if less to operate matters more to you than development speed. The tie went to Next.js (React) on team skill match (2 vs 1, layers the team already uses). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +27.7
- Time to MVP: +22.2
- Team skills: +11.1
- SEO need: +10.2
- Application type: +8.9
- Team size: +8.2

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| SEO | 5.0 | 3.2 | 16.2 |
| Team skill match | 4.5 | 3.5 | 15.6 |
| Development speed | 5.0 | 3.0 | 15.2 |
| Learning curve | 5.0 | 2.5 | 12.7 |
| Low ops burden | 4.0 | 2.5 | 9.5 |
| Ecosystem maturity | 5.0 | 1.5 | 7.6 |
| Performance / latency | 4.0 | 1.8 | 6.8 |
| Hiring pool | 5.0 | 0.5 | 2.5 |
| Rich client interactivity | 5.0 | 0.5 | 2.5 |
| Structure for large teams | 3.0 | 0.3 | 0.8 |
| Portability (low lock-in) | 4.0 | 0.2 | 0.8 |
| Realtime fit | 3.0 | 0.2 | 0.5 |

**Alternatives**
- Astro (stack 84.5, -0.4): Note: Official adapters/presets deploy this framework to the CDN + functions platform with no server to manage.
- SvelteKit (stack 83.9, -1.0): Note: Official adapters/presets deploy this framework to the CDN + functions platform with no server to manage.

**Why not the others?**
- Why not Astro? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.4 points lower; either is defensible. Next.js (React) is stronger on development speed (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0); Astro is stronger on low ops burden (5.0 vs 4.0), performance / latency (5.0 vs 4.0).
- Why not React SPA (Vite)? (popular choice) Swapping it in lowers the stack score by 1.8 points. Next.js (React) is stronger on SEO (5.0 vs 2.0), development speed (5.0 vs 4.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0).

**Excluded by hard constraints**
- React Native (Expo): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Flutter: Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Native iOS + Android (Swift / Kotlin): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- No frontend (API only): You target a user interface, so a frontend is needed

### Backend: Serverless functions (Node/Python FaaS) (77.4)

Request-scoped functions (AWS Lambda, Vercel/Netlify Functions, Cloud Run functions, Azure Functions).

Serverless functions (Node/Python FaaS) serves the API at about 2.2 requests/s at peak (Small (1k-10k daily users)) for a team of 3. Functions scale per request and cost nothing while idle, which suits ~2.2 requests/s of uneven traffic. Supabase (BaaS on Postgres) is within 0.2 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

**Why**
- Low ops burden: 5.0/5 vs 4.2 average for this layer - weighted up because: Small team (3).
- Learning curve: 4.0/5 vs 3.8 average for this layer - weighted up because: 4-week MVP: no time to learn new tools; Small team (3).
- Scalability: 5.0/5 vs 4.3 average for this layer.
- Stack synergy (+4): Functions deploy natively on this platform's function runtime.
- Stack synergy (+6): One language across the stack: shared types, shared validation, any developer can work on any layer.
- Team skill match (3.5/5, related): nobody listed Serverless functions (Node/Python FaaS), but JavaScript carries over.
- Scale to zero: pay nothing when idle
- No servers to patch; automatic horizontal scaling
- Natural fit for event-driven and spiky workloads

**Trade-offs**
- Cold starts hurt tight latency targets
- No persistent connections (websockets) and execution time limits

**Risks**
- Serverless functions need a pooled/HTTP driver (Neon serverless driver, Supabase pooler, PlanetScale) to avoid connection exhaustion.

**Versus runner-up:** Serverless functions (Node/Python FaaS) and Supabase (BaaS on Postgres) are within 0.2 stack points of each other, inside the 1-point tie margin, so they count as tied. Serverless functions (Node/Python FaaS) is stronger on cost at your scale (5.0 vs 4.6), scalability (5.0 vs 4.0); Supabase (BaaS on Postgres) is stronger on development speed (5.0 vs 4.0), learning curve (5.0 vs 4.0). Choose Supabase (BaaS on Postgres) instead if development speed matters more to you than a lower bill. The tie went to Serverless functions (Node/Python FaaS) on adjacent team skills (16.5 vs 16, summed skill fit). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +27.8
- Time to MVP: +15.7
- Monthly budget: +14.5
- Team size: +9.1
- Team skills: +7.5
- Application type: +2.4

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 4.0 | 19.3 |
| Low ops burden | 5.0 | 2.5 | 12.1 |
| Development speed | 4.0 | 3.0 | 10.9 |
| Team skill match | 3.5 | 3.5 | 10.6 |
| Learning curve | 4.0 | 2.5 | 9.1 |
| Ecosystem maturity | 4.0 | 1.5 | 5.4 |
| Performance / latency | 3.0 | 1.8 | 4.3 |
| Scalability | 5.0 | 0.7 | 3.4 |
| Hiring pool | 4.0 | 0.5 | 1.8 |
| Portability (low lock-in) | 3.0 | 0.2 | 0.5 |
| Realtime fit | 1.0 | 0.2 | 0.0 |
| Structure for large teams | 1.0 | 0.3 | 0.0 |

**Alternatives**
- Supabase (BaaS on Postgres) (stack 85.1, +0.2): Loses: Functions deploy natively on this platform's function runtime. Note: Supabase is a managed Postgres: auth, row-level security, storage and realtime come with the database.
- Node.js + Express (stack 83.2, -1.8): Loses: Functions deploy natively on this platform's function runtime. Note: This framework can be adapted to serverless functions, but you lose in-memory state, background jobs and WebSockets.

**Why not the others?**
- Why not Supabase (BaaS on Postgres)? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.2 points higher; either is defensible. Serverless functions (Node/Python FaaS) is stronger on team skill match (3.5 vs 3.0), cost at your scale (5.0 vs 4.6); Supabase (BaaS on Postgres) is stronger on development speed (5.0 vs 4.0), learning curve (5.0 vs 4.0).
- Why not Firebase (BaaS on Google Cloud)? (highest score in this layer) Swapping it in lowers the stack score by 12.8 points. Serverless functions (Node/Python FaaS) is stronger on team skill match (3.5 vs 3.0), portability (low lock-in) (3.0 vs 1.0); Firebase (BaaS on Google Cloud) is stronger on development speed (5.0 vs 4.0), learning curve (5.0 vs 4.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 1.8 points. Serverless functions (Node/Python FaaS) is stronger on low ops burden (5.0 vs 4.0), scalability (5.0 vs 4.0); Node.js + Express is stronger on team skill match (4.5 vs 3.5), learning curve (5.0 vs 4.0).
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 11.8 points. Serverless functions (Node/Python FaaS) is stronger on team skill match (3.5 vs 1.5), low ops burden (5.0 vs 4.0); Python + Django is stronger on development speed (5.0 vs 4.0), ecosystem maturity (5.0 vs 4.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: PostgreSQL (80.2)

Open-source relational database with ACID transactions, JSONB, full-text search and extensions (PostGIS, pgvector, TimescaleDB).

Your data is mainly relational and reaches about 14 GB within 12 months; PostgreSQL fits relational data 5/5. You need strong consistency, and PostgreSQL gives it: a read after a write always sees that write. Its share of the estimated bill is ₹1,440-₹4,800 a month, against a total budget of ₹2,000 a month. MySQL is within 0.5 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

Suggested offering: Neon / Supabase Postgres connected through Hyperdrive

**Why**
- Data-model fit: 4.7/5 vs 3.9 average for this layer.
- Consistency fit: 5.0/5 vs 4.8 average for this layer - weighted up because: Strong consistency required.
- Learning curve: 5.0/5 vs 4.8 average for this layer - weighted up because: 4-week MVP: no time to learn new tools; Small team (3).
- Team skill match (4.5/5, direct): your team lists SQL, a direct match for PostgreSQL.
- Default choice for relational data: constraints, joins, transactions
- Extensions cover JSON, search, geo, time-series and vectors
- Every cloud offers it managed; zero vendor lock-in

**Trade-offs**
- Single-writer primary: write scale-out needs sharding (Citus) or Aurora Limitless
- Connection-per-process model needs PgBouncer/RDS Proxy under serverless

**Risks**
- Minimum ~$15/month uses most of the budget (-3.5).
- Serverless functions need a pooled/HTTP driver (Neon serverless driver, Supabase pooler, PlanetScale) to avoid connection exhaustion.

**Versus runner-up:** PostgreSQL and MySQL are within 0.5 stack points of each other, inside the 1-point tie margin, so they count as tied. PostgreSQL is stronger on data-model fit (4.7 vs 4.3), realtime fit (3.0 vs 2.0). PostgreSQL has the higher stack score. Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +42.5
- Time to MVP: +9.5
- Team skills: +8.8
- Team size: +6.5
- Consistency need: +6.0
- Application type: +3.0

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.7 | 5.0 | 18.4 |
| Team skill match | 4.5 | 3.5 | 12.3 |
| Learning curve | 5.0 | 2.5 | 10.0 |
| Consistency fit | 5.0 | 2.5 | 10.0 |
| Cost at your scale | 3.1 | 4.0 | 8.6 |
| Low ops burden | 4.0 | 2.5 | 7.5 |
| Ecosystem maturity | 5.0 | 1.5 | 6.0 |
| Performance / latency | 4.0 | 1.8 | 5.4 |
| Scalability | 4.0 | 0.7 | 2.1 |
| Hiring pool | 5.0 | 0.5 | 2.0 |
| Portability (low lock-in) | 5.0 | 0.2 | 0.8 |
| Realtime fit | 3.0 | 0.2 | 0.4 |
| Adjustment: Minimum ~$15/month uses most of the budget | | | -3.5 |

**Alternatives**
- MySQL (stack 84.4, -0.5): Scores 78.3 on its own; its stack is 0.5 stack points behind the pick.
- Microsoft SQL Server (stack 83.3, -1.6): Scores 73.7 on its own; its stack is 1.6 stack points behind the pick.

**Why not the others?**
- Why not MySQL? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.5 points lower; either is defensible. PostgreSQL is stronger on data-model fit (4.7 vs 4.3), realtime fit (3.0 vs 2.0); MySQL takes a penalty: Minimum ~$15/month uses most of the budget.
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 6.7 points. PostgreSQL is stronger on data-model fit (4.7 vs 3.0), consistency fit (5.0 vs 3.5); MongoDB is stronger on scalability (5.0 vs 4.0), realtime fit (4.0 vs 3.0); MongoDB takes a penalty: Only 2/5 fit for your primary 'relational' data.

**Excluded by hard constraints**
- Amazon DynamoDB: Poor fit for 'relational' data as the primary store (1/5)
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: ~14 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your relational, document data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (2/5)
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational, document data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational, document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- Cloud Firestore: Poor fit for 'relational' data as the primary store (1/5)
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Eventually consistent; cannot be the system of record for ACID data

### Hosting: Cloudflare Pages + Workers (87.2)

Edge platform: static hosting with unmetered bandwidth, Workers (V8 isolates) at 300+ locations, Durable Objects for stateful/WebSocket workloads.

Cloudflare Pages + Workers hosts the stack for users in India at a 99% availability target. It serves the pages from a global CDN and runs server code as functions, which covers ~2.2 requests/s at peak without servers to manage. Its share of the estimated bill is ₹0-₹480 a month, against a total budget of ₹2,000 a month. Vercel is within 0.7 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

Runs here: Next.js (server rendering + static files), the serverless functions. The database runs as a separate managed service (see Database).

**Why**
- Cost at your scale: 4.8/5 vs 3.3 average for this layer - weighted up because: Tight budget (~$21/month).
- Low ops burden: 5.0/5 vs 4.0 average for this layer - weighted up because: Small team (3).
- Performance / latency: 5.0/5 vs 4.0 average for this layer - weighted up because: Core Web Vitals affect ranking; Read-heavy: fast reads/caching.
- Stack synergy (+4): Functions deploy natively on this platform's function runtime.
- Team skill match (4.0/5, related): nobody listed Cloudflare Pages + Workers, but JavaScript, React carry over.
- Static assets with no bandwidth charges: cheapest way to serve high-traffic content
- Edge compute close to users everywhere, including Indian PoPs
- Durable Objects give WebSockets/stateful coordination at the edge

**Trade-offs**
- Workers runtime is not full Node.js (some npm packages need polyfills)
- Next.js needs the OpenNext adapter; not every feature is supported

**Risks**
- Serverless functions need a pooled/HTTP driver (Neon serverless driver, Supabase pooler, PlanetScale) to avoid connection exhaustion.
- Next.js runs on Cloudflare through the OpenNext adapter; some features (e.g. certain ISR/image paths) differ from Vercel.

**Versus runner-up:** Cloudflare Pages + Workers and Vercel are within 0.7 stack points of each other, inside the 1-point tie margin, so they count as tied. Cloudflare Pages + Workers is stronger on cost at your scale (4.8 vs 3.6), realtime fit (3.0 vs 2.0); Vercel is stronger on learning curve (5.0 vs 4.0). Choose Vercel instead if a gentler learning curve matters more to you than a lower bill. Cloudflare Pages + Workers stays as part of the stack chosen by the tie-break on a minimum bill that fits your budget. Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +33.1
- Monthly budget: +15.9
- Time to MVP: +10.5
- Team size: +10.5
- Team skills: +10.5
- Application type: +5.6

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 4.8 | 4.0 | 21.2 |
| Team skill match | 4.0 | 3.5 | 14.7 |
| Low ops burden | 5.0 | 2.5 | 14.0 |
| Learning curve | 4.0 | 2.5 | 10.5 |
| Performance / latency | 5.0 | 1.8 | 10.1 |
| Ecosystem maturity | 4.0 | 1.5 | 6.3 |
| Region coverage | 5.0 | 1.0 | 5.6 |
| Scalability | 5.0 | 0.7 | 3.9 |
| Realtime fit | 3.0 | 0.2 | 0.6 |
| Portability (low lock-in) | 3.0 | 0.2 | 0.6 |

**Alternatives**
- Vercel (stack 85.6, +0.7): Note: Vercel builds Next.js: ISR, image optimisation, middleware and preview deploys work with zero configuration.
- Netlify (stack 82.9, -2.0): Scores 75.3 on its own; its stack is 2.0 stack points behind the pick.

**Why not the others?**
- Why not Vercel? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.7 points higher; either is defensible. Cloudflare Pages + Workers is stronger on cost at your scale (4.8 vs 3.6), realtime fit (3.0 vs 2.0); Vercel is stronger on learning curve (5.0 vs 4.0); Vercel takes a penalty: Minimum ~$20/month uses most of the budget.
- Why not AWS ECS on Fargate? (popular choice) Swapping it in lowers the stack score by 17.8 points. Cloudflare Pages + Workers is stronger on team skill match (4.0 vs 1.5), cost at your scale (4.8 vs 2.6); AWS ECS on Fargate is stronger on ecosystem maturity (5.0 vs 4.0), realtime fit (4.0 vs 3.0); AWS ECS on Fargate takes a penalty: Minimum ~$50/month is 2.4x the whole budget.
- Why not Render? (popular choice) Swapping it in lowers the stack score by 13.4 points. Cloudflare Pages + Workers is stronger on team skill match (4.0 vs 1.5), cost at your scale (4.8 vs 3.6); Render is stronger on learning curve (5.0 vs 4.0), portability (low lock-in) (4.0 vs 3.0).

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

- (caveat, -2) Serverless functions need a pooled/HTTP driver (Neon serverless driver, Supabase pooler, PlanetScale) to avoid connection exhaustion.
- (synergy, +4) Functions deploy natively on this platform's function runtime.
- (synergy, +6) One language across the stack: shared types, shared validation, any developer can work on any layer.
- (caveat, -4) Next.js runs on Cloudflare through the OpenNext adapter; some features (e.g. certain ISR/image paths) differ from Vercel.

## Supporting services

- **Search**: Postgres full-text search to start; Meilisearch/Typesense/OpenSearch when facets & typo-tolerance matter: Catalogue/content search with relevance tuning outgrows LIKE queries quickly.
- **Payments**: Razorpay / Cashfree (India) or Stripe with hosted checkout (card tokens): Card data never touches your servers, which keeps your PCI-DSS audit scope to the smallest self-assessment form (SAQ A).
- **Object storage**: Cloudflare R2 (+ Cloudflare CDN): Media and documents belong in object storage, not the database.
- **Authentication**: Clerk / Auth0 / framework built-in auth: Do not hand-roll password storage, MFA or SSO.
- **Observability**: OpenTelemetry instrumentation -> Grafana Cloud / Sentry: Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: Cloudflare Pages + Workers | 0 | 5 | Small (1k-10k daily users) price band |
| Database: PostgreSQL | 15 | 50 | Small (10-100 GB of data) database tier (~14 GB in 12 months) |
| **Total** | **15** | **55** | |

About ₹1,440-₹5,280 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Budget raised to ₹10,000/month (x5)**: hosting: Cloudflare Pages + Workers -> Vercel
  - Why hosting changes: Vercel no longer takes a penalty (Minimum ~$20/month uses most of the budget), moving the gap 2.8 points toward Vercel; learning curve moved the gap 0.3 points toward Vercel (Vercel 5.0/5 vs Cloudflare Pages + Workers 4.0/5).
- **10x fewer users (800 DAU)**: hosting: Cloudflare Pages + Workers -> Netlify
  - Why hosting changes: Cost at your scale moved the gap 6.8 points toward Netlify (Netlify 5.0/5 vs Cloudflare Pages + Workers 5.0/5, was 3.6 vs 4.8); on its own Cloudflare Pages + Workers still scores 2.3 higher, so Netlify wins as part of the whole stack (the other layers changed, and the stack-level compatibility rules or tie-break favour it).
- **Realtime becomes core**: backend: Serverless functions (Node/Python FaaS) -> Supabase (BaaS on Postgres)
  - Why backend changes: Realtime fit moved the gap 9.2 points toward Supabase (BaaS on Postgres) (Supabase (BaaS on Postgres) 4.0/5 vs Serverless functions (Node/Python FaaS) 1.0/5, weight 0.2 -> 3.2).
- **Must run on-premises**: backend: Serverless functions (Node/Python FaaS) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> On-prem VMs + Docker Compose
  - Why backend changes: Serverless functions (Node/Python FaaS) is now ruled out: Needs a managed function platform, unavailable on-premises.
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: Public-cloud service; deployment must be on-premises.
- **Low tolerance for vendor lock-in**: frontend: Next.js (React) -> Astro
  - Why frontend changes: Portability (low lock-in) moved the gap 2.6 points toward Astro (Astro 5.0/5 vs Next.js (React) 4.0/5, weight 0.2 -> 2.5); on its own Next.js (React) still scores 7.8 higher, so Astro wins as part of the whole stack (a stack rule now applies: Official adapters/presets deploy this framework to the CDN + functions platform with no server to manage).
- **HIPAA compliance required**: backend: Serverless functions (Node/Python FaaS) -> Node.js + Express; hosting: Cloudflare Pages + Workers -> AWS Lambda + API Gateway
  - Why backend changes: Low ops burden, where Serverless functions (Node/Python FaaS) leads (5.0/5 vs 4.0/5), counts for less now (share of the total weight fell; gap 0.1 points toward Node.js + Express).
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: No HIPAA Business Associate Agreement available.
- **Data must stay in India**: hosting: Cloudflare Pages + Workers -> AWS Lambda + API Gateway
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: Keeping data and TLS termination inside India or the EU needs the Data Localization Suite, an Enterprise add-on; treated as not meeting a residency rule.

## Next-best complete stacks

- Next.js (React) + Supabase (BaaS on Postgres) + PostgreSQL + Vercel (85.7, +0.8)
- Next.js (React) + Serverless functions (Node/Python FaaS) + PostgreSQL + Vercel (85.6, +0.7)
- Next.js (React) + Serverless functions (Node/Python FaaS) + MySQL + Vercel (85.1, +0.2)

## Sources

- https://nextjs.org/docs
- https://react.dev
- https://survey.stackoverflow.co/2025/technology
- https://web.dev/articles/rendering-on-the-web
- https://nextjs.org/docs/app/getting-started/deploying
- https://docs.aws.amazon.com/lambda/latest/dg/welcome.html
- https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html
- https://vercel.com/docs/functions
- https://www.postgresql.org/docs/current/
- https://github.com/pgvector/pgvector
- https://www.citusdata.com/
- https://www.pgbouncer.org/
- https://supabase.com/pricing
- https://neon.com/docs/introduction/plans
- https://aiven.io/pricing/postgresql
- https://supabase.com/docs/guides/platform/compute-and-disk
- https://neon.com/pricing
- https://developers.cloudflare.com/pages/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/durable-objects/
- https://www.cloudflare.com/trust-hub/compliance-resources/
- https://developers.cloudflare.com/data-localization/region-support/
- https://neon.tech/docs/serverless/serverless-driver
- https://www.typescriptlang.org/docs/
- https://opennext.js.org/cloudflare
