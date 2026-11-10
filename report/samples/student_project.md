# StackSense recommendation: CampusSwap (student project)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Prototype / student / hackathon' project at Hobby (<1k daily users) scale (~0.1 peak req/s) built by 1 engineer(s) in 2 weeks, StackSense recommends React SPA (Vite) + Firebase (BaaS on Google Cloud) + Cloud Firestore + Vercel (architecture: BaaS-first (managed backend + thin server-side functions)). Estimated infrastructure cost: ₹0/month (within budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **React SPA (Vite)** | 86.3 | 1.2, close call (under 1.5) | Next.js (React) (-1.2) |
| Backend | **Firebase (BaaS on Google Cloud)** | 90.3 | 4.5, clear (4+ points) | Serverless functions (Node/Python FaaS) (-4.5) |
| Database | **Cloud Firestore** | 91.7 | 19.1, clear (4+ points) | MongoDB (-19.1) |
| Hosting | **Vercel** | 90.9 | 0.9, close call (under 1.5) | Cloudflare Pages + Workers (-0.9, tie) |

Stack score: **91.8** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**BaaS-first (managed backend + thin server-side functions)**: A backend-as-a-service covers auth, data access and realtime; put custom logic in a few functions until it outgrows them. Sized for ~0.1 requests/s at peak, about 1.7 GB of data within 12 months and a 99% availability target.

Availability approach: Firebase runs the backend; keep daily backups/exports of your data

### How the parts fit

1. **Request path**: The browser loads React SPA (Vite) from Vercel; it calls Firebase's API directly through the client SDK (~0.1 requests/s at peak), and Firebase's access rules decide what each user may read or write.
2. **Sign-in**: Firebase Auth signs users in and issues tokens; its access rules check the token on every read and write.
3. **Data**: Cloud Firestore is the system of record (about 1.7 GB within 12 months), run by Firebase.
4. **Deploy**: A git push builds the app; Vercel deploys it with a preview URL per pull request. Access rules and indexes ship with the Firebase CLI from the same repository; Cloud Firestore keeps no schema, so new code reads both the old and the new document shape during a rollout.

## Inputs used

- Scale tier: Hobby (<1k daily users) (peak ~0.1 req/s, derived); database tier: Hobby (<1k daily users) (~1.7 GB in 12 months)
- Budget: ~$0/month (INR converted at a fixed planning rate of 96 INR = 1 USD (FBIL reference rate, Sep 2026).)
- Defaults used (2): What do users do? = read, sign_in, post; Special workloads = none

## Per-layer reasoning

### Frontend: React SPA (Vite) (86.3)

Client-rendered single-page React app built with Vite; deploys as static files to any CDN.

React SPA (Vite) is the frontend for a Prototype / student / hackathon project with about 50 daily users (~0.1 requests/s at peak), built by a solo developer in 2 weeks. Search visibility is marked not needed (behind login), so rendering in the browser is acceptable, and it scores 5.0/5 for rich, app-like interaction. It leads the runner-up, Next.js (React), by 1.2 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Learning curve: 5.0/5 vs 4.1 average for this layer - weighted up because: 2-week MVP: no time to learn new tools; Prototype: learnability.
- Low ops burden: 5.0/5 vs 4.4 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Hiring pool: 5.0/5 vs 3.6 average for this layer.
- Stack synergy (+4): Static build output is served directly from a global CDN.
- Team skill match (4.5/5, direct): your team lists React, a direct match for React SPA (Vite).
- Static build: cheapest and simplest hosting
- Huge component ecosystem (dashboards, charts, admin UIs)
- No server to operate for the UI

**Trade-offs**
- Client-side rendering hurts SEO and first paint on slow phones
- Routing, data fetching and state are your own architecture decisions

