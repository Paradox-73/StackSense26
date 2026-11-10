## Appendix B. Question catalogue and traceability

Every question the app asks, generated from `data/questions.json`. The last five columns come from the question-influence study (`tools/question_influence.py`): the engine was re-run with each other value of one question while every other answer stayed fixed, and a run counts when at least one of the four picks changed. F, B, D and H are the shares of re-runs in which the frontend, backend, database or hosting pick changed. The reason each question is asked is in the app (the Why we ask button) and in `data/questions.json`; Appendix E gives it by group.

<div class="appb">

### B.1 Product

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 1 | Project name<br>`project_name` | Free text; names the project only | - | names only | - | - | - | - |
| 2 | Application type<br>`app_type` | One of 13; default B2B / B2C SaaS | yes | 38% | 13% | 17% | 10% | 8% |
| 3 | Client platforms<br>`platforms` | Any of 3; default Web | yes | 55% | 55% | 3% | 1% | 0% |
| 4 | What do users do?<br>`user_actions` | Any of 4; default Read or browse published content, Sign in to their own account, Create or upload things | - | 5% | 1% | 4% | 2% | 3% |
| 5 | Special workloads<br>`special_workloads` | Any of 7; default none | - | 4% | 1% | 2% | 1% | 2% |
| 6 | Work that runs in the background<br>`background_work` | One of 3; default None, or short jobs of a few minutes | - | 20% | 2% | 4% | 3% | 19% |
| 7 | Do several customer organisations share the app?<br>`tenancy` | One of 3; default No: one organisation, or a consumer app | - | 18% | 2% | 5% | 12% | 4% |

*Note:* Special workloads changes a pick in 4% of re-runs; its main effect is on the supporting services and the cost estimate (video, maps, SMS and file delivery are priced separately).

### B.2 Scale & data

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 8 | Daily active users<br>`dau` | Number (users/day), 0 to 2,000,000,000; default 1,000 | yes | 24% | 2% | 8% | 10% | 14% |
| 9 | Peak requests per second<br>`peak_rps` | Number (req/s), 0 to 10,000,000; optional, derived when left empty | - | 17% | 2% | 6% | 6% | 9% |
| 10 | Traffic pattern<br>`traffic_pattern` | One of 3; default Typical for the app type | - | 3% | 0% | 1% | 1% | 1% |
| 11 | How much of the traffic can be cached?<br>`cacheable_share` | One of 4; default Typical for the app type | - | 3% | 0% | 1% | 1% | 1% |
| 12 | Data volume at launch<br>`data_volume_gb` | Number (GB), 0 to 100,000,000; default 5 | - | 12% | 1% | 2% | 10% | 3% |
| 13 | Data growth per month<br>`data_growth_gb_month` | Number (GB/month), 0 to 10,000,000; default 1 | - | 9% | 0% | 2% | 7% | 2% |
| 14 | Do people mostly look at data, or mostly add and change it?<br>`read_write` | One of 3; default About even | - | 16% | 2% | 4% | 12% | 3% |
| 15 | What kinds of data do you store?<br>`data_shapes` | Any of 8; default Tables of related records | - | 66% | 2% | 6% | 65% | 5% |
| 16 | If two people change the same thing at the same moment, must everyone see one agreed result at once?<br>`consistency` | One of 2; default Yes: exactly one wins and everyone sees it at once | - | 16% | 1% | 1% | 15% | 2% |

### B.3 User experience & reliability

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 17 | Realtime needs<br>`realtime` | One of 3; default None | yes | 30% | 6% | 16% | 7% | 9% |
| 18 | Users connected at the same moment, at peak<br>`peak_concurrent` | Number (users), 0 to 100,000,000; optional, derived when left empty | - | 21% | 3% | 8% | 7% | 10% |
| 19 | How fast must the app answer?<br>`latency_target_ms` | Number (ms), 5 to 60,000; default 300 | - | 22% | 5% | 10% | 3% | 10% |
| 20 | Search engine visibility<br>`seo` | One of 3; default Not needed | yes | 32% | 31% | 1% | 1% | 0% |
| 21 | Offline support required<br>`offline` | Yes or no; default no | yes | 17% | 9% | 2% | 8% | 2% |
| 22 | Availability target<br>`availability` | One of 4; default 99.9% | - | 44% | 4% | 6% | 7% | 39% |
| 23 | Where are your users?<br>`regions` | Any of 5; default none | - | 2% | 0% | 0% | 0% | 2% |

