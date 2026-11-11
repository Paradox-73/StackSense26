# StackSense reference

Long-form reference material moved out of the [README](../README.md): troubleshooting, the app walkthrough, project layout, language-model configuration, the full scoring description, the input model, the knowledge base and the API.

Contents: [Troubleshooting](#troubleshooting), [Using the app](#using-the-app), [Project layout](#project-layout), [Language-model configuration](#language-model-configuration), [How scoring works](#how-scoring-works), [Input model](#input-model), [Knowledge base](#knowledge-base), [API](#api), [Benchmark](#benchmark)

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python` is not found (Windows) | Use `py run.py`, or install Python from <https://www.python.org/downloads/> with "Add python.exe to PATH" ticked. |
| `could not create .venv` (Debian/Ubuntu) | `sudo apt install python3-venv`, delete the `.venv` folder, run again. |
| "the .venv folder is broken" | The folder was copied from another computer or Python was reinstalled. Delete `.venv` and run again. |
| `pip install failed` | Check the internet connection. On Python 3.15 or newer, install Python 3.12 or 3.13 and retry. |
| "port 8000 is already in use" | The launcher moves to the next free port and prints it; or pass `--port 8080`. |
| Browser does not open | Open the printed address yourself, e.g. <http://127.0.0.1:8000>. |
| No server wanted | `python3 cli.py --all` prints all example recommendations in the terminal. |

## Using the app

1. **Live result.** A stack for the default answers appears on page load. Every answer change re-runs the engine after 250 ms; older requests are cancelled and late responses ignored. Cards whose pick changed turn gold and show "was X", with the reason under the sliders.
2. **Seven quick questions** (what you build, daily users, budget, team and languages, compliance, where it must run, must-haves), or an example from the row above them. "Refine with all 42 questions" opens the full form; on desktop the result stays pinned beside it while you scroll.
3. **Not sure.** Every question has a *Not sure* option. The default is used, and the *Depends on* panel re-runs the engine across that answer's plausible values (one answer at a time, at most 48 runs). It lists the layers that are robust, the value at which each other layer flips (e.g. "Hosting: Netlify up to 100/day, Vercel at 1k/day, ..."), and *Pick* buttons that set the answer. Each question also has a *Help me choose* hint.
4. **Glossary.** Every technical term (HIPAA, GDPR, DPDP, PCI-DSS, SOC 2, DAU, peak req/s, p95 latency, consistency, availability, BaaS, serverless, lock-in, data residency, ...) has an (i) button with a plain-English definition, who it applies to, and an official source (`data/glossary.json`). Esc or a click outside closes it.
5. **What if.** The users, budget and team sliders and the chips/fields are the same answer: moving a slider moves the chip (or shows "Custom: 500/day") and the refine field, and the reverse.
6. **Details.** *Why these picks* (per-answer score trace and sources), *Growth path* (the stack at 1x, 10x and 100x your users), *Architecture* (generated diagram), *Cost*, *Alternatives*, *Inputs & weights*; export as JSON, Markdown or Print/PDF.
7. **Share.** *Copy link* puts the answers you gave in the address (`#a=...`); opening it on another machine gives the same four picks. *Answers (JSON)* downloads the same answers as a small file and *Load answers* reads one back (a scenario file with an `input` object or a bare answers object also works; unknown keys are listed and ignored).
8. **Mobile.** A bar at the bottom always shows the four picks and the cost; tap it to jump to the full result.
9. **Scenario file** (`/scenario`). Every field of the problem statement's standard schema as a form, with the default of each empty field shown. *Load scenario file* reads a JSON file (unknown or invalid values are kept and reported), the P1-P6 and E1-E9 buttons load the example files, *Run scenario* shows the standard output, and *Download output JSON* saves it.

## Project layout

```
stacksense/
  run.py                 one-command launcher (creates .venv, installs, serves)
  cli.py                 command-line interface
  requirements.txt       run-time and test packages (requirements.lock.txt: exact versions)
  requirements-dev.txt   report-building packages only (PDF, screenshots)
  app/main.py            FastAPI routes
  app/static/            index.html, app.js, share.js, styles.css, scenario.html/.js/.css, fonts/ (no build step)
  engine/
    standard.py          the standard scenario format: validate, map to answers, build the section 4 output
    kb.py                loads + validates the knowledge base, criterion lists
    profile.py           input normalisation and derived quantities
    conflicts.py         contradictory/risky input detection
    scoring.py           weights, hard constraints, per-technology scoring
    stack.py             combination search + compatibility rules
    explain.py           reasons, trade-offs, risks, attributions
    advice.py            architecture style, supporting services, cost, split hosting
    recommender.py       pipeline + counterfactuals
    sensitivity.py       "Not sure" analysis and "which question matters next"
    whynot.py            "Why not X?": pin a layer or a whole stack and compare with the pick
    robustness.py        how often each pick holds when every knowledge-base score is shifted by seeded noise
    export.py            Markdown and decision-record export
    llm.py               optional OpenAI-compatible chat client (urllib, model fallback, disk cache, daily request cap)
    brief.py             project description -> answers: schema and evidence-quote checks around the LLM step
    brief_rules.py       the pattern reader for the same job (numbers, money, skills, regions, compliance, app type)
    summary.py           facts from the engine result, LLM summary, technology and number validator, template fallback
    whatif.py            plain-English what-if question -> answer changes
    parallel.py          worker processes that spread the many engine re-runs of /api/next (no model involved)
  data/
    kb/frontend.json backend.json database.json hosting.json compat_rules.json
    questions.json       questionnaire = input schema (defaults, ranges, hints, "why we ask", sources)
    glossary.json        plain-English definitions of every technical term, with official sources
    presets.json         14 ready-made scenarios
    rubric.json          the 1/3/5 anchors of every scored criterion
    explain_templates.json  sentence templates for the justification paragraphs
    llm_cache/           saved model answers, one small JSON file each (optional, created on first use)
  scenarios/             public/ (P1-P6 from the problem statement), edge/ (E1-E9, one per edge-case category)
  outputs/               the engine's output for P1-P6 (python cli.py --scenario scenarios/public --out outputs)
  docs/                  architecture.svg, pipeline.svg (the two figures above)
  tests/                 pytest suite + 8 scenario fixtures (tests/scenarios/*.json); tests/benchmark/ holds the answer key
  tools/                 build_assets.py (samples, tables, appendices), build_report.py (counts + PDF), capture_screenshots.py,
                         bench.py, llm_baseline.py, fuzz.py, question_influence.py, robustness_report.py, check_links.py, run_scenarios.py,
                         package_submission.py (the submission folder), baseline_grading.py, demo_captions.py (video captions), ci_launch_check.py
  report/                report.md (the PDF's source), StackSense_Report.pdf, facts.json, samples/, screenshots/, sources.md
```

## Language-model configuration

**Configuration** (environment variables, or a `.env` file in the repository root; `.env` is git-ignored and `.env.example` lists the names):

| Variable | Meaning | Default |
|---|---|---|
| `STACKSENSE_LLM` | `off` (or `0`, `false`, `no`) switches every language-model feature off: no request, no saved answer. `run.py --no-llm` and `cli.py --no-llm` set it. The stack is the same either way. | on |
| `STACKSENSE_LLM_API_KEY` or `OPENROUTER_API_KEY` | API key. Never logged or returned by the API. | none (LLM features off) |
| `STACKSENSE_LLM_BASE_URL` | Any OpenAI-compatible chat API | `https://generativelanguage.googleapis.com/v1beta/openai` (Google Gemini free tier) |
| `STACKSENSE_LLM_MODELS` | Comma-separated model chain, tried in order after a 404, 429, 5xx or a 30 s timeout | `gemini-3.5-flash-lite`, `gemini-flash-lite-latest`, `gemini-2.5-flash-lite` |
| `STACKSENSE_LLM_DAILY_LIMIT` | Most real network requests per calendar day, counted in `data/llm_cache/.usage.json` (git-ignored, not in the zip). When it is reached the app behaves as if there were no key, but saved answers are still served. `0` means no limit. | `200` |

Two ready-made setups are in `.env.example`: the Gemini free tier above, and OpenRouter (`STACKSENSE_LLM_BASE_URL=https://openrouter.ai/api/v1` with models such as `google/gemma-4-31b-it:free`). Saved answers are keyed by the model chain, so changing the chain asks the provider again.

The client (`engine/llm.py`) uses only the Python standard library (`urllib`). `GET /api/health` reports `llm_enabled`.

**LLM-only baseline.** `python tools/llm_baseline.py` asks the same model chain for the four picks of each of the 40 benchmark briefs (no rule engine), scores them with the same rule as `tools/bench.py`, and writes `benchmark/llm_baseline.json`. It writes after every brief and skips briefs already in the file, so it can be run in pieces under a daily request limit (`--limit 10`); `--grade` grades the saved stacks with the rule engine (hard-requirement breaks, minimum cost, over-budget, score gap; the engine's own picks are graded the same way as a check) with no request; `--repeat` asks the same briefs again with the cache bypassed into `benchmark/llm_baseline_repeat.json` (resumable) to measure how often the model gives the same stack twice; `--show` prints every metric next to the rule engine without any request.

## How scoring works

The pipeline runs in seven stages ([pipeline figure](pipeline.svg)). Stage 7 covers supporting services, cost and the explanation.

1. **Normalise inputs** (`profile.py`)
   - Missing answers get documented defaults; each default is listed as an *assumption*.
   - Non-numbers, negative or extreme values and unknown options are clamped or replaced, and each one produces a *warning*.
2. **Derive quantities**
   - Peak RPS, if not given = DAU x requests-per-user-per-day for the app type / 86,400 x peak factor (e.g. e-commerce uses x10 for sale spikes).
   - Scale tier 0-5 = max(tier from DAU, tier from peak RPS). Thresholds: DAU 1k/10k/100k/1M/10M and RPS 5/50/500/5k/50k. The label names the measure that set the tier ("Medium (10k-100k daily users)" or "Large (500-5,000 req/s at peak)"); the database tier label names the data size when data sets it ("Small (10-100 GB of data)").
   - Database tier = max(tier from the 12-month data volume, scale tier), one tier lower for read-heavy apps because caches and CDNs absorb reads.
   - Data volume, if not given = about 0.2-4 MB of database rows per daily user a month by app type (0.5 MB for a SaaS, 1.5 MB for a social feed, ~4 MB for a device reporting once a minute) at the user count typical of the scale tier, with one month of growth at launch. It is the same at every user count of a tier, so the growth path agrees with every run. A content site keeps its own default (1 GB + 0.1 GB a month).
   - Implied requirements: fintech forces strong consistency, and fintech in India adds Indian data residency (RBI payment-data rule); a mobile-first app adds iOS and Android; a realtime-collaboration app forces realtime = core.
3. **Detect conflicts** (`conflicts.py`)
   - 22 cross-field checks (53 warning codes across the whole engine), including: 1 developer + microservices, HIPAA on a ₹0 budget, 99.99% availability with 2 people, a 20 ms target across continents, EU + India residency together, and a peak RPS that contradicts the DAU.
   - Each check states how it was resolved.
   - Resolution priority: compliance > deployment model > physics and team capacity > budget and preferences.
4. **Build criterion weights** (`scoring.py`)
   - There are 19 criteria (cost at your scale, scalability, learning curve, ops burden, maturity, realtime, performance, SEO, velocity, hiring, offline, structure, interactivity, skill match, portability, data-model fit, consistency fit, region coverage, compliance maturity).
   - Each criterion's weight = baseline (the standard weight every project starts from) + contributions from specific answers. Example: "SEO critical" adds +4 to the SEO weight; a 1-person team adds +2.5 to ops burden.
   - Every contribution is stored together with the answer that caused it.
   - **Cost at your scale** is absolute, not ranked against the other options: `score = 5 - 4 * min(1, ln(1 + bill / share) / ln(31))`, where `share` is the layer's slice of the budget (60% hosting/backend, 40% database). $0 scores 5 and a bill of 30x the share scores 1. An option's cost score depends only on its own bill, so it moves smoothly as users grow.
   - **Team cloud skills**: if the team lists AWS, GCP or Azure, hosting on that cloud gets skill match 4.5+ and a +3.5 bonus (half an explicit cloud preference); hosting on a different hyperscaler is capped at 2.5, because a generic skill such as Docker does not carry IAM, networking and billing knowledge across clouds.
   - **Compliance maturity** (hosting and BaaS backends) has zero weight unless HIPAA or PCI-DSS data is in scope. It then gets +1, +1.5 more at 100k+ DAU and +2 more at 1M+ DAU, because breach reporting duties ([HHS breach rule](https://www.hhs.gov/hipaa/for-professionals/breach-notification/index.html)) and audit depth ([PCI DSS Level 1 assessments](https://www.pcisecuritystandards.org/document_library/)) grow with volume. Each host is scored 1-5 from its published attestations, native audit logging and dedicated-tenancy options (`compliance.maturity` in `data/kb/hosting.json`, with sources). AWS, GCP and Azure score 5, Vercel 3, Render/Fly.io 2. A self-hosted backend framework scores 5 (it adds no data processor of its own); a BaaS adds a second vendor in the regulated data path (Supabase 3, Firebase 2). Result: the HIPAA telehealth example (an AWS-skilled team) stays on AWS ECS + Django from 20k to 10M DAU, instead of Vercel + Supabase.
5. **Hard constraints, then weighted scoring**
   - Hard constraints remove an option before scoring: compliance (HIPAA BAA, PCI attestation, SOC 2), data residency, deployment model, platform, ACID consistency, data-model mismatch, an in-memory store as the system of record for more than 10 GB, a single-node database at 99.95%+ availability (or at a stated 99.9% with 1,000+ daily users), a static (no database, no server code) option unless users only read, scale ceiling and lock-in.
   - Constraints that come from preferences are relaxed only if a layer would otherwise be empty. Compliance is never relaxed.
   - `base = Σ w_c · s_c / Σ w_c`, rescaled to 0-100.
   - Adjustments with stated reasons are then added: near the scale ceiling, a minimum price above the layer's budget share (penalty = 6 x ln(overshoot), so 4x over budget costs less than 40x over), needs a bigger team, a preferred cloud, an in-memory store holding too much data, and so on.
   - Because each weight is a sum of per-answer contributions, the score splits exactly into **per-answer contributions**. The UI shows this as "Which of your answers drove this score".
6. **Stack-level search** (`stack.py`)
   - Takes the top 5 options per layer, which gives 5^4 = 625 combinations.
   - Each combination is scored with 65 compatibility rules: synergies (Next.js + Vercel, Supabase + Postgres, DynamoDB + Lambda), caveats (Lambda + Postgres needs RDS Proxy, Next.js on Cloudflare needs OpenNext, WebSockets on Vercel are in beta) and conflicts (WebSockets on Netlify/Lambda, DynamoDB off AWS, HTMX with a BaaS, SQLite on multi-instance hosts).
   - `stack score = (Σ layer scores + Σ rule deltas) / 4`.
   - **Ties**: stacks within 1 stack point of the top score are treated as tied (a stack point is one point of the 0-100 stack score, the average of the four layer scores; the 1-point band is the tie margin), because the weights come from planning estimates. A tie goes first to the stack with the fewest misses, where a miss is a layer penalised by a requirement you stated (availability, latency, SEO, offline, realtime, compliance, data shape, data volume or consistency; defaults left unanswered do not count, except a single-file database under the default 99.9% availability target, because that stack is priced as one instance with no redundancy) and a minimum bill over the budget counts as one more, then to fixed preferences: your preferred cloud, team skill match (layers whose technology the team already uses; adjacent skills are in the score already), hiring pool (when no skills are listed), your most important inputs (the frontend's points through the answers that weight SEO, interactivity and offline use most, heaviest answer first, a gap under 1 stack point ignored) and lower vendor lock-in (the lock-in scores of the four picks added up, lower is better; skipped when your lock-in tolerance is high); past those the higher score wins. The summary and the runner-up text say when a tie decided the pick, list the criteria each option is stronger on, and say when to choose the other one.
   - **Growing users**: every run also works out the recommendation at all six scale tiers for the same answers, smallest first, and its own answer is the entry for its tier, so runs at different user counts agree. A stack that would go back to a technology a smaller tier already left is passed over for one that does not when that one scores within 4 points of the top. Where the path leaves a technology and later comes back to it, the technology is held through the tiers in between if it stays within 4 points of the top there; otherwise the return is avoided when a stack without it is within 8 points. An earlier pick is not kept for any other reason. Measured scope: every preset passes `tests/test_stability.py` (no layer returns to an earlier pick from 100 to 10M daily users); in `python tools/fuzz.py --n 1000 --growth-n 100` (seed 2026), 0 of 100 random growth walks have a layer that returns to an earlier pick, and the other 14 properties have 0 violations over 1,000 projects.
   - **Budget**: if the chosen stack's estimated minimum bill is over the budget, the best stack that keeps the same backend and database, fits the budget and scores at most 5 points lower is chosen instead (usually a cheaper host), and the summary says so. `tests/test_static_and_budget.py` checks that raising the budget never moves a preset to a stack over the new budget.
   - **Split hosting**: a frontend platform (Vercel, Netlify, Cloudflare) runs a server framework (Express, NestJS, FastAPI, Go, ...) only as short-lived functions. From Large scale (100k+ daily users), or when realtime is core, the API gets its own long-running host: the best-scoring container, PaaS or Kubernetes host that passed the hard constraints, plus the compatibility rules that do not involve the frontend. The frontend platform keeps the pages. The hosting card, the cost estimate (an "API host" line), the summary and the diagram show both hosts (`tests/test_split_hosting.py`).
   - The two alternatives per layer come from swapping that one layer in the winning stack and re-scoring the whole stack.
7. **Supporting services, cost and explanation**
   - *Supporting services and cost* (`advice.py`):
      - Services follow the stack and the hard inputs: nothing cloud-only on-premises, nothing without an Indian or EU region under a residency rule, nothing without a BAA under HIPAA, portable services under hybrid deployment (`tests/test_services_lint.py` checks presets, the extra scenarios and 500 random inputs).
      - Ops budget (a judgement call): a team of 1-2 runs at most 1 extra system (cache, secondary store, analytics store, search engine, ingestion log) beside its app and database, 3-5 people 2, 6-12 people 4. The rest are listed under "Add later" with the trigger for adding them; compliance services are never deferred.
      - Each cost line states its basis: price band for the scale tier, deploying seats, an availability multiplier for capacity you run yourself (x1.5 at 99.9%, x2 at 99.95%, x3 at 99.99%; only for a stated target, since the 99.9% default is a goal), a database bill of at least its storage (~$0.115 per GB-month, one to three copies) with the band's top sized by the data when traffic sets the tier, add-ons (cache, job queue, secondary store, warehouse) at the app's own tier, stored GB and per-operation pricing for a BaaS or Firestore, and usage for model inference, video (per minute delivered for a managed video service; CDN data transfer in volume tiers plus transcoding for storage + transcoder + CDN), maps, SMS and media delivery.
   - *Explanation* (`explain.py`, `advice.py`, `recommender.py`):
      - A 3-5 sentence justification paragraph per layer, built from fixed templates in `data/explain_templates.json`. It quotes the project's numbers (users, peak requests/s, data size, availability, budget) and facts from the pick's knowledge-base entry (BAA, long-running processes, consistency, data-model fit).
      - Why: the technical criteria where the pick beats the layer average most, with the answers that raised those weights. Team skill match comes last and says whether the match is direct or only related.
      - For every switch (what-if note, counterfactual, "Depends on" entry): its cause, i.e. the exclusion, the criterion or penalty that moved the gap, or the stack rule.
      - "How stable is this pick?": 30 seeded re-runs per noise level with every 1-5 knowledge-base score shifted by up to ±0.25 and ±0.5, counting how often each layer keeps its pick (`engine/robustness.py`; `python tools/robustness_report.py` prints the table for every preset). The seed comes from the answers, so the percentages repeat.
      - "Why not X?" per layer: the runner-up, the layer's top scorer and the widely used options, each with the stack gap or the rule that excludes it, plus the full ranking. In the app, any option (or a whole stack) can be compared: the search re-runs with it fixed, and the single answer changes that would make it the pick are listed (`engine/whynot.py`). An option a hard constraint excludes is scored anyway and marked approximate.
      - Trade-offs and risks.
      - A runner-up comparison. Its listed contributions add up to the margin, in stack points.
      - The margin over the runner-up, labelled clear (4+ points), solid (1.5-4) or close call (under 1.5); the listed answers behind it, plus an "other answers and rounding" remainder, add up to that margin.
      - The architecture style (modular monolith, service-oriented, serverless or BaaS-first) with the peak load, data size and availability it is sized for, the availability approach, and "How the parts fit": the request path, sign-in, where the data (and any PHI or card data) lives, and how a change is deployed.
      - Supporting services: cache, realtime, secondary stores, ingestion buffer, search, payments, object storage, auth, push notifications, model serving, observability.
      - A cost estimate (USD and INR) compared with the budget.
      - **Counterfactuals**: up to 14 single-answer changes (budget x0.2/x5, 10x users, a solo developer or 15 engineers, a 4-week deadline, realtime, SEO, on-prem, low lock-in, HIPAA, India residency, no skills). The engine re-runs for each one and lists only the changes that alter the stack.

## Input model

The questionnaire is defined in `data/questions.json`. That file also drives defaults and validation, so the UI and the engine cannot drift apart. Every field has help text, a "why we ask" explanation and sources.

| Step | Fields |
|---|---|
| Product | project name, app type (13 archetypes), platforms (web/iOS/Android) |
| Scale & data | DAU, peak RPS (optional, derived), data volume, growth/month, read/write mix, data shapes (ordered, first = primary), consistency |
| Experience & reliability | realtime (none/some/core), p95 latency target, SEO, offline, availability (99-99.99%), user regions |
| Team & delivery | team size, existing skills (33 options + free text), time to MVP, architecture preference |
| Budget & constraints | monthly budget, currency (USD/INR), deployment (cloud/hybrid/on-prem), preferred cloud, lock-in tolerance, compliance (GDPR, DPDP, HIPAA, PCI-DSS, SOC 2, India/EU residency) |

## Knowledge base

`data/kb/*.json` holds 11 frontends, 14 backends, 15 databases and 24 hosting platforms (64 technologies) and 65 compatibility rules. Each entry has:

- 1-5 scores per criterion
- compliance maturity 1-5 with a note and sources (hosting and BaaS only)
- skills and related skills (used for team skill match)
- a scale ceiling and a minimum team size
- lock-in (1-5)
- cost bands in USD/month for six scale tiers
- compliance flags (HIPAA BAA and minimum price, PCI, SOC 2, GDPR DPA) and regions
- consistency model and data-model fit (databases only)
- managed offerings per cloud
- strengths and weaknesses (a line can carry a `when` condition, e.g. only for Indian users or only on a Next.js stack, so it is shown only where it applies) and official documentation URLs

`validate_kb()` checks the schema at server start-up and in the tests.

**Adding a technology:** add an entry to the right JSON file and run `pytest`. Code changes are only needed for a new criterion.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status, knowledge-base counts, `llm_enabled` and `llm_switched_off` |
| POST | `/api/scenario` | body = a scenario in the standard schema (problem statement 3.2), returns the section 4 output; invalid input gives status `invalid_input` with field errors, never an HTTP error |
| GET | `/api/scenario/fields` | every field of the standard schema with kind, required, default, allowed values and meaning (the scenario page's form) |
| GET | `/api/scenario/examples`, `/api/scenario/examples/{name}` | the example files in `scenarios/public` (P1-P6) and `scenarios/edge` (E1-E9) |
| GET | `/api/questions` | questionnaire/input schema |
| GET | `/api/presets` | scenario presets |
| GET | `/api/kb` | full knowledge base + rules |
| POST | `/api/recommend` | body = answers (any subset), returns the full explained recommendation; `?lite=1` skips counterfactuals |
| POST | `/api/sensitivity` | body = `{"answers": {...}, "unknown": ["dau", ...]}`, returns per unknown answer and layer: robust, or which values flip the pick |
| POST | `/api/next` | body = `{"answers": {...}}` (only the answers given), returns the unanswered questions ranked by the layers they can still change, the ones that cannot, and whether the stack is settled |
| POST | `/api/switch` | body = `{"before": {...}, "after": {...}}`, returns for each layer whose pick differs the cause: an exclusion, the criterion or penalty that moved the gap, or a stack rule |
| POST | `/api/whynot` | body = `{"answers": {...}, "pins": {"hosting": "netlify"}}` (one layer, or all four to grade a stack), returns the gap to the recommendation, the criteria, rules and cost behind it, any exclusion, and the single answer changes that would make that choice the pick |
| POST | `/api/robustness` | body = answers, returns for each layer how often the pick holds over 30 seeded runs with every knowledge-base score shifted by ±0.25 and by ±0.5 |
| GET | `/api/glossary` | definitions, "who it applies to" and official sources for every technical term |
| POST | `/api/brief` | body = `{"text": "..."}`, returns the answers read from the description (value, source `rule` or `llm`, quote) and the questions still unknown; works without a key (pattern reader only) |
| POST | `/api/summary` | body = answers, returns a plain-English summary per layer and overall, `source` (`llm` or `template`) and `checked`; the template explanation is returned without a key or when the model's text fails the check |
| POST | `/api/whatif` | body = `{"answers": {...}, "question": "what if ..."}`, returns the answer changes the question implies (with quotes and previous values) |
| POST | `/api/export/markdown` | same input, returns a Markdown report |
| POST | `/api/export/adr` | same input, returns one architecture decision record per layer (context, decision, alternatives considered, consequences, revisit when) |

Conventions of the pattern reader (`engine/brief_rules.py`), each shown beside the answer as a note:

- A monthly or audience count is scaled to daily users at 20% (`DAU_PER_MAU`); a count of staff ("800 staff users", or "50 employees" in a brief that calls the app internal) is taken as daily users in full, because an internal tool is used on working days.
- A fleet of devices, sensors or vehicles ("50,000 trucks reporting GPS every 5 seconds") sets the app type to IoT/telemetry, counts every device as active, and gives peak requests per second = devices / reporting interval (10,000 a second).
- Number words ("two Flutter devs", "a dozen engineers") give the team size; "AWS shop" and "all-in on AWS" set the cloud preference; "free tier please" and "zero budget" set the budget to 0; "each customer gets their own database" sets isolated tenancy.
- Data retention ("keep data for 2 years") and expected growth ("50k users in two years") are not read, because the questionnaire has no field for them.

Interactive docs are at `/docs` (generated by FastAPI).

`/api/next` re-runs the engine about 90 times (one run per plausible answer of each open question). On the development machine (12 logical cores) it takes about 1 to 2 seconds in one process and about 0.4 second when the server spreads the runs over worker processes; with other programs keeping the processor busy, both can take two to three times longer. The server starts the workers by default on a computer with 4 or more cores, and an answer set already asked is served from a cache. Set `STACKSENSE_WORKERS=0` to keep everything in one process, or a number to choose how many workers start. The answers are the same either way.

## Benchmark

`python tools/bench.py` scores the engine against `tests/benchmark/answer_key.json`: 40 project briefs with a best pick and an acceptable set per layer, from an answer key written before measurement, with sources. **Who wrote the labels:** a language model playing three architect personas (a pragmatic startup CTO in Bangalore, an enterprise solutions architect, a senior cloud/platform engineer), blind to the engine (no access to its code or outputs). They are not human raters, and the Krippendorff alpha of 0.91 printed by `tools/bench.py` describes agreement between those three personas only. (The key's SHA-256 is in `tests/benchmark/answer_key.sha256`; it was recomputed once, when the key's description was reworded to say this; no label changed.) Add `--briefs` for one line per brief. Ten briefs are held out and were not used for tuning. Result: 81% top-1 (128 of the 158 layer picks that have a best pick; 2 layer picks, both in brief A05, have no majority best pick) and 96% acceptable (154 of all 160 layer picks); held-out 72% and 95% (60% and 80% before the rule fixes in `tests/benchmark/baseline_before_fixes.json`). `tests/test_benchmark.py` fails if the rates drop.