**Versus runner-up:** React SPA (Vite) beats Next.js (React) by 1.2 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on seo need (+2.0), team size (+0.8). Next.js (React) is stronger on time to mvp (+0.6), application type (+0.3). Close call: either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +26.9
- Time to MVP: +20.0
- Team size: +18.0
- Team skills: +11.3
- Application type: +9.0
- Realtime needs: +2.6

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Learning curve | 5.0 | 4.5 | 23.2 |
| Low ops burden | 5.0 | 3.5 | 18.0 |
| Team skill match | 4.5 | 3.5 | 15.8 |
| Development speed | 4.0 | 4.0 | 15.5 |
| Realtime fit | 3.0 | 1.2 | 3.1 |
| Ecosystem maturity | 5.0 | 0.5 | 2.6 |
| Hiring pool | 5.0 | 0.5 | 2.6 |
| Rich client interactivity | 5.0 | 0.5 | 2.6 |
| Performance / latency | 3.0 | 0.5 | 1.3 |
| Portability (low lock-in) | 5.0 | 0.2 | 1.0 |
| Structure for large teams | 2.0 | 0.3 | 0.4 |
| SEO | 2.0 | 0.2 | 0.3 |

**Alternatives**
- Next.js (React) (stack 90.6, -1.2): Loses: Static build output is served directly from a global CDN. Note: Vercel builds Next.js: ISR, image optimisation, middleware and preview deploys work with zero configuration.
- Astro (stack 88.8, -3.0): Loses: Static build output is served directly from a global CDN. Note: Official adapters/presets deploy this framework to the CDN + functions platform with no server to manage.

**Why not the others?**
- Why not Next.js (React)? (runner-up) Swapping it in lowers the stack score by 1.2 points. React SPA (Vite) is stronger on low ops burden (5.0 vs 4.0), portability (low lock-in) (5.0 vs 4.0); Next.js (React) is stronger on development speed (5.0 vs 4.0), SEO (5.0 vs 2.0); Next.js (React) takes a penalty: No search visibility needed: server rendering adds a Node.js server for pages that React SPA (Vite) serves as static files.

**Excluded by hard constraints**
- React Native (Expo): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Flutter: Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- Native iOS + Android (Swift / Kotlin): Mobile toolkit; web is a target, so the primary frontend is a web framework (mobile app suggested as companion)
- No frontend (API only): You target a user interface, so a frontend is needed

### Backend: Firebase (BaaS on Google Cloud) (90.3)

Google's mobile/web BaaS: Firestore, Auth, Cloud Functions, FCM push, Crashlytics, Remote Config.

Firebase (BaaS on Google Cloud) serves the API at about 0.1 requests/s at peak (Hobby (<1k daily users)) for a solo developer. As a hosted backend it supplies sign-in, the database API and file storage, so a solo developer only needs to write the business rules in the 2 weeks available. Its share of the estimated bill is ₹0 a month, against a total budget of ₹0 a month. It leads the runner-up, Serverless functions (Node/Python FaaS), by 4.5 stack points.

**Why**
- Learning curve: 5.0/5 vs 3.8 average for this layer - weighted up because: 2-week MVP: no time to learn new tools; Prototype: learnability.
- Development speed: 5.0/5 vs 4.3 average for this layer - weighted up because: 2-week MVP: speed dominates; Prototype: ship fast.
- Low ops burden: 5.0/5 vs 4.2 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Stack synergy (+4): Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end.
- Team skill match (3.0/5, related): nobody listed Firebase (BaaS on Google Cloud), but JavaScript, React carry over.
- Realtime sync and offline persistence in client SDKs
- Push notifications, analytics and crash reporting for mobile
- Generous Spark (free) tier

**Trade-offs**
- Proprietary APIs: highest vendor lock-in
- Per-read billing can surprise at scale

**Risks**
- High vendor lock-in: migrating away later means rewriting data access code.

