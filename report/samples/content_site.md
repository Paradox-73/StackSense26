# StackSense recommendation: TrailNotes (content)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Content / blog / marketing (SEO)' project at Medium (10k-100k daily users) scale (~5.6 peak req/s) built by 1 engineer(s) in 4 weeks, StackSense recommends Next.js (React) + No server code (static site) + No database (content files in git) + Netlify (architecture: Static site (pre-built pages on a CDN)). Estimated infrastructure cost: $0/month (within budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **Next.js (React)** | 90.6 | 0.5, close call (under 1.5) | Astro (-0.5, tie) |
| Backend | **No server code (static site)** | 100.0 | 3.0, solid (1.5-4 points) | Serverless functions (Node/Python FaaS) (-3.0) |
| Database | **No database (content files in git)** | 91.9 | 8.5, clear (4+ points) | MongoDB (-8.5) |
| Hosting | **Netlify** | 89.8 | 1.2, close call (under 1.5) | Cloudflare Pages + Workers (-1.2) |

Stack score: **93.1** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**Static site (pre-built pages on a CDN)**: Users only read what the team publishes, so every page is built at deploy time and served as files: no server code or database to run, patch or pay for. Add an API or a BaaS when users need to sign in, post or pay. About 20,000 daily users read pages from the CDN.

Availability approach: The CDN serves the pre-built pages from many locations; the git repository is the backup.

### How the parts fit

1. **Request path**: The browser loads Next.js (React) from Netlify's CDN as pre-built pages; there is no API call on the request path, so ~5.6 requests/s at peak are plain file reads.
2. **Sign-in**: No sign-in: everything is public and read-only.
3. **Data**: Content lives as files in the git repository (about 1.1 GB); there is no database.
4. **Deploy**: A git push rebuilds the pages and Netlify publishes them to its CDN.

## Inputs used

- Scale tier: Medium (10k-100k daily users) (peak ~5.6 req/s, derived); database tier: Small (one tier below the traffic: read-heavy, caches absorb most reads) (~1.1 GB in 12 months)
- Budget: ~$20/month
- Defaults used (1): Special workloads = none

## Per-layer reasoning

### Frontend: Next.js (React) (90.6)

React meta-framework with server rendering, static generation, React Server Components and file-based routing.

Next.js (React) is the frontend for a Content / blog / marketing (SEO) project with about 20,000 daily users (~5.6 requests/s at peak), built by a solo developer in 4 weeks. Search visibility is marked critical (organic traffic is the business), and it serves full HTML from the server or the build (SEO 5.0/5), so crawlers read the content without running JavaScript. Astro is within 0.5 stack points, inside the tie margin (stacks this close count as tied); the tie went to Next.js (React) on team skill match (3 vs 2, layers the team already uses).

**Why**
- Development speed: 5.0/5 vs 4.0 average for this layer - weighted up because: 4-week MVP: speed dominates.
- SEO: 5.0/5 vs 4.4 average for this layer - weighted up because: SEO critical; Content sites live on search.
- Learning curve: 5.0/5 vs 4.1 average for this layer - weighted up because: 4-week MVP: no time to learn new tools; Solo developer.
- Team skill match (4.5/5, direct): your team lists React, a direct match for Next.js (React).
- SSR/SSG/ISR give crawlers full HTML (strong SEO, fast LCP)
- Largest React ecosystem and hiring pool
- Same codebase can host API routes / server actions for small apps

**Trade-offs**
- App Router + Server Components add conceptual load
- Some features (ISR, image optimisation, middleware) are smoothest on Vercel

