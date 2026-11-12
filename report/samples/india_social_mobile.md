# StackSense recommendation: GupShup (social)

_Engine v1.0.0. Deterministic: the same inputs always give the same output._

## Summary

For a 'Social network / UGC feed' project at Large (100k-1M daily users) scale (~1,389 peak req/s) built by 3 engineer(s) in 10 weeks, StackSense recommends React Native (Expo) + Firebase (BaaS on Google Cloud) + Cloud Firestore + Provided by Firebase (architecture: BaaS-first (managed backend + thin server-side functions)). Estimated infrastructure cost: ₹58,848-₹321,024/month (stretch budget).

## Recommended stack

| Layer | Pick | Score | Margin over runner-up | Runner-up |
|---|---|---|---|---|
| Frontend | **React Native (Expo)** | 74.6 | 1.7, solid (1.5-4 points) | Flutter (-1.7) |
| Backend | **Firebase (BaaS on Google Cloud)** | 96.2 | 11.5, clear (4+ points) | Node.js + Express (-11.5) |
| Database | **Cloud Firestore** | 91.0 | 16.9, clear (4+ points) | MongoDB (-16.9) |
| Hosting | **Provided by Firebase** | 83.1 | no runner-up | - |

Stack score: **88.2** / 100 (average of layer scores plus compatibility adjustments).

## Architecture

**BaaS-first (managed backend + thin server-side functions)**: A backend-as-a-service covers auth, data access and realtime; put custom logic in a few functions until it outgrows them. Sized for ~1,389 requests/s at peak, about 290 GB of data within 12 months and a 99.9% availability target.

Availability approach: Firebase runs the backend on a paid plan; turn on point-in-time recovery and check the plan's uptime commitment

### How the parts fit

1. **Request path**: The iOS/Android app, installed from the app stores, calls Firebase's API directly through the client SDK (~1,389 requests/s at peak), and Firebase's access rules decide what each user may read or write.
2. **Sign-in**: Firebase Auth signs users in and issues tokens; its access rules check the token on every read and write.
3. **Data**: Cloud Firestore is the system of record (about 290 GB within 12 months), run by Firebase; uploaded files go to Cloud Storage for Firebase (included in the Firebase project).
4. **Deploy**: App releases go through App Store and Google Play review. JavaScript-only fixes can ship as over-the-air updates (Expo EAS Update). Access rules and indexes ship with the Firebase CLI from the same repository; Cloud Firestore keeps no schema, so new code reads both the old and the new document shape during a rollout.

## Inputs used