**Versus runner-up:** Firebase (BaaS on Google Cloud) beats Serverless functions (Node/Python FaaS) by 4.5 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+1.5), realtime needs (+1.0), time to mvp (+0.7). Serverless functions (Node/Python FaaS) is stronger on team skills (+0.3).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +25.1
- Monthly budget: +15.6
- Time to MVP: +15.6
- Application type: +13.6
- Team size: +13.6
- Team skills: +4.9

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 6.5 | 25.3 |
| Learning curve | 5.0 | 4.5 | 17.5 |
| Development speed | 5.0 | 4.0 | 15.6 |
| Low ops burden | 5.0 | 3.5 | 13.6 |
| Team skill match | 3.0 | 3.5 | 6.8 |
| Realtime fit | 5.0 | 1.2 | 4.7 |
| Scalability | 5.0 | 0.5 | 1.9 |
| Ecosystem maturity | 5.0 | 0.5 | 1.9 |
| Performance / latency | 4.0 | 0.5 | 1.5 |
| Hiring pool | 4.0 | 0.5 | 1.5 |
| Structure for large teams | 1.0 | 0.3 | 0.0 |
| Portability (low lock-in) | 1.0 | 0.2 | 0.0 |

**Alternatives**
- Serverless functions (Node/Python FaaS) (stack 87.3, -4.5): Loses: Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end. Note: Firestore outside Google Cloud adds cross-cloud latency and egress costs.
- Node.js + Express (stack 86.0, -5.8): Loses: Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end. Note: Firestore outside Google Cloud adds cross-cloud latency and egress costs.