**Versus runner-up:** Next.js (React) and Astro are within 0.5 stack points of each other, inside the 1-point tie margin, so they count as tied. Next.js (React) is stronger on development speed (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0); Astro is stronger on low ops burden (5.0 vs 4.0), performance / latency (5.0 vs 4.0). Choose Astro instead if less to operate matters more to you than development speed. The tie went to Next.js (React) on team skill match (3 vs 2, layers the team already uses). Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +22.7
- Time to MVP: +18.2
- SEO need: +16.7
- Team size: +12.0
- Team skills: +9.1
- Application type: +7.3

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| SEO | 5.0 | 5.2 | 21.7 |
| Team skill match | 4.5 | 3.5 | 12.8 |
| Learning curve | 5.0 | 3.0 | 12.5 |
| Development speed | 5.0 | 3.0 | 12.5 |
| Low ops burden | 4.0 | 3.5 | 10.9 |
| Performance / latency | 4.0 | 2.3 | 7.2 |
| Ecosystem maturity | 5.0 | 1.5 | 6.2 |
| Hiring pool | 5.0 | 0.5 | 2.1 |
| Rich client interactivity | 5.0 | 0.5 | 2.1 |
| Portability (low lock-in) | 4.0 | 0.5 | 1.6 |
| Structure for large teams | 3.0 | 0.3 | 0.6 |
| Realtime fit | 3.0 | 0.2 | 0.4 |

**Alternatives**
- Astro (stack 92.5, -0.5): Note: Official adapters/presets deploy this framework to the CDN + functions platform with no server to manage.
- SvelteKit (stack 91.8, -1.3): Note: Official adapters/presets deploy this framework to the CDN + functions platform with no server to manage.

**Why not the others?**
- Why not Astro? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.5 points lower; either is defensible. Next.js (React) is stronger on development speed (5.0 vs 4.0), ecosystem maturity (5.0 vs 3.0); Astro is stronger on low ops burden (5.0 vs 4.0), performance / latency (5.0 vs 4.0).
- Why not React SPA (Vite)? (popular choice) Swapping it in lowers the stack score by 6.0 points. Next.js (React) is stronger on SEO (5.0 vs 2.0), development speed (5.0 vs 4.0); React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0); React SPA (Vite) takes a penalty: Client-side rendering is a liability when organic search is the business.

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

### Backend: No server code (static site) (100.0)

No API server: the frontend is pre-built into static files at deploy time and served from a CDN.

The site serves about 20,000 daily users read-only, so the pages are built once and served as files: there is no API server to run, patch or pay for. Its strongest weighted criterion for your answers is cost at your scale: 5.0/5 at weight 4.0, the largest share of its score. It leads the runner-up, Serverless functions (Node/Python FaaS), by 3.0 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Learning curve: 5.0/5 vs 3.9 average for this layer - weighted up because: 4-week MVP: no time to learn new tools; Solo developer.
- Performance / latency: 5.0/5 vs 3.8 average for this layer - weighted up because: Core Web Vitals affect ranking; p95 target 200 ms.
- Low ops burden: 5.0/5 vs 4.3 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Bonus +6: Your team already ships No server code (static site) (html listed in team skills).
- If users start to sign in, post or pay: Node.js + Express is the next-best backend that passes your constraints.
- No server to patch, scale or secure: the attack surface is a set of static files
- Free static hosting tiers cover read-only sites well past 100k daily users

**Trade-offs**
- No sign-in, posting, payments or per-user pages: add server code or a BaaS when those arrive
- Contact forms and comments need a third-party service or one serverless function

**Versus runner-up:** No server code (static site) beats Serverless functions (Node/Python FaaS) by 3.0 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team skills (+2.2), general quality (baseline weights) (+1.5), time to mvp (+1.2). Serverless functions (Node/Python FaaS) is stronger on stack compatibility (+2.5), score limit (scores stop at 0 and 100) (+0.7).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +30.0
- Time to MVP: +18.4
- Team skills: +15.2
- Team size: +14.7
- Monthly budget: +12.6
- Application type: +4.2

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 4.0 | 16.8 |
| Low ops burden | 5.0 | 3.5 | 14.7 |
| Team skill match | 4.5 | 3.5 | 12.9 |
| Learning curve | 5.0 | 3.0 | 12.6 |
| Development speed | 5.0 | 3.0 | 12.6 |
| Performance / latency | 5.0 | 2.3 | 9.7 |
| Scalability | 5.0 | 1.5 | 6.3 |
| Ecosystem maturity | 5.0 | 1.5 | 6.3 |
| Hiring pool | 5.0 | 0.5 | 2.1 |
| Portability (low lock-in) | 5.0 | 0.5 | 2.1 |
| Structure for large teams | 3.0 | 0.3 | 0.6 |
| Realtime fit | 1.0 | 0.2 | 0.0 |
| Adjustment: Your team already ships No server code (static site) (html listed in team skills) | | | +6.0 |

