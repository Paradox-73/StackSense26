# StackSense recommendation: OpsDesk (internal admin)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For an 'Internal tool / admin panel' project at Hobby (<1k daily users) scale (~1.7 peak req/s) built by 1 engineer(s) in 3 weeks, StackSense recommends Server-rendered HTML + HTMX + Python + Django + SQLite (+ Litestream backups) + On-prem VMs + Docker Compose (architecture: Modular monolith). Estimated infrastructure cost: ₹0-₹14,400/month (stretch budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Server-rendered HTML + HTMX** | 84.5 | 3.3, solid (1.5-4 points) | Astro (-3.3) |
| Backend | **Python + Django** | 100.0 | 0.8, close call (under 1.5) | Python + FastAPI (-0.8, tie) |
| Database | **SQLite (+ Litestream backups)** | 91.1 | 3.4, solid (1.5-4 points) | PostgreSQL (-3.4) |
| Hosting | **On-prem VMs + Docker Compose** | 64.1 | 23.5, clear (4+ points) | On-prem Kubernetes (k3s / RKE2 / OpenShift) (-23.5) |

Stack score: **87.7** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Modular monolith**: With 1 engineer(s), one deployable with strict internal module boundaries is the fastest and cheapest to run; modules can be extracted into services later. Sized for ~1.7 requests/s at peak, about 3.4 GB of data within 12 months and a 99% availability target.

Availability approach: Single server + nightly backups copied off the machine

### How the parts fit

1. **Request path**: The browser requests pages that the Python + Django service renders with Django templates on On-prem VMs + Docker Compose (HTMX swaps in HTML fragments); ~1.7 requests/s at peak, each answered from SQLite (+ Litestream backups).
2. **Sign-in**: Sign-in uses Keycloak (self-hosted); the Python + Django API checks the session or token on every request.
3. **Data**: SQLite (+ Litestream backups) is the system of record (about 3.4 GB within 12 months).
4. **Deploy**: CI builds container images; Docker Compose pulls them and restarts the services on your servers. Database schema changes run as versioned migrations before the new code serves traffic.

## Inputs used

