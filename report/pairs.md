# One answer apart

**Startup SaaS MVP, then add HIPAA** (preset `startup_mvp`; changed answer: `compliance`: gdpr → gdpr, hipaa)

| Layer | Before | After |
|---|---|---|
| Frontend | Next.js (React) | Next.js (React) |
| Backend | Supabase (BaaS on Postgres) | **Node.js + Express** |
| Database | PostgreSQL | PostgreSQL |
| Hosting | Cloudflare Pages + Workers | **Google Cloud Run** |
| Est. cost / month | $26–$28 | $27–$82 |

- Backend: Supabase (BaaS on Postgres) now takes a penalty (Minimum ~$584/month is 11.7x the whole budget), moving the gap 17.8 points toward Node.js + Express; cost at your scale moved the gap 11.1 points toward Node.js + Express (Node.js + Express 5.0/5 vs Supabase (BaaS on Postgres) 1.5/5, was 5.0 vs 4.8).
- Hosting: Cloudflare Pages + Workers is now ruled out: No HIPAA Business Associate Agreement available.

**IoT telemetry, 40,000 devices vs 5 million** (preset `iot_telemetry`; changed answer: `dau`: 40,000 → 5,000,000)

| Layer | Before | After |
|---|---|---|
| Frontend | React SPA (Vite) | React SPA (Vite) |
| Backend | Go (net/http, chi or Gin) | Go (net/http, chi or Gin) |
| Database | TimescaleDB (Postgres) | TimescaleDB (Postgres) |
| Hosting | AWS ECS on Fargate | AWS ECS on Fargate |
| Est. cost / month | $1,365–$14,731 | $38,500–$157,328 |


**Internal tool, own servers vs cloud** (preset `internal_tool`; changed answer: `deployment`: on_prem → cloud)

| Layer | Before | After |
|---|---|---|
| Frontend | Server-rendered HTML + HTMX | Server-rendered HTML + HTMX |
| Backend | Python + Django | Python + Django |
| Database | SQLite (+ Litestream backups) | SQLite (+ Litestream backups) |
| Hosting | On-prem VMs + Docker Compose | **Render** |
| Est. cost / month | $0–$153 | $7–$32 |

- Hosting: On-prem VMs + Docker Compose is now ruled out: On-premises option; you chose public cloud.