**Alternatives**
- Serverless functions (Node/Python FaaS) (stack 90.1, -3.0): Note: Functions deploy natively on this platform's function runtime.
- Node.js + Express (stack 85.4, -7.6): Note: This framework can be adapted to serverless functions, but you lose in-memory state, background jobs and WebSockets.

**Why not the others?**
- Why not Serverless functions (Node/Python FaaS)? (runner-up) Swapping it in lowers the stack score by 3.0 points. No server code (static site) is stronger on performance / latency (5.0 vs 3.0), team skill match (4.5 vs 3.5).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 7.6 points. No server code (static site) is stronger on performance / latency (5.0 vs 3.0), low ops burden (5.0 vs 4.0); Node.js + Express is stronger on realtime fit (4.0 vs 1.0). 3.5 of the 7.6 points come from a stack compatibility rule: This framework can be adapted to serverless functions, but you lose in-memory state, background jobs and WebSockets.
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 42.4 points. No server code (static site) is stronger on team skill match (4.5 vs 1.5), performance / latency (5.0 vs 3.0); Python + Django is stronger on structure for large teams (4.0 vs 3.0), realtime fit (2.0 vs 1.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn. 33.5 of the 42.4 points come from a stack compatibility rule: Netlify Functions run TypeScript and JavaScript; Go runs only in the deprecated Lambda-compatible mode, which accepts no deploys after 1 July 2027, and no other language runs there, so this API cannot run on Netlify. Host it on a container or PaaS service.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 39.2 points. No server code (static site) is stronger on team skill match (4.5 vs 1.5), learning curve (5.0 vs 2.0); Java/Kotlin + Spring Boot is stronger on structure for large teams (5.0 vs 3.0), realtime fit (3.0 vs 1.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn. 27.5 of the 39.2 points come from a stack compatibility rule: Netlify Functions run TypeScript and JavaScript; Go runs only in the deprecated Lambda-compatible mode, which accepts no deploys after 1 July 2027, and no other language runs there, so this API cannot run on Netlify. Host it on a container or PaaS service.

### Database: No database (content files in git) (91.9)

No database server: pages and posts are Markdown or JSON files in the repository, built into static HTML at deploy time.

The content is about 1.1 GB of files kept in git, so there is no database server to run, back up or pay for. Its strongest weighted criterion for your answers is cost at your scale: 5.0/5 at weight 4.0, the largest share of its score. It leads the runner-up, MongoDB, by 8.5 stack points.

Suggested offering: Content files in the git repository, built into static pages at deploy time (no database to run)

**Why**
- Cost at your scale: 5.0/5 vs 3.3 average for this layer - weighted up because: Tight budget (~$20/month).
- Learning curve: 5.0/5 vs 3.7 average for this layer - weighted up because: 4-week MVP: no time to learn new tools; Solo developer.
- Data-model fit: 4.0/5 vs 3.4 average for this layer.
- If users start to sign in, post or pay: Cloud Firestore is the next-best database that passes your constraints.
- Nothing to run, back up or pay for: content is versioned and reviewed in git like code
- Pages are pre-built, so the CDN serves every read with no database round trip

**Trade-offs**
- Only for content the team publishes: as soon as users sign in, post or pay, add a real database
- Every content change needs a rebuild and deploy (seconds to minutes)

**Versus runner-up:** No database (content files in git) beats MongoDB by 8.5 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+5.0), monthly budget (+1.4), team size (+0.8). MongoDB is stronger on general quality (baseline weights) (+0.3).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +39.6
- Team size: +13.2
- Monthly budget: +11.3
- Time to MVP: +9.0
- Team skills: +8.2
- Application type: +3.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 4.0 | 15.1 |
| Data-model fit | 4.0 | 5.0 | 14.2 |
| Low ops burden | 5.0 | 3.5 | 13.2 |
| Team skill match | 4.5 | 3.5 | 11.6 |
| Learning curve | 5.0 | 3.0 | 11.3 |
| Performance / latency | 5.0 | 2.3 | 8.7 |
| Scalability | 5.0 | 1.5 | 5.7 |
| Ecosystem maturity | 5.0 | 1.5 | 5.7 |
| Consistency fit | 4.0 | 1.0 | 2.8 |
| Hiring pool | 5.0 | 0.5 | 1.9 |
| Portability (low lock-in) | 5.0 | 0.5 | 1.9 |
| Realtime fit | 1.0 | 0.2 | 0.0 |

**Alternatives**
- MongoDB (stack 84.6, -8.5): Note: With no server code, nothing can query a database at request time; a static site reads content files at build time.
- Cloud Firestore (stack 83.0, -10.1): Note: Firestore outside Google Cloud adds cross-cloud latency and egress costs.

**Why not the others?**
- Why not MongoDB? (runner-up) Swapping it in lowers the stack score by 8.5 points. No database (content files in git) is stronger on cost at your scale (5.0 vs 3.1), team skill match (4.5 vs 3.5); MongoDB is stronger on data-model fit (5.0 vs 4.0), realtime fit (4.0 vs 1.0). 5.0 of the 8.5 points come from a stack compatibility rule: With no server code, nothing can query a database at request time; a static site reads content files at build time.
- Why not PostgreSQL? (popular choice) Swapping it in lowers the stack score by 11.9 points. No database (content files in git) is stronger on team skill match (4.5 vs 1.5), cost at your scale (5.0 vs 3.3); PostgreSQL is stronger on realtime fit (3.0 vs 1.0). 5.5 of the 11.9 points come from a stack compatibility rule: With no server code, nothing can query a database at request time; a static site reads content files at build time.
- Why not MySQL? (popular choice) Swapping it in lowers the stack score by 16.7 points. No database (content files in git) is stronger on team skill match (4.5 vs 1.5), cost at your scale (5.0 vs 3.3); MySQL is stronger on realtime fit (2.0 vs 1.0); MySQL takes a penalty: Only 3/5 fit for your primary 'document' data. 5.5 of the 16.7 points come from a stack compatibility rule: With no server code, nothing can query a database at request time; a static site reads content files at build time.

**Excluded by hard constraints**
- Redis / Valkey: In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your document data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- ClickHouse: Poor fit for 'document' data as the primary store (1/5)
- OpenSearch / Elasticsearch: Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your document data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.9% availability

### Hosting: Netlify (89.8)

Jamstack platform: CDN hosting, serverless/edge functions, forms, deploy previews.

Netlify hosts the stack for users worldwide at a 99.9% availability target. It serves the pages from a global CDN and runs server code as functions, which covers ~5.6 requests/s at peak without servers to manage. Its share of the estimated bill is $0 a month, against a total budget of $20 a month. It leads the runner-up, Cloudflare Pages + Workers, by 1.2 stack points.

Runs here: Next.js as pre-built static pages. No server code and no database: content files are built into pages at deploy time, and the free static plan covers the traffic.

**Why**
- Cost at your scale: 5.0/5 vs 2.2 average for this layer - weighted up because: Tight budget (~$20/month).
- Learning curve: 5.0/5 vs 3.5 average for this layer - weighted up because: 4-week MVP: no time to learn new tools; Solo developer.
- Low ops burden: 5.0/5 vs 4.3 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Team skill match (3.5/5, related): nobody listed Netlify, but JavaScript carries over.
- Excellent for static/content sites (Astro, Nuxt, SvelteKit)
- Built-in forms, redirects, split testing

**Trade-offs**
- Paid plans bill in credits (Personal $9/month with 1,000 credits, Pro $20/month for unlimited members with 3,000, no per-seat charge) spent on deploys, bandwidth and requests, so the bill follows usage once the credits run out
- Function regions are limited (no India region by default)

**Versus runner-up:** Netlify beats Cloudflare Pages + Workers by 1.2 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+1.0), time to mvp (+0.3), team size (+0.3). Cloudflare Pages + Workers is stronger on team skills (+0.4). Close call: either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +28.6
- Team size: +16.7
- Monthly budget: +14.3
- Time to MVP: +10.1
- Team skills: +7.4
- Application type: +4.8

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 4.0 | 19.1 |
| Low ops burden | 5.0 | 3.5 | 16.7 |
| Learning curve | 5.0 | 3.0 | 14.3 |
| Performance / latency | 5.0 | 2.3 | 10.9 |
| Team skill match | 3.5 | 3.5 | 10.4 |
| Scalability | 5.0 | 1.5 | 7.1 |
| Ecosystem maturity | 4.0 | 1.5 | 5.4 |
| Region coverage | 5.0 | 1.0 | 4.8 |
| Portability (low lock-in) | 3.0 | 0.5 | 1.2 |
| Realtime fit | 1.0 | 0.2 | 0.0 |