**Why not the others?**
- Why not Serverless functions (Node/Python FaaS)? (runner-up) Swapping it in lowers the stack score by 4.5 points. Firebase (BaaS on Google Cloud) is stronger on realtime fit (5.0 vs 1.0), learning curve (5.0 vs 4.0); Serverless functions (Node/Python FaaS) is stronger on team skill match (3.5 vs 3.0), portability (low lock-in) (3.0 vs 1.0).
- Why not Node.js + Express? (popular choice) Swapping it in lowers the stack score by 5.8 points. Firebase (BaaS on Google Cloud) is stronger on development speed (5.0 vs 4.0), low ops burden (5.0 vs 4.0); Node.js + Express is stronger on team skill match (4.5 vs 3.0), portability (low lock-in) (5.0 vs 1.0).
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 17.4 points. Firebase (BaaS on Google Cloud) is stronger on team skill match (3.0 vs 1.5), learning curve (5.0 vs 4.0); Python + Django is stronger on structure for large teams (4.0 vs 1.0), portability (low lock-in) (5.0 vs 1.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 20.2 points. Firebase (BaaS on Google Cloud) is stronger on learning curve (5.0 vs 2.0), development speed (5.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on structure for large teams (5.0 vs 1.0), portability (low lock-in) (5.0 vs 1.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: Cloud Firestore (91.7)

Google's serverless document database with realtime listeners and offline client caching.

Your data is mainly document and reaches about 1.7 GB within 12 months; Cloud Firestore fits document data 5/5. Its strongest weighted criterion for your answers is cost at your scale: 5.0/5 at weight 6.5, the largest share of its score. It leads the runner-up, MongoDB, by 19.1 stack points.

Suggested offering: Included with Firebase (BaaS on Google Cloud)

**Why**
- Data-model fit: 5.0/5 vs 3.3 average for this layer.
- Cost at your scale: 5.0/5 vs 4.1 average for this layer - weighted up because: Zero budget: free tiers only; Prototype: free tiers.
- Learning curve: 5.0/5 vs 3.7 average for this layer - weighted up because: 2-week MVP: no time to learn new tools; Prototype: learnability.
- Stack synergy (+4): Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end.
- Team skill match (3.5/5, related): nobody listed Cloud Firestore, but JavaScript carries over.
- Realtime listeners + offline persistence out of the box
- Zero ops; scales automatically

**Trade-offs**
- Limited querying (no joins, restricted aggregations)
- Per-document read billing; Google advises against high write rates to a single document (the sustainable rate depends on the workload), so hot counters need sharding

**Risks**
- High vendor lock-in: migrating away later means rewriting data access code.

**Versus runner-up:** Cloud Firestore beats MongoDB by 19.1 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+13.5), monthly budget (+3.3), application type (+0.9). MongoDB is stronger on general quality (baseline weights) (+0.1).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +39.5
- Monthly budget: +14.6
- Team size: +12.8
- Application type: +9.6
- Time to MVP: +7.8
- Team skills: +5.7

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 6.5 | 23.7 |
| Data-model fit | 5.0 | 5.0 | 18.2 |
| Learning curve | 5.0 | 4.5 | 16.4 |
| Low ops burden | 5.0 | 3.5 | 12.8 |
| Team skill match | 3.5 | 3.5 | 8.0 |
| Realtime fit | 5.0 | 1.2 | 4.4 |
| Consistency fit | 4.0 | 1.0 | 2.7 |
| Scalability | 5.0 | 0.5 | 1.8 |
| Ecosystem maturity | 4.0 | 0.5 | 1.4 |
| Performance / latency | 4.0 | 0.5 | 1.4 |
| Hiring pool | 3.0 | 0.5 | 0.9 |
| Portability (low lock-in) | 1.0 | 0.2 | 0.0 |

**Alternatives**
- MongoDB (stack 72.7, -19.1): Loses: Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end. Note: Firebase is designed around Firestore/Realtime Database; pairing it with another primary DB needs a separate server tier.

**Why not the others?**
- Why not MongoDB? (runner-up) Swapping it in lowers the stack score by 19.1 points. Cloud Firestore is stronger on cost at your scale (5.0 vs 3.7), learning curve (5.0 vs 4.0); MongoDB is stronger on portability (low lock-in) (4.0 vs 1.0), consistency fit (4.5 vs 4.0); MongoDB takes a penalty: No free option at your scale (from ~$8/month).
- Why not PostgreSQL? (popular choice) Swapping it in lowers the stack score by 21.6 points. Cloud Firestore is stronger on team skill match (3.5 vs 1.5), cost at your scale (5.0 vs 4.1); PostgreSQL is stronger on hiring pool (5.0 vs 3.0), portability (low lock-in) (5.0 vs 1.0); PostgreSQL takes a penalty: No free option at your scale (from ~$5/month).
- Why not MySQL? (popular choice) Swapping it in lowers the stack score by 26.5 points. Cloud Firestore is stronger on data-model fit (5.0 vs 3.0), team skill match (3.5 vs 1.5); MySQL is stronger on hiring pool (5.0 vs 3.0), portability (low lock-in) (5.0 vs 1.0); MySQL takes a penalty: No free option at your scale (from ~$5/month).

**Excluded by hard constraints**
- Redis / Valkey: In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your document data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- ClickHouse: Poor fit for 'document' data as the primary store (1/5)
- OpenSearch / Elasticsearch: Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your document data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- No database (content files in git): Only for read-only sites; your users sign in, post or pay

### Hosting: Vercel (90.9)

Frontend cloud: global CDN, SSR and serverless/edge functions; made by the Next.js team.

Vercel hosts the stack for users in India at a 99% availability target. It serves the pages from a global CDN and runs server code as functions, which covers ~0.1 requests/s at peak without servers to manage. Its share of the estimated bill is ₹0 a month, against a total budget of ₹0 a month. Cloudflare Pages + Workers is within 0.9 stack points, inside the tie margin (stacks this close count as tied), so either is defensible (see the runner-up note).

Runs here: React SPA (static files). Firebase runs the API, auth and database as its own managed service.

**Why**
- Cost at your scale: 5.0/5 vs 3.9 average for this layer - weighted up because: Zero budget: free tiers only; Prototype: free tiers.
- Learning curve: 5.0/5 vs 3.6 average for this layer - weighted up because: 2-week MVP: no time to learn new tools; Prototype: learnability.
- Low ops burden: 5.0/5 vs 4.0 average for this layer - weighted up because: Solo developer: every hour on ops is lost on product.
- Stack synergy (+4): Static build output is served directly from a global CDN.
- Team skill match (4.0/5, related): nobody listed Vercel, but JavaScript, React carry over.
- Zero-config deploys for most frontend frameworks, preview URLs per pull request
- Global edge network gives fast TTFB everywhere

**Trade-offs**
- Realtime fit is only 2.0/5 (weight 1.2).
- Hobby tier is non-commercial; bandwidth/function overages get expensive at scale
- WebSockets on Functions are in public beta: a connection pins to one instance, so fan-out needs a shared pub/sub

**Versus runner-up:** Vercel and Cloudflare Pages + Workers are within 0.9 stack points of each other, inside the 1-point tie margin, so they count as tied. Vercel is stronger on learning curve (5.0 vs 4.0); Cloudflare Pages + Workers is stronger on realtime fit (3.0 vs 2.0). Choose Cloudflare Pages + Workers instead if live updates matters more to you than a gentler learning curve. Vercel has the higher stack score. Either is defensible.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +27.6
- Monthly budget: +18.3
- Team size: +16.0
- Application type: +12.0
- Time to MVP: +10.3
- Team skills: +8.6

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Cost at your scale | 5.0 | 6.5 | 29.7 |
| Learning curve | 5.0 | 4.5 | 20.6 |
| Low ops burden | 5.0 | 3.5 | 16.0 |
| Team skill match | 4.0 | 3.5 | 12.0 |
| Region coverage | 5.0 | 1.0 | 4.6 |
| Scalability | 5.0 | 0.5 | 2.3 |
| Performance / latency | 5.0 | 0.5 | 2.3 |
| Ecosystem maturity | 4.0 | 0.5 | 1.7 |
| Realtime fit | 2.0 | 1.2 | 1.4 |
| Portability (low lock-in) | 3.0 | 0.2 | 0.5 |

**Alternatives**
- Cloudflare Pages + Workers (stack 90.8, -0.9): Scores 87.1 on its own; its stack is 0.9 stack points behind the pick.
- Netlify (stack 90.4, -1.4): Scores 85.2 on its own; its stack is 1.4 stack points behind the pick.

**Why not the others?**
- Why not Cloudflare Pages + Workers? (runner-up) Within the 1-point tie margin (counted as tied): swapped in, its stack scores 0.9 points lower; either is defensible. Vercel is stronger on learning curve (5.0 vs 4.0); Cloudflare Pages + Workers is stronger on realtime fit (3.0 vs 2.0).
- Why not AWS ECS on Fargate? (popular choice) Swapping it in lowers the stack score by 18.1 points. Vercel is stronger on cost at your scale (5.0 vs 2.8), learning curve (5.0 vs 3.0); AWS ECS on Fargate is stronger on realtime fit (4.0 vs 2.0), ecosystem maturity (5.0 vs 4.0); AWS ECS on Fargate takes a penalty: Usually needs a team of 2+ to operate.
- Why not Render? (popular choice) Swapping it in lowers the stack score by 4.9 points. Vercel is stronger on team skill match (4.0 vs 1.5), cost at your scale (5.0 vs 4.5); Render is stronger on realtime fit (4.0 vs 2.0), portability (low lock-in) (4.0 vs 3.0).

**Excluded by hard constraints**
- AWS S3 + CloudFront (static): Only for read-only sites; your users sign in, post or pay
- On-prem VMs + Docker Compose: On-premises option; you chose public cloud
- On-prem Kubernetes (k3s / RKE2 / OpenShift): On-premises option; you chose public cloud
- AWS EC2 VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Google Compute Engine VMs (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs
- Azure Virtual Machines (Docker Compose): Plain VMs your team patches and operates; offered when you choose self-managed VMs

## Stack compatibility checks

- (synergy, +4) Static build output is served directly from a global CDN.
- (synergy, +4) Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end.

## Supporting services

- **Realtime**: Built-in realtime of Firebase (BaaS on Google Cloud): Subscriptions/listeners are provided by the BaaS; no socket server needed.
- **Observability**: OpenTelemetry instrumentation -> Grafana Cloud / Sentry: Traces, metrics and error tracking from day one; required to defend an availability target.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Hosting: Vercel | 0 | 0 | Hobby (<1k daily users) price band |
| Backend: Firebase (BaaS on Google Cloud) (includes its database) | 0 | 0 | plan sized for the larger of traffic (Hobby (<1k daily users)) and ~2 GB of data in 12 months; per-read/write pricing at your request volume; disk beyond the plan's allowance billed per GB |
| **Total** | **0** | **0** | |

About ₹0-₹0 per month. Budget status: **within**. Planning estimate from published price bands at your scale tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **A team of 15 engineers**: frontend: React SPA (Vite) -> Next.js (React)
  - Why frontend changes: Structure for large teams moved the gap 1.9 points toward Next.js (React) (Next.js (React) 3.0/5 vs React SPA (Vite) 2.0/5, weight 0.3 -> 1.8); on its own React SPA (Vite) still scores 0.6 higher, so Next.js (React) wins as part of the whole stack (a stack rule now applies: Vercel builds Next.js: ISR, image optimisation, middleware and preview deploys work with zero configuration).
- **SEO becomes critical**: frontend: React SPA (Vite) -> Next.js (React)
  - Why frontend changes: React SPA (Vite) now takes a penalty (Client-side rendering is a liability when organic search is the business), moving the gap 18.0 points toward Next.js (React); SEO moved the gap 12.7 points toward Next.js (React) (Next.js (React) 5.0/5 vs React SPA (Vite) 2.0/5, weight 0.2 -> 4.2).
- **Must run on-premises**: backend: Firebase (BaaS on Google Cloud) -> Node.js + Express; database: Cloud Firestore -> MongoDB; hosting: Vercel -> On-prem VMs + Docker Compose
  - Why backend changes: Firebase (BaaS on Google Cloud) is now ruled out: Managed-only BaaS cannot run on-premises.
  - Why database changes: Cloud Firestore is now ruled out: Managed-only cloud database cannot run on-premises.
  - Why hosting changes: Vercel is now ruled out: Public-cloud service; deployment must be on-premises.
- **Low tolerance for vendor lock-in**: backend: Firebase (BaaS on Google Cloud) -> Supabase (BaaS on Postgres); database: Cloud Firestore -> PostgreSQL
  - Why backend changes: Firebase (BaaS on Google Cloud) is now ruled out: Proprietary API with the highest lock-in; you asked for low lock-in.
  - Why database changes: Cloud Firestore is now ruled out: Proprietary API with the highest lock-in; you asked for low lock-in.
- **HIPAA compliance required**: backend: Firebase (BaaS on Google Cloud) -> Node.js + Express; hosting: Vercel -> Google Cloud Run
  - Why backend changes: Firebase (BaaS on Google Cloud) is now ruled out: No HIPAA Business Associate Agreement available.
  - Why hosting changes: Vercel now takes a penalty (No free option at your scale (from ~$350/month)), moving the gap 37.3 points toward Google Cloud Run; cost at your scale moved the gap 28.1 points toward Google Cloud Run (Google Cloud Run 4.3/5 vs Vercel 1.0/5, was 4.3 vs 5.0).

## Next-best complete stacks

- React SPA (Vite) + Firebase (BaaS on Google Cloud) + Cloud Firestore + Cloudflare Pages + Workers (90.8, -0.9)
- Next.js (React) + Firebase (BaaS on Google Cloud) + Cloud Firestore + Vercel (90.6, -1.2)
- React SPA (Vite) + Firebase (BaaS on Google Cloud) + Cloud Firestore + Netlify (90.4, -1.4)

## Sources

- https://react.dev
- https://vite.dev/guide/
- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- https://firebase.google.com/docs
- https://firebase.google.com/pricing
- https://firebase.google.com/support/privacy
- https://cloud.google.com/security/compliance/hipaa
- https://firebase.google.com/docs/firestore/locations
- https://firebase.google.com/docs/projects/locations
- https://firebase.google.com/docs/auth/admin/create-custom-tokens
- https://firebase.google.com/docs/firestore
- https://cloud.google.com/firestore/docs/best-practices
- https://cloud.google.com/firestore/quotas
- https://firebase.google.com/docs/firestore/manage-data/enable-offline
- https://vercel.com/docs
- https://vercel.com/pricing
- https://vercel.com/docs/limits/fair-use-guidelines
- https://vercel.com/security
- https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections
- https://vite.dev/guide/static-deploy