### B.4 Team & delivery

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 24 | Engineering team size<br>`team_size` | Number (engineers), 1 to 5,000; default 3 | yes | 43% | 15% | 30% | 6% | 10% |
| 25 | Existing team skills<br>`team_skills` | Any of 33; default none | yes | 93% | 48% | 83% | 20% | 24% |
| 26 | Time to MVP<br>`timeline_weeks` | Number (weeks), 1 to 520; default 12 | - | 21% | 7% | 11% | 3% | 4% |
| 27 | Architecture preference<br>`architecture` | One of 4; default Decide for me | - | 13% | 1% | 5% | 2% | 9% |

### B.5 Budget, infrastructure & compliance

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 28 | Monthly infrastructure budget<br>`budget_monthly` | Number (per month), 0 to 100,000,000; default 100 | yes | 30% | 3% | 7% | 13% | 18% |
| 29 | Currency<br>`currency` | One of 2; default USD | - | names only | - | - | - | - |
| 30 | Deployment model<br>`deployment` | One of 3; default Public cloud | yes | 68% | 6% | 10% | 11% | 63% |
| 31 | Preferred cloud<br>`cloud_preference` | One of 4; default No preference | - | 29% | 1% | 3% | 5% | 27% |
| 32 | Vendor lock-in tolerance<br>`lock_in_tolerance` | One of 3; default Medium | - | 26% | 9% | 7% | 12% | 7% |
| 33 | Compliance & data residency<br>`compliance` | Any of 7; default none | yes | 15% | 3% | 5% | 4% | 9% |
| 34 | Customers sign in with their company account<br>`enterprise_sso` | Yes or no; default no | - | 2% | 0% | 1% | 0% | 0% |
| 35 | Your top 3 priorities<br>`priorities` | Any of 6; default none | - | 26% | 8% | 13% | 5% | 7% |
| 36 | Existing systems you must keep<br>`existing_systems` | Any of 6; default none | - | 33% | 1% | 4% | 30% | 3% |

</div>

### B.6 Quantities derived from the answers

| Quantity | How it is computed | Decides |
|---|---|---|
| Budget in dollars | budget; if the currency is INR, budget / 96 (a fixed planning rate) | cost fit, budget guard, over-budget warnings |
| Requests per user per day | set by the app type, from 8 to 1,440; 100 if unknown | peak requests per second |
| Peak factor | ecommerce x10, content site x3, iot telemetry x1.5, social network x6; x5 for other app types; steady traffic caps it at 3, spiky traffic raises it to at least 15 | peak requests per second |
| Share reaching the servers | cacheable share: little or unsure x1.0, some x0.6, most x0.2 | peak requests per second (a CDN, a network of caching servers close to users, absorbs the rest) |
| Peak requests per second | daily users x requests per user per day / 86,400 x peak factor x share reaching the servers; a stated peak is used as given (times the share reaching the servers); if it differs from the estimate by more than 30 times, the larger figure is used, except for IoT where the stated rate wins | compute tier, load balancer and cache advice |
| Compute tier (0 to 5) | the higher of the tier of daily users (limits 1,000 / 10,000 / 100,000 / 1,000,000 / 10,000,000) and the tier of peak requests per second (limits 5 / 50 / 500 / 5,000 / 50,000) | price band of every option, scale ceilings, weights |
| Data tier (0 to 5) | data in 12 months = volume + 12 x monthly growth; tier limits in GB 10 / 100 / 1,000 / 10,000 / 100,000 | database choice |
| Database tier | the higher of the data tier and the compute tier, one lower for read-heavy apps (caches absorb reads) | database scale ceiling and write-scaling rules |
| Implied answers | fintech forces strong consistency, and adds Indian data residency when users are in India; realtime collaboration forces realtime to core; mobile-first adds iOS and Android; a DPDP answer is noted as consent and breach duties | hard constraints and weights, each shown as an assumption or a warning |

Every row above is read from `engine/profile.py`, so the table cannot drift from the engine; `tests/test_questions.py` checks that every question except the project name changes at least one pick, cost or warning in the study.