**Alternatives**
- Cloudflare Pages + Workers (stack 91.8, -1.2): Note: Next.js runs on Cloudflare through the OpenNext adapter; some features (e.g. certain ISR/image paths) differ from Vercel.
- AWS S3 + CloudFront (static) (stack 91.2, -1.9): Scores 82.4 on its own; its stack is 1.9 stack points behind the pick.

**Why not the others?**
- Why not Cloudflare Pages + Workers? (runner-up) Swapping it in lowers the stack score by 1.2 points. Netlify is stronger on learning curve (5.0 vs 4.0); Cloudflare Pages + Workers is stronger on team skill match (4.0 vs 3.5), realtime fit (3.0 vs 1.0).
- Why not Vercel? (popular choice) Swapping it in lowers the stack score by 3.7 points. Netlify is stronger on cost at your scale (5.0 vs 1.8); Vercel is stronger on team skill match (4.0 vs 3.5), realtime fit (2.0 vs 1.0); Vercel takes a penalty: Minimum ~$40/month is 2.0x the whole budget.
- Why not AWS ECS on Fargate? (popular choice) Swapping it in lowers the stack score by 17.3 points. Netlify is stronger on cost at your scale (5.0 vs 1.4), team skill match (3.5 vs 1.5); AWS ECS on Fargate is stronger on ecosystem maturity (5.0 vs 4.0), realtime fit (4.0 vs 1.0); AWS ECS on Fargate takes a penalty: Usually needs a team of 2+ to operate. 2.0 of the 17.3 points come from a stack compatibility rule: Pre-built pages need only a static file host and its CDN; serving them from containers, functions or a server means building and patching a web-server image and paying for instances to hand out files.
- Why not Render? (popular choice) Swapping it in lowers the stack score by 10.9 points. Netlify is stronger on cost at your scale (5.0 vs 1.8), team skill match (3.5 vs 1.5); Render is stronger on realtime fit (4.0 vs 1.0), portability (low lock-in) (4.0 vs 3.0); Render takes a penalty: Minimum ~$50/month is 2.5x the whole budget.