- Scale tier: Hobby (<1k daily users) (peak ~1.7 req/s, derived); database tier: Hobby (<1k daily users) (~3.4 GB in 12 months)
- Budget: ~$0/month (INR converted at a fixed planning rate of 96 INR = 1 USD (an assumption; check the FBIL reference rate for today's value).)
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Per-layer reasoning

### Frontend: Server-rendered HTML + HTMX (84.5)

HTML rendered by the backend (Django/Rails/Phoenix/Go templates) with HTMX attributes for partial page updates; no SPA build step.

Server-rendered HTML + HTMX is the frontend for an Internal tool / admin panel project with about 200 daily users (~1.7 requests/s at peak), built by a solo developer in 3 weeks. Its strongest weighted criterion for your answers is low ops burden: 5.0/5 at weight 3.5, the largest share of its score. It leads the runner-up, Astro, by 3.3 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Learning curve: 5.0/5 vs 3.7 average for this layer - weighted up because: 3-week MVP: no time to learn new tools; Solo developer.
- Low ops burden: 5.0/5 vs 4.4 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Portability (low lock-in): 5.0/5 vs 4.7 average for this layer - weighted up because: Low lock-in tolerance.
- Stack synergy (+5): The backend renders HTML fragments directly: one codebase, no API layer or SPA build.
- Team skill match (4.5/5, direct): your team lists HTML/CSS, a direct match for Server-rendered HTML + HTMX.
- One codebase, one language; no JS build pipeline
- Excellent for CRUD internal tools and admin panels
- Pages are real HTML, so SEO is free

**Trade-offs**
- Rich client interactions (drag-drop editors, offline) get awkward
- Requires a server-rendering backend; does not pair with BaaS

**Versus runner-up:** Server-rendered HTML + HTMX beats Astro by 3.3 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+1.2), time to mvp (+0.8), team skills (+0.8).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +21.9
- Time to MVP: +19.7
- Team size: +17.8
- Team skills: +11.1
- Lock-in tolerance: +10.2
- Application type: +3.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Low ops burden | 5.0 | 3.5 | 17.8 |
| Team skill match | 4.5 | 3.5 | 15.6 |
| Learning curve | 5.0 | 3.0 | 15.2 |
| Development speed | 4.0 | 4.0 | 15.2 |
| Portability (low lock-in) | 5.0 | 2.5 | 12.7 |
| Ecosystem maturity | 3.0 | 1.0 | 2.5 |
| Performance / latency | 4.0 | 0.5 | 1.9 |
| Hiring pool | 3.0 | 0.5 | 1.3 |
| SEO | 5.0 | 0.2 | 1.0 |
| Rich client interactivity | 2.0 | 0.5 | 0.6 |
| Structure for large teams | 2.0 | 0.3 | 0.4 |
| Realtime fit | 2.0 | 0.2 | 0.2 |

**Alternatives**
- Astro (stack 84.4, -3.3): Loses: The backend renders HTML fragments directly: one codebase, no API layer or SPA build.
- React SPA (Vite) (stack 83.3, -4.4): Loses: The backend renders HTML fragments directly: one codebase, no API layer or SPA build.

**Why not the others?**
- Why not Astro? (runner-up) Swapping it in lowers the stack score by 3.3 points. Server-rendered HTML + HTMX is stronger on team skill match (4.5 vs 3.5), learning curve (5.0 vs 4.0); Astro is stronger on performance / latency (5.0 vs 4.0), structure for large teams (3.0 vs 2.0). 1.2 of the 3.3 points come from a stack compatibility rule: The backend renders HTML fragments directly: one codebase, no API layer or SPA build.
- Why not Next.js (React)? (popular choice) Swapping it in lowers the stack score by 7.5 points. Server-rendered HTML + HTMX is stronger on team skill match (4.5 vs 1.5), learning curve (5.0 vs 3.0); Next.js (React) is stronger on development speed (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0); Next.js (React) takes a penalty: No search visibility needed: server rendering adds a Node.js server for pages that React SPA (Vite) serves as static files. 1.3 of the 7.5 points come from a stack compatibility rule: The backend renders HTML fragments directly: one codebase, no API layer or SPA build.
- Why not React SPA (Vite)? (popular choice) Swapping it in lowers the stack score by 4.4 points. Server-rendered HTML + HTMX is stronger on team skill match (4.5 vs 1.5), learning curve (5.0 vs 4.0); React SPA (Vite) is stronger on ecosystem maturity (5.0 vs 3.0), rich client interactivity (5.0 vs 2.0). 1.2 of the 4.4 points come from a stack compatibility rule: The backend renders HTML fragments directly: one codebase, no API layer or SPA build.

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

### Backend: Python + Django (100.0)

Batteries-included Python web framework: ORM, migrations, admin, auth, forms, templates.

Python + Django serves the API at about 1.7 requests/s at peak (Hobby (<1k daily users)) for a solo developer. The team lists Django and Python, so it needs no new server language (team skill match 5.0/5). It runs as a long-running Python service, so background jobs and database connection pools live in one deployable process. Python + FastAPI is within 0.8 stack points, inside the tie margin (stacks this close count as tied); the tie went to Python + Django on adjacent team skills (18.5 vs 18, summed skill fit).

**Why**
- Learning curve: 5.0/5 vs 3.7 average for this layer - weighted up because: 3-week MVP: no time to learn new tools; Solo developer.
- Development speed: 5.0/5 vs 4.3 average for this layer - weighted up because: 3-week MVP: speed dominates; Internal tools are CRUD-heavy.
- Low ops burden: 4.0/5 vs 3.8 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Bonus +6: Your team already ships Python + Django (django, python listed in team skills).
- Bonus +4: Generated admin/CRUD scaffolding fits internal tools.
- Stack synergy (+5): The backend renders HTML fragments directly: one codebase, no API layer or SPA build.
- Team skill match (5.0/5, direct): your team lists Django, Python, a direct match for Python + Django.
- Auto-generated admin UI: an internal tool in days
- Mature security defaults (CSRF, SQL injection, XSS protection)
- Proven at very large scale (Instagram)

**Trade-offs**
- Sync-first ORM; async support is partial

**Versus runner-up:** Python + Django and Python + FastAPI are within 0.8 stack points of each other, inside the 1-point tie margin, so they count as tied. Python + Django is stronger on ecosystem maturity (5.0 vs 4.0), structure for large teams (4.0 vs 2.0); Python + FastAPI is stronger on performance / latency (4.0 vs 3.0), realtime fit (3.0 vs 2.0). Choose Python + FastAPI instead if raw speed matters more to you than a mature ecosystem. The tie went to Python + Django on adjacent team skills (18.5 vs 18, summed skill fit). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +25.6
- Time to MVP: +18.0
- Monthly budget: +16.0
- Team skills: +16.0
- Team size: +11.5
- Application type: +10.0

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 5.5 | 22.0 |
| Development speed | 5.0 | 4.0 | 16.0 |
| Team skill match | 5.0 | 3.5 | 14.0 |
| Learning curve | 5.0 | 3.0 | 12.0 |
| Low ops burden | 4.0 | 3.5 | 10.5 |
| Portability (low lock-in) | 5.0 | 2.5 | 10.0 |
| Ecosystem maturity | 5.0 | 1.0 | 4.0 |
| Scalability | 4.0 | 0.5 | 1.5 |
| Hiring pool | 4.0 | 0.5 | 1.5 |
| Performance / latency | 3.0 | 0.5 | 1.0 |
| Structure for large teams | 4.0 | 0.3 | 0.9 |
| Realtime fit | 2.0 | 0.2 | 0.2 |
| Adjustment: Your team already ships Python + Django (django, python listed in team skills) | | | +6.0 |
| Adjustment: Generated admin/CRUD scaffolding fits internal tools | | | +4.0 |

**Alternatives**
- Python + FastAPI (stack 86.9, -0.8): Scores 97.0 on its own; its stack is 0.8 stack points behind the pick.
- PHP + Laravel (stack 85.0, -2.7): Scores 89.3 on its own; its stack is 2.7 stack points behind the pick.

**Why not the others?**
- Why not Python + FastAPI? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.8 points lower; either is defensible. Python + Django is stronger on team skill match (5.0 vs 4.5), ecosystem maturity (5.0 vs 4.0); Python + FastAPI is stronger on performance / latency (4.0 vs 3.0), realtime fit (3.0 vs 2.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 7.7 points. Python + Django is stronger on team skill match (5.0 vs 1.5), development speed (5.0 vs 4.0); Node.js + Express is stronger on hiring pool (5.0 vs 4.0), realtime fit (4.0 vs 2.0); Node.js + Express takes a penalty: Nobody on the team listed Node.js or a closely related skill: a new server language to learn.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 11.3 points. Python + Django is stronger on team skill match (5.0 vs 1.5), learning curve (5.0 vs 2.0); Java/Kotlin + Spring Boot is stronger on hiring pool (5.0 vs 4.0), performance / latency (4.0 vs 3.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- Serverless functions (Node/Python FaaS): Needs a managed function platform, unavailable on-premises
- Firebase (BaaS on Google Cloud): Managed-only BaaS cannot run on-premises; Proprietary API with the highest lock-in; you asked for low lock-in
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: SQLite (+ Litestream backups) (91.1)

Embedded, serverless SQL database in a single file; replicate with Litestream or use Turso/libSQL.

Your data is mainly relational and reaches about 3.4 GB within 12 months; SQLite (+ Litestream backups) fits relational data 4/5. You need strong consistency, and SQLite (+ Litestream backups) gives it: a read after a write always sees that write. Its share of the estimated bill is ₹0 a month, against a total budget of ₹0 a month. It leads the runner-up, PostgreSQL, by 3.4 stack points.

Suggested offering: SQLite file on local disk with Litestream backups

**Why**
- Cost at your scale: 5.0/5 vs 3.8 average for this layer - weighted up because: Zero budget: free tiers only; Internal tools rarely justify spend.
- Low ops burden: 5.0/5 vs 4.2 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Portability (low lock-in): 5.0/5 vs 4.3 average for this layer - weighted up because: Low lock-in tolerance.
- Stack synergy (+6): A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.
- Team skill match (4.5/5, direct): your team lists SQL, a direct match for SQLite (+ Litestream backups).
- Zero cost, zero ops; perfect for prototypes, single-server apps and on-device storage
- In-process reads are extremely fast

**Trade-offs**
- Single writer; does not suit multi-instance or serverless deployments without Turso/LiteFS
- No built-in network access control

**Versus runner-up:** SQLite (+ Litestream backups) beats PostgreSQL by 3.4 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on monthly budget (+2.3), stack compatibility (+1.5), team size (+0.6). PostgreSQL is stronger on general quality (baseline weights) (+1.4).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +34.1
- Monthly budget: +14.2
- Team size: +12.4
- Time to MVP: +8.4
- Team skills: +7.8
- Lock-in tolerance: +7.1

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 5.5 | 19.5 |
| Data-model fit | 4.0 | 5.0 | 13.3 |
| Low ops burden | 5.0 | 3.5 | 12.4 |
| Team skill match | 4.5 | 3.5 | 10.9 |
| Learning curve | 5.0 | 3.0 | 10.6 |
| Portability (low lock-in) | 5.0 | 2.5 | 8.9 |
| Consistency fit | 5.0 | 2.5 | 8.9 |
| Ecosystem maturity | 5.0 | 1.0 | 3.5 |
| Performance / latency | 5.0 | 0.5 | 1.8 |
| Hiring pool | 4.0 | 0.5 | 1.3 |
| Scalability | 1.0 | 0.5 | 0.0 |
| Realtime fit | 1.0 | 0.2 | 0.0 |

**Alternatives**
- PostgreSQL (stack 84.3, -3.4): Loses: A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.
- MySQL (stack 84.3, -3.4): Loses: A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.

**Why not the others?**
- Why not PostgreSQL? (runner-up) Swapping it in lowers the stack score by 3.4 points. SQLite (+ Litestream backups) is stronger on cost at your scale (5.0 vs 4.1), low ops burden (5.0 vs 4.0); PostgreSQL is stronger on data-model fit (5.0 vs 4.0), scalability (4.0 vs 1.0); PostgreSQL takes a penalty: No free option at your scale (from ~$5/month). 1.5 of the 3.4 points come from a stack compatibility rule: A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.
- Why not MySQL? (popular choice) Swapping it in lowers the stack score by 3.4 points. SQLite (+ Litestream backups) is stronger on cost at your scale (5.0 vs 4.1), low ops burden (5.0 vs 4.0); MySQL is stronger on data-model fit (5.0 vs 4.0), scalability (4.0 vs 1.0); MySQL takes a penalty: No free option at your scale (from ~$5/month). 1.5 of the 3.4 points come from a stack compatibility rule: A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.
- Why not MongoDB? (popular choice) Swapping it in lowers the stack score by 15.6 points. SQLite (+ Litestream backups) is stronger on team skill match (4.5 vs 1.5), data-model fit (4.0 vs 2.0); MongoDB is stronger on scalability (5.0 vs 1.0), realtime fit (4.0 vs 1.0); MongoDB takes a penalty: No free option at your scale (from ~$8/month). 1.5 of the 15.6 points come from a stack compatibility rule: A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.

**Excluded by hard constraints**
- Amazon DynamoDB: Managed-only cloud database cannot run on-premises; Poor fit for 'relational' data as the primary store (1/5); Proprietary API with the highest lock-in; you asked for low lock-in
- Redis / Valkey: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your relational data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- Apache Cassandra / ScyllaDB: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5)
- ClickHouse: Eventually consistent; cannot be the system of record for ACID data
- OpenSearch / Elasticsearch: Eventually consistent; cannot be the system of record for ACID data; Poor fit for 'relational' data as the primary store (1/5); Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your relational data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your relational data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- Cloud Firestore: Managed-only cloud database cannot run on-premises; Poor fit for 'relational' data as the primary store (1/5); Proprietary API with the highest lock-in; you asked for low lock-in
- No database (content files in git): Only for read-only sites; your users sign in, post or pay; Poor fit for 'relational' data as the primary store (1/5)
- Google BigQuery: Managed-only cloud database cannot run on-premises; Eventually consistent; cannot be the system of record for ACID data

### Hosting: On-prem VMs + Docker Compose (64.1)

Your own servers or private data centre running containers with Compose/systemd and a reverse proxy.

On-prem VMs + Docker Compose hosts the stack for users in India at a 99% availability target. It runs the Python + Django API as long-running processes, sized for ~1.7 requests/s at peak. Its share of the estimated bill is ₹0-₹14,400 a month, against a total budget of ₹0 a month. It leads the runner-up, On-prem Kubernetes (k3s / RKE2 / OpenShift), by 23.5 stack points.

Runs here: Server-rendered HTML + HTMX (server rendering + static files), the Python + Django API as long-running processes. The database is SQLite, an embedded single-file database: one file on this host's disk that the Python + Django process opens directly, with no separate database server (copy the file to object storage for backups).

**Why**
- Learning curve: 5.0/5 vs 3.0 average for this layer - weighted up because: 3-week MVP: no time to learn new tools; Solo developer.
- Cost at your scale: 2.0/5 vs 1.5 average for this layer - weighted up because: Zero budget: free tiers only; Internal tools rarely justify spend.
- Low ops burden: 2.0/5 vs 1.5 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Bonus +2: Simple long-running deploy suits a monolith.
- Stack synergy (+6): A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.
- Team skill match (4.5/5, direct): your team lists Linux admin, a direct match for On-prem VMs + Docker Compose.
- Full data control; simplest on-prem option for small teams
- Easy to move to Kubernetes later (same images)

**Trade-offs**
- Cost at your scale is only 2.0/5 (weight 5.5).
- Low ops burden is only 2.0/5 (weight 3.5).
- Manual scaling and failover
- Hardware capex + sysadmin time

**Versus runner-up:** On-prem VMs + Docker Compose beats On-prem Kubernetes (k3s / RKE2 / OpenShift) by 23.5 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on monthly budget (+10.2), stack compatibility (+7.5), team size (+6.4). On-prem Kubernetes (k3s / RKE2 / OpenShift) is stronger on score limit (scores stop at 0 and 100) (+6.5).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +18.9
- Time to MVP: +11.2
- Team skills: +10.3
- Lock-in tolerance: +9.4
- Team size: +7.7
- Monthly budget: +4.6

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Team skill match | 4.5 | 3.5 | 14.4 |
| Learning curve | 5.0 | 3.0 | 14.2 |
| Portability (low lock-in) | 5.0 | 2.5 | 11.8 |
| Cost at your scale | 2.0 | 5.5 | 6.3 |
| Region coverage | 5.0 | 1.0 | 4.7 |
| Low ops burden | 2.0 | 3.5 | 4.1 |
| Ecosystem maturity | 4.0 | 1.0 | 3.5 |
| Performance / latency | 4.0 | 0.5 | 1.8 |
| Realtime fit | 4.0 | 0.2 | 0.7 |
| Scalability | 2.0 | 0.5 | 0.6 |
| Adjustment: Simple long-running deploy suits a monolith | | | +2.0 |

**Alternatives**
- On-prem Kubernetes (k3s / RKE2 / OpenShift) (stack 64.1, -23.5): Loses: A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite. Note: SQLite is a single local file; ephemeral or multi-instance platforms lose or fork it. Use a hosted SQLite service (Turso, Cloudflare D1) or a server database.

**Why not the others?**
- Why not On-prem Kubernetes (k3s / RKE2 / OpenShift)? (runner-up) Swapping it in lowers the stack score by 23.5 points. On-prem VMs + Docker Compose is stronger on learning curve (5.0 vs 1.0), cost at your scale (2.0 vs 1.0); On-prem Kubernetes (k3s / RKE2 / OpenShift) is stronger on scalability (4.0 vs 2.0); On-prem Kubernetes (k3s / RKE2 / OpenShift) takes a penalty: Usually needs a team of 5+ to operate. 7.5 of the 23.5 points come from a stack compatibility rule: SQLite is a single local file; ephemeral or multi-instance platforms lose or fork it. Use a hosted SQLite service (Turso, Cloudflare D1) or a server database.
- Why not Vercel? (popular choice) Ruled out for your answers: Public-cloud service; deployment must be on-premises.
- Why not AWS ECS on Fargate? (popular choice) Ruled out for your answers: Public-cloud service; deployment must be on-premises.
- Why not Render? (popular choice) Ruled out for your answers: Public-cloud service; deployment must be on-premises.

**Excluded by hard constraints**
- Vercel: Public-cloud service; deployment must be on-premises
- Netlify: Public-cloud service; deployment must be on-premises
- Cloudflare Pages + Workers: Public-cloud service; deployment must be on-premises
- Render: Public-cloud service; deployment must be on-premises
- Railway: Public-cloud service; deployment must be on-premises
- Fly.io: Public-cloud service; deployment must be on-premises
- AWS ECS on Fargate: Public-cloud service; deployment must be on-premises
- AWS EKS (Kubernetes): Public-cloud service; deployment must be on-premises
- AWS Lambda + API Gateway: Public-cloud service; deployment must be on-premises
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay; Public-cloud service; deployment must be on-premises
- Firebase Hosting (static): Only for read-only sites; your users sign in, post or pay; Public-cloud service; deployment must be on-premises
- Google Cloud Storage + Cloud CDN (static): Only for read-only sites; your users sign in, post or pay; Public-cloud service; deployment must be on-premises
- Azure Static Web Apps: Only for read-only sites; your users sign in, post or pay; Public-cloud service; deployment must be on-premises
- Azure Blob Storage + Front Door (static): Only for read-only sites; your users sign in, post or pay; Public-cloud service; deployment must be on-premises
- Google Cloud Run: Public-cloud service; deployment must be on-premises
- Google Kubernetes Engine (Autopilot): Public-cloud service; deployment must be on-premises
- Azure App Service / Container Apps: Public-cloud service; deployment must be on-premises
- DigitalOcean (App Platform + Managed DBs): Public-cloud service; deployment must be on-premises
- Hetzner Cloud / VPS (Docker, Coolify): Public-cloud service; deployment must be on-premises
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs; Public-cloud service; deployment must be on-premises
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs; Public-cloud service; deployment must be on-premises
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs; Public-cloud service; deployment must be on-premises

## Stack compatibility checks

- (synergy, +5) The backend renders HTML fragments directly: one codebase, no API layer or SPA build.
- (synergy, +6) A persistent volume plus Litestream/LiteFS gives backups and replicas for SQLite.

## Supporting services

- **Background jobs**: A jobs table in SQLite polled by a worker: Send emails, process uploads and call slow APIs outside the request path. On a $0 budget the jobs table lives in your database, so no Redis instance is needed; add Celery with a Redis broker (or RQ / Dramatiq) on Redis when job volume outgrows it.
- **Authentication**: Keycloak (self-hosted): Do not hand-roll password storage, MFA or SSO.
- **Observability**: OpenTelemetry instrumentation -> self-hosted Grafana + Prometheus + Loki + Tempo (the same stack on-premises and in the cloud): Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: On-prem VMs + Docker Compose | 0 | 150 | Hobby (<1k daily users) price band |
| Database: SQLite (+ Litestream backups) | 0 | 0 | Hobby (<1k daily users) database tier (~3 GB in 12 months) |
| **Total** | **0** | **150** | |

About ₹0-₹14,400 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Team has no relevant prior skills**: frontend: Server-rendered HTML + HTMX -> React SPA (Vite); backend: Python + Django -> Node.js + Express
  - Why frontend changes: Team skill match moved the gap 13.3 points toward React SPA (Vite) (React SPA (Vite) 3.0/5 vs Server-rendered HTML + HTMX 3.0/5, weight 3.5 -> 0.0, was 1.5 vs 4.5).
  - Why backend changes: Node.js + Express no longer takes a penalty (Nobody on the team listed Node.js or a closely related skill: a new server language to learn), moving the gap 14.0 points toward Node.js + Express; team skill match moved the gap 12.2 points toward Node.js + Express (Node.js + Express 3.0/5 vs Python + Django 3.0/5, weight 3.5 -> 0.0, was 1.5 vs 5.0); on its own Python + Django still scores 2.4 higher, so Node.js + Express wins as part of the whole stack (a stack rule now applies: One language across the stack: shared types, shared validation, any developer can work on any layer).

## Next-best complete stacks

- Server-rendered HTML + HTMX + Python + FastAPI + SQLite (+ Litestream backups) + On-prem VMs + Docker Compose (86.9, -0.8)
- Server-rendered HTML + HTMX + PHP + Laravel + SQLite (+ Litestream backups) + On-prem VMs + Docker Compose (85.0, -2.7)
- Server-rendered HTML + HTMX + Ruby on Rails + SQLite (+ Litestream backups) + On-prem VMs + Docker Compose (84.6, -3.0)

## Sources

- https://htmx.org/docs/
- https://htmx.org/essays/hypermedia-driven-applications/
- https://docs.djangoproject.com/
- https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- https://channels.readthedocs.io/
- https://www.sqlite.org/whentouse.html
- https://litestream.io/
- https://docs.turso.tech/
- https://docs.docker.com/compose/
- https://docs.docker.com/engine/security/
- https://fly.io/docs/litefs/