- Scale tier: Large (100k-1M daily users) (peak ~1,389 req/s, derived); database tier: Medium (100 GB-1 TB of data) (~290 GB in 12 months)
- Budget: ~$833/month (INR converted at a fixed planning rate of 96 INR = 1 USD (an assumption; check the FBIL reference rate for today's value).)
- Assumption: compliance = dpdp: DPDP Act 2023 (in force through the DPDP Rules 2025, notified November 2025 and phased in over 18 months) allows cross-border transfer except to notified countries, so it adds consent/breach-notice duties but not an India-region filter. Add 'Data must stay in India' if a sector rule (e.g. RBI) applies.
- Defaults used (1): Special workloads = none

## Warnings and how they were resolved

- **[WARNING] Budget below the top of the estimate**: ₹58,848-₹321,024/month against ₹80,000/month: the top (~3x today's load) and the middle are over, most of the rise in Firebase and Neo4j. *Resolution:* Raise the budget before the load grows.

## Per-layer reasoning

### Frontend: React Native (Expo) (74.6)

Cross-platform native mobile apps in React/TypeScript; Expo provides builds, OTA updates and native modules.

React Native (Expo) is the app for a Social network / UGC feed project with about 100,000 daily users (~1,389 requests/s at peak), built by a team of 3 in 10 weeks. One codebase builds both the iOS and the Android app, which halves the work for a team of 3. It leads the runner-up, Flutter, by 1.7 stack points (points of the overall stack score, the average of the four layer scores).

**Why**
- Learning curve: 5.0/5 vs 3.3 average for this layer - weighted up because: 10-week MVP; Small team (3).
- Development speed: 4.0/5 vs 3.3 average for this layer - weighted up because: 10-week MVP.
- Low ops burden: 4.0/5 vs 3.7 average for this layer - weighted up because: Small team (3).
- Stack synergy (+4): Mobile SDKs handle auth, storage and push without a custom API.
- Team skill match (5.0/5, direct): your team lists JavaScript, React, React Native, TypeScript, a direct match for React Native (Expo).
- One codebase for iOS + Android (+ web via react-native-web)
- Reuses React skills and TypeScript types from the web app
- Expo EAS handles builds and over-the-air updates

**Trade-offs**
- Heavy animations / complex native integrations need native modules
- App-store review cycle still applies to native changes

**Versus runner-up:** React Native (Expo) beats Flutter by 1.7 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on team skills (+2.4), team size (+0.3), time to mvp (+0.3). Flutter is stronger on stack compatibility (+1.0), latency target (+0.1).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +19.8
- Realtime needs: +12.1
- Team skills: +11.0
- Offline support: +9.9
- Team size: +7.2
- Time to MVP: +5.5

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Rich client interactivity | 5.0 | 2.5 | 11.0 |
| Team skill match | 5.0 | 2.5 | 11.0 |
| Offline support | 4.0 | 3.0 | 9.9 |
| Low ops burden | 4.0 | 2.5 | 8.3 |
| Realtime fit | 3.0 | 3.7 | 8.2 |
| Learning curve | 5.0 | 1.5 | 6.6 |
| Development speed | 4.0 | 2.0 | 6.6 |
| Performance / latency | 3.0 | 2.3 | 5.1 |
| Ecosystem maturity | 4.0 | 1.5 | 5.0 |
| Hiring pool | 4.0 | 0.5 | 1.6 |
| Structure for large teams | 3.0 | 0.3 | 0.7 |
| Portability (low lock-in) | 4.0 | 0.2 | 0.7 |
| SEO | 1.0 | 0.2 | 0.0 |

**Alternatives**
- Flutter (stack 86.5, -1.7): Loses: Mobile SDKs handle auth, storage and push without a custom API. Note: FlutterFire is maintained by Google, giving first-party auth, Firestore offline sync and push notifications.
- Native iOS + Android (Swift / Kotlin) (stack 84.4, -3.8): Scores 59.5 on its own; its stack is 3.8 stack points behind the pick.

**Why not the others?**
- Why not Flutter? (runner-up) Swapping it in lowers the stack score by 1.7 points. React Native (Expo) is stronger on team skill match (5.0 vs 1.5), learning curve (5.0 vs 3.0); Flutter is stronger on performance / latency (4.0 vs 3.0).

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

### Backend: Firebase (BaaS on Google Cloud) (96.2)

Google's mobile/web BaaS: Firestore, Auth, Cloud Functions, FCM push, Crashlytics, Remote Config.

Firebase (BaaS on Google Cloud) serves the API at about 1,389 requests/s at peak (Large (100k-1M daily users)) for a team of 3. As a hosted backend it supplies sign-in, the database API and file storage, so a team of 3 only needs to write the business rules in the 10 weeks available. Realtime is core, and it scores 5.0/5 on realtime fit. Its share of the estimated bill is ₹46,368-₹257,952 a month, against a total budget of ₹80,000 a month. It leads the runner-up, Node.js + Express, by 11.5 stack points.

**Why**
- Realtime fit: 5.0/5 vs 3.5 average for this layer - weighted up because: Realtime is core to the product; Feeds and notifications.
- Scalability: 5.0/5 vs 4.3 average for this layer - weighted up because: Large (100k-1M daily users); Viral growth.
- Low ops burden: 5.0/5 vs 4.2 average for this layer - weighted up because: Small team (3).
- Bonus +6: Your team already ships Firebase (BaaS on Google Cloud) (firebase listed in team skills).
- Stack synergy (+4): Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end.
- Stack synergy (+4): Mobile SDKs handle auth, storage and push without a custom API.
- Team skill match (4.5/5, direct): your team lists Firebase, a direct match for Firebase (BaaS on Google Cloud).
- Realtime sync and offline persistence in client SDKs
- Push notifications, analytics and crash reporting for mobile
- Generous Spark (free) tier

**Trade-offs**
- Proprietary APIs: highest vendor lock-in
- Per-read billing can surprise at scale

**Risks**
- High vendor lock-in: migrating away later means rewriting data access code.

**Versus runner-up:** Firebase (BaaS on Google Cloud) beats Node.js + Express by 11.5 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+7.5), team skills (+1.1), realtime needs (+1.0). Node.js + Express is stronger on monthly budget (+0.2), general quality (baseline weights) (+0.1).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +28.1
- Team skills: +16.2
- Realtime needs: +15.7
- Team size: +9.3
- Scale (DAU / peak RPS): +8.7
- Time to MVP: +7.0

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Realtime fit | 5.0 | 3.7 | 17.2 |
| Scalability | 5.0 | 3.0 | 13.9 |
| Low ops burden | 5.0 | 2.5 | 11.6 |
| Team skill match | 4.5 | 2.5 | 10.2 |
| Development speed | 5.0 | 2.0 | 9.3 |
| Performance / latency | 4.0 | 2.3 | 8.0 |
| Learning curve | 5.0 | 1.5 | 7.0 |
| Ecosystem maturity | 5.0 | 1.5 | 7.0 |
| Cost at your scale | 3.4 | 1.5 | 4.2 |
| Hiring pool | 4.0 | 0.5 | 1.7 |
| Structure for large teams | 1.0 | 0.3 | 0.0 |
| Portability (low lock-in) | 1.0 | 0.2 | 0.0 |
| Adjustment: Your team already ships Firebase (BaaS on Google Cloud) (firebase listed in team skills) | | | +6.0 |

**Alternatives**
- Node.js + Express (stack 76.7, -11.5): Loses: Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end. Note: Firestore outside Google Cloud adds cross-cloud latency and egress costs.
- Node.js + NestJS (stack 76.1, -12.1): Loses: Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end. Note: Firestore outside Google Cloud adds cross-cloud latency and egress costs.

**Why not the others?**
- Why not Node.js + Express? (runner-up) Swapping it in lowers the stack score by 11.5 points. Firebase (BaaS on Google Cloud) is stronger on realtime fit (5.0 vs 4.0), scalability (5.0 vs 4.0); Node.js + Express is stronger on cost at your scale (5.0 vs 3.4), team skill match (5.0 vs 4.5). 7.5 of the 11.5 points come from a stack compatibility rule: Firestore outside Google Cloud adds cross-cloud latency and egress costs.
- Why not Python + Django? (popular choice) Swapping it in lowers the stack score by 25.4 points. Firebase (BaaS on Google Cloud) is stronger on realtime fit (5.0 vs 2.0), team skill match (4.5 vs 1.5); Python + Django is stronger on cost at your scale (5.0 vs 3.4), structure for large teams (4.0 vs 1.0); Python + Django takes a penalty: Nobody on the team listed Python or a closely related skill: a new server language to learn. 15.0 of the 25.4 points come from a stack compatibility rule: Frontend platforms run code only as short-lived functions; this framework expects a long-running server. Host the API on a container/PaaS service instead.
- Why not Java/Kotlin + Spring Boot? (popular choice) Swapping it in lowers the stack score by 41.8 points. Firebase (BaaS on Google Cloud) is stronger on team skill match (4.5 vs 1.5), realtime fit (5.0 vs 3.0); Java/Kotlin + Spring Boot is stronger on cost at your scale (5.0 vs 3.4), structure for large teams (5.0 vs 1.0); Java/Kotlin + Spring Boot takes a penalty: Nobody on the team listed Java/Kotlin or a closely related skill: a new server language to learn. 31.5 of the 41.8 points come from a stack compatibility rule: Cloudflare Workers run JavaScript, TypeScript, Python and Rust; other languages, Go among them, run only compiled to WebAssembly, so a Go (net/http, chi or Gin), Java, .NET, PHP, Elixir or Ruby server needs Cloudflare Containers instead, a separate product on the Workers Paid plan without autoscaling yet.

**Excluded by hard constraints**
- No server code (static site): Only for read-only sites; your users sign in, post or pay

### Database: Cloud Firestore (91.0)

Google's serverless document database with realtime listeners and offline client caching.

Your data is mainly document and reaches about 290 GB within 12 months; Cloud Firestore fits document data 5/5. Realtime is core, and it can push changes to clients (realtime fit 5.0/5). It leads the runner-up, MongoDB, by 16.9 stack points.

Suggested offering: Included with Firebase (BaaS on Google Cloud)

**Why**
- Offline support: 5.0/5 vs 1.6 average for this layer - weighted up because: Offline support required.
- Realtime fit: 5.0/5 vs 2.8 average for this layer - weighted up because: Realtime is core to the product; Feeds and notifications.
- Data-model fit: 4.7/5 vs 3.6 average for this layer.
- Stack synergy (+4): Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end.
- Team skill match (4.5/5, direct): your team lists Firebase, a direct match for Cloud Firestore.
- Realtime listeners + offline persistence out of the box
- Zero ops; scales automatically

**Trade-offs**
- Limited querying (no joins, restricted aggregations)
- Per-document read billing; Google advises against high write rates to a single document (the sustainable rate depends on the workload), so hot counters need sharding

**Risks**
- High vendor lock-in: migrating away later means rewriting data access code.

**Versus runner-up:** Cloud Firestore beats MongoDB by 16.9 stack points (points on the 0-100 stack score, the average of the four layer scores), mainly on stack compatibility (+13.5), offline support (+2.0), realtime needs (+0.7). MongoDB is stronger on general quality (baseline weights) (+0.3), compliance (+0.1).

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +36.5
- Realtime needs: +12.0
- Offline support: +10.6
- Team skills: +7.8
- Team size: +7.1
- Scale (DAU / peak RPS): +6.7

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Data-model fit | 4.7 | 5.0 | 16.2 |
| Realtime fit | 5.0 | 3.7 | 13.1 |
| Scalability | 5.0 | 3.0 | 10.6 |
| Offline support | 5.0 | 3.0 | 10.6 |
| Low ops burden | 5.0 | 2.5 | 8.9 |
| Team skill match | 4.5 | 2.5 | 7.8 |
| Performance / latency | 4.0 | 2.3 | 6.1 |
| Learning curve | 5.0 | 1.5 | 5.3 |
| Cost at your scale | 4.5 | 1.5 | 4.7 |
| Ecosystem maturity | 4.0 | 1.5 | 4.0 |
| Consistency fit | 4.0 | 1.0 | 2.7 |
| Hiring pool | 3.0 | 0.5 | 0.9 |
| Portability (low lock-in) | 1.0 | 0.2 | 0.0 |

**Alternatives**
- MongoDB (stack 71.3, -16.9): Loses: Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end. Note: Firebase is designed around Firestore/Realtime Database; pairing it with another primary DB needs a separate server tier.

**Why not the others?**
- Why not MongoDB? (runner-up) Swapping it in lowers the stack score by 16.9 points. Cloud Firestore is stronger on offline support (5.0 vs 2.0), realtime fit (5.0 vs 4.0); MongoDB is stronger on ecosystem maturity (5.0 vs 4.0), portability (low lock-in) (4.0 vs 1.0). 13.5 of the 16.9 points come from a stack compatibility rule: Firebase is designed around Firestore/Realtime Database; pairing it with another primary DB needs a separate server tier.
- Why not PostgreSQL? (popular choice) Swapping it in lowers the stack score by 21.6 points. Cloud Firestore is stronger on offline support (5.0 vs 1.0), team skill match (4.5 vs 1.5); PostgreSQL is stronger on ecosystem maturity (5.0 vs 4.0), hiring pool (5.0 vs 3.0). 14.0 of the 21.6 points come from a stack compatibility rule: Firebase is designed around Firestore/Realtime Database; pairing it with another primary DB needs a separate server tier.
- Why not MySQL? (popular choice) Swapping it in lowers the stack score by 26.6 points. Cloud Firestore is stronger on offline support (5.0 vs 1.0), realtime fit (5.0 vs 2.0); MySQL is stronger on ecosystem maturity (5.0 vs 4.0), hiring pool (5.0 vs 3.0); MySQL takes a penalty: Only 3/5 fit for your primary 'document' data. 14.0 of the 26.6 points come from a stack compatibility rule: Firebase is designed around Firestore/Realtime Database; pairing it with another primary DB needs a separate server tier.

**Excluded by hard constraints**
- Redis / Valkey: Poor fit for 'document' data as the primary store (2/5); In-memory store: ~290 GB within 12 months cannot sensibly live in RAM as the system of record (use it as a cache); In-memory store: with the default append-only-file setting (fsync every second) a crash loses up to the last second of writes, and snapshots alone lose minutes; it holds key-value data but not tables of records: your document, graph data needs a durable general-purpose primary store, with Redis / Valkey beside it as a supporting store
- ClickHouse: Poor fit for 'document' data as the primary store (1/5)
- OpenSearch / Elasticsearch: Search index: no multi-document transactions, and a write becomes searchable only after the next refresh, so it keeps append-only events (logs) but records that are updated belong in a transactional store it indexes from: your document, graph data needs a durable general-purpose primary store, with OpenSearch / Elasticsearch beside it as a supporting store
- Neo4j: Graph store: built for relationship traversals, and fits tables of records 2/5; graph deployments typically sit beside the relational system of record (Neo4j's own financial-services case kept SQL Server for customer history and added the graph for link analysis): your document data needs a durable general-purpose primary store, with Neo4j beside it as a supporting store
- SQLite (+ Litestream backups): Single-node file database: no failover, so it cannot meet 99.9% availability; One writer at a time for the whole file: offline devices upload their queued changes together when they reconnect, so the server copy they all sync with needs a client/server database (SQLite stays on the device as the local copy); One writer at a time for the whole file: 20.0M+ requests a day at Large (100k-1M daily users) is past the 1M a day SQLite's own guide says it has been shown to handle
- No database (content files in git): Only for read-only sites; your users sign in, post or pay

### Hosting: Provided by Firebase (83.1)

Firebase hosts the backend; the app itself ships through the app stores.

With about 100,000 daily users on iOS and Android, nothing of yours needs separate hosting: Firebase runs the backend and the app stores ship the app. If you add a web landing page, Firebase Hosting can serve it; it is optional. The backend's estimated bill, ₹46,368-₹257,952 a month against a total budget of ₹80,000 a month, covers what would otherwise be hosting.

**Why**
- Nothing of yours needs hosting: the app ships through the App Store and Google Play, and Firebase runs the API, auth, database and file storage. Firebase Hosting (free tier) is optional, for a landing page or web admin.

**Trade-offs**
- Backend quotas, regions and pricing are Firebase's; see the Backend card.

**Inputs that drove this score** (points out of 100)
- General quality (baseline weights): +29.3
- Scale (DAU / peak RPS): +9.9
- Realtime needs: +9.9
- Team size: +9.3
- Team skills: +9.3
- Application type: +3.7

| Criterion | Score (1-5) | Weight | Points |
|---|---|---|---|
| Scalability | 5.0 | 3.0 | 14.8 |
| Low ops burden | 5.0 | 2.5 | 12.4 |
| Performance / latency | 5.0 | 2.3 | 11.4 |
| Team skill match | 4.0 | 2.5 | 9.3 |
| Realtime fit | 3.0 | 3.7 | 9.2 |
| Region coverage | 5.0 | 1.5 | 7.4 |
| Cost at your scale | 4.8 | 1.5 | 7.0 |
| Learning curve | 4.0 | 1.5 | 5.6 |
| Ecosystem maturity | 4.0 | 1.5 | 5.6 |
| Portability (low lock-in) | 3.0 | 0.2 | 0.5 |

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

- (synergy, +4) Firebase SDKs give Firestore realtime listeners, offline cache and security rules end-to-end.
- (synergy, +4) Mobile SDKs handle auth, storage and push without a custom API.

## Supporting services

- **Realtime**: Built-in realtime of Firebase (BaaS on Google Cloud): Subscriptions/listeners are provided by the BaaS; no socket server needed.
- **Secondary store (graph)**: Neo4j (Neo4j AuraDB): Your primary database fits your data less well than Neo4j: 'graph' 1/5 against 5/5.
- **Search**: Meilisearch Cloud: Search across ~193 GB of documents (an estimate: the document share of your ~290 GB total, from your 2 data shapes) needs an inverted index with relevance ranking, highlighting and filters; database text indexes slow down and rank poorly at this size.
- **Object storage**: Cloud Storage for Firebase (included in the Firebase project): Media and documents belong in object storage, not the database. Firebase security rules cover both.
- **Offline sync**: Firestore offline persistence (built into the client SDKs): Offline use needs a local copy of the data and conflict handling when the device reconnects; the primary database does not provide that by itself.
- **Push notifications**: Expo push notifications (FCM and APNs underneath): Standard channel for mobile engagement on Android and iOS.
- **Observability**: OpenTelemetry instrumentation -> Grafana Cloud: Traces, metrics and error tracking from day one; required to defend an availability target.

### Add later (ops budget)

A team of 3 is kept to 2 extra system(s) to operate. Our estimate: a team of 1-2 people runs at most 1 extra system next to its app and database, 3-5 people 2, 6-12 people 4, 13 or more no cap. Compliance and security services are never deferred.

- **Analytics**: ClickHouse Cloud (AWS/GCP/Azure) fed by a continuous copy of database changes: add when dashboard or reporting queries on the primary database take more than ~2 s. Run heavy aggregations on a columnar store instead of the transactional database.

## Estimated monthly cost

| Component | Low (USD) | High (USD) | Basis |
|---|---|---|---|
| Backend: Firebase (BaaS on Google Cloud) (includes its database) | 483 | 2,687 | plan sized for the larger of traffic (Large (100k-1M daily users)) and ~290 GB of data in 12 months, from the band's floor up to its price at ~3x the load, for 1,389 req/s at peak (44% of the way up the tier, log scale); per-read/write pricing at your request volume; disk beyond the plan's allowance billed per GB |
| Secondary store (graph): Neo4j | 130 | 657 | Medium (100 GB-1 TB of data) price band (the app's scale), from the band's floor up to its price at ~3x the load, for ~290 GB of data (46% of the way up the tier, log scale) |
| **Total** | **613** | **3,344** | |

About ₹58,848-₹321,024 per month. Budget status: **stretch**. Planning estimate from published price bands at your scale tier, each read where the project sits inside its tier, with the usage terms listed per line; excludes salaries, third-party SaaS (auth, email, payments fees) and egress spikes.

## What would change the recommendation

- **Must run on-premises**: backend: Firebase (BaaS on Google Cloud) -> Node.js + Express; database: Cloud Firestore -> MongoDB; hosting: Provided by Firebase -> On-prem VMs + Docker Compose
  - Why backend changes: Firebase (BaaS on Google Cloud) is now ruled out: Managed-only BaaS cannot run on-premises.
  - Why database changes: Cloud Firestore is now ruled out: Managed-only cloud database cannot run on-premises.
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: Public-cloud service; deployment must be on-premises.
- **Low tolerance for vendor lock-in**: backend: Firebase (BaaS on Google Cloud) -> Node.js + Express; database: Cloud Firestore -> MongoDB; hosting: Provided by Firebase -> DigitalOcean (App Platform + Managed DBs)
  - Why backend changes: Firebase (BaaS on Google Cloud) is now ruled out: Proprietary API with the highest lock-in; you asked for low lock-in.
  - Why database changes: Cloud Firestore is now ruled out: Proprietary API with the highest lock-in; you asked for low lock-in.
  - Why hosting changes: Portability (low lock-in) moved the gap 2.5 points toward DigitalOcean (App Platform + Managed DBs) (DigitalOcean (App Platform + Managed DBs) 4.0/5 vs Cloudflare Pages + Workers 3.0/5, weight 0.2 -> 2.5); on its own Cloudflare Pages + Workers still scores 9.8 higher, so DigitalOcean (App Platform + Managed DBs) wins as part of the whole stack (a stack rule now applies: Git-push deploys with managed database add-ons are the shortest path to production for a monolith).
- **HIPAA compliance required**: backend: Firebase (BaaS on Google Cloud) -> Node.js + Express; hosting: Provided by Firebase -> Google Cloud Run
  - Why backend changes: Firebase (BaaS on Google Cloud) is now ruled out: No HIPAA Business Associate Agreement available.
  - Why hosting changes: Cloudflare Pages + Workers is now ruled out: No HIPAA Business Associate Agreement available.
- **Team has no relevant prior skills**: frontend: React Native (Expo) -> Native iOS + Android (Swift / Kotlin)
  - Why frontend changes: Team skill match moved the gap 9.6 points toward Native iOS + Android (Swift / Kotlin) (Native iOS + Android (Swift / Kotlin) 3.0/5 vs React Native (Expo) 3.0/5, weight 2.5 -> 0.0, was 1.5 vs 5.0).

## Next-best complete stacks

- Flutter + Firebase (BaaS on Google Cloud) + Cloud Firestore + Provided by Firebase (86.5, -1.7)
- Native iOS + Android (Swift / Kotlin) + Firebase (BaaS on Google Cloud) + Cloud Firestore + Provided by Firebase (84.4, -3.8)
- React Native (Expo) + Node.js + Express + Cloud Firestore + Google Cloud Run (80.6, -7.6)

## Sources

- https://reactnative.dev/docs/getting-started
- https://docs.expo.dev/
- https://docs.expo.dev/eas-update/introduction/
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
- https://developers.cloudflare.com/pages/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/durable-objects/
- https://www.cloudflare.com/trust-hub/compliance-resources/
- https://developers.cloudflare.com/data-localization/region-support/
- https://supabase.com/docs/guides/getting-started/quickstarts/expo-react-native