**Excluded by hard constraints**
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs

## Supporting services

- **Search**: Pagefind (a static search index built at deploy time): Full-text search for a static site with no server: the index ships with the pages.
- **Observability**: An uptime check plus the host's web analytics: With no server code there is nothing to trace; watch that the pages are up and how fast they load.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: Netlify | 0 | 0 | free static plan: pre-built files only |
| **Total** | **0** | **0** | |

About ₹0-₹0 per month. Budget status: **within**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Budget raised to $100/month (x5)**: hosting: Netlify -> Vercel
  - Why hosting changes: Vercel no longer takes a penalty (Minimum ~$40/month is 2.0x the whole budget), moving the gap 7.2 points toward Vercel; team skill match moved the gap 0.2 points toward Vercel (Vercel 4.0/5 vs Netlify 3.5/5); on its own Netlify still scores 2.5 higher, so Vercel wins as part of the whole stack (a stack rule now applies: Vercel builds Next.js: ISR, image optimisation, middleware and preview deploys work with zero configuration).
- **10x more users (200,000 DAU)**: hosting: Netlify -> Cloudflare Pages + Workers
  - Why hosting changes: Cost at your scale moved the gap 3.1 points toward Cloudflare Pages + Workers (Cloudflare Pages + Workers 5.0/5 vs Netlify 4.3/5, was 5.0 vs 5.0).
- **10x fewer users (2,000 DAU)**: hosting: Netlify -> Firebase Hosting (static)
  - Why hosting changes: Cost at your scale, where Netlify leads (5.0/5 vs 3.7/5), counts for less now (share of the total weight fell; gap 10.7 points toward Firebase Hosting (static)); on its own Netlify still scores 3.9 higher, so Firebase Hosting (static) wins as part of the whole stack (the other layers changed, and the stack-level compatibility rules or tie-break favour it).
- **A team of 15 engineers**: hosting: Netlify -> Cloudflare Pages + Workers
  - Why hosting changes: Team skill match moved the gap 1.0 points toward Cloudflare Pages + Workers (Cloudflare Pages + Workers 4.0/5 vs Netlify 3.5/5, weight 3.5 -> 4.5).
- **Realtime becomes core**: backend: No server code (static site) -> Firebase (BaaS on Google Cloud); database: No database (content files in git) -> Cloud Firestore; hosting: Netlify -> Cloudflare Pages + Workers
  - Why backend changes: No server code (static site) is now ruled out: Static files cannot hold live connections; realtime is core.
  - Why database changes: No database (content files in git) is now ruled out: Static files cannot hold live connections; realtime is core.
  - Why hosting changes: Netlify now takes a penalty (Cannot hold persistent realtime connections), moving the gap 8.0 points toward Cloudflare Pages + Workers; realtime fit moved the gap 5.9 points toward Cloudflare Pages + Workers (Cloudflare Pages + Workers 3.0/5 vs Netlify 1.0/5, weight 0.2 -> 3.2).
- **Must run on-premises**: hosting: Netlify -> On-prem VMs + Docker Compose
  - Why hosting changes: Netlify is now ruled out: Public-cloud service; deployment must be on-premises.
- **HIPAA compliance required**: hosting: Netlify -> AWS S3 + CloudFront (static)
  - Why hosting changes: Netlify is now ruled out: No HIPAA Business Associate Agreement available.
- **Data must stay in India**: hosting: Netlify -> AWS S3 + CloudFront (static)
  - Why hosting changes: Netlify is now ruled out: Netlify serves a static site's files from its global edge and keeps hosting, storage and logs with US providers; a function region moves only where functions run (and their durable cache), so only a US residency rule is met for a static site.

## Next-best complete stacks

- Astro + No server code (static site) + No database (content files in git) + Netlify (92.5, -0.5)
- Astro + No server code (static site) + No database (content files in git) + Cloudflare Pages + Workers (92.3, -0.8)
- Next.js (React) + No server code (static site) + No database (content files in git) + Cloudflare Pages + Workers (91.8, -1.2)

## Sources

- https://nextjs.org/docs
- https://react.dev
- https://survey.stackoverflow.co/2025/technology
- https://web.dev/articles/rendering-on-the-web
- https://nextjs.org/docs/app/getting-started/deploying
- https://docs.astro.build/en/guides/deploy/
- https://developers.cloudflare.com/pages/
- https://docs.astro.build/en/guides/content-collections/
- https://developers.cloudflare.com/pages/framework-guides/
- https://docs.netlify.com/
- https://www.netlify.com/pricing/
- https://docs.netlify.com/functions/optional-configuration/
- https://docs.netlify.com/build/caching/caching-overview/
- https://www.netlify.com/legal/subprocessors/
