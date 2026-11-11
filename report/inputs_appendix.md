## Appendix B. Question catalogue and traceability

Every question the app asks, generated from `data/questions.json`. The last five columns come from the question-influence study (`tools/question_influence.py`): the engine was re-run with each other value of one question while every other answer stayed fixed, and a run counts when at least one of the four picks changed. F, B, D and H are the shares of re-runs in which the frontend, backend, database or hosting pick changed. The reason each question is asked is in the app (the Why we ask button) and in `data/questions.json`; Appendix E gives it by group.

<div class="appb">

### B.1 Product

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 1 | Project name<br>`project_name` | Free text; names the project only | - | names only | - | - | - | - |
| 2 | Application type<br>`app_type` | One of 13; default B2B / B2C SaaS | yes | 28% | 10% | 13% | 3% | 6% |
| 3 | Client platforms<br>`platforms` | Any of 5; default Web | yes | 49% | 49% | 3% | 1% | 1% |
| 4 | What do users do?<br>`user_actions` | Any of 4; default Read or browse published content, Sign in to their own account, Create or upload things | - | 9% | 0% | 8% | 5% | 3% |
| 5 | Special workloads<br>`special_workloads` | Any of 8; default none | - | 5% | 0% | 2% | 0% | 4% |
| 6 | Work that runs in the background<br>`background_work` | One of 3; default None, or short jobs of a few minutes | - | 17% | 0% | 4% | 0% | 17% |
| 7 | Machine-learning features<br>`ml_features` | One of 4; default None | - | 1% | 0% | 0% | 0% | 1% |
| 8 | Do several customer organisations share the app?<br>`tenancy` | One of 3; default No: one organisation, or a consumer app | - | 11% | 1% | 2% | 8% | 2% |

*Note:* Special workloads changes a pick in 5% of re-runs; its main effect is on the supporting services and the cost estimate (video, maps, SMS and file delivery are priced separately).

### B.2 Scale & data

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 9 | Daily active users<br>`dau` | Number (users/day), 0 to 2,000,000,000; default 1,000 | yes | 21% | 2% | 3% | 4% | 15% |
| 10 | Peak requests per second<br>`peak_rps` | Number (req/s), 0 to 10,000,000; optional, derived when left empty | - | 17% | 1% | 2% | 4% | 13% |
| 11 | Traffic pattern<br>`traffic_pattern` | One of 3; default Typical for the app type | - | 2% | 0% | 2% | 2% | 0% |
| 12 | How much of the traffic can be cached?<br>`cacheable_share` | One of 4; default Typical for the app type | - | 2% | 0% | 0% | 1% | 2% |
| 13 | Data volume at launch<br>`data_volume_gb` | Number (GB), 0 to 100,000,000; default 5 | - | 10% | 0% | 5% | 8% | 2% |
| 14 | Data growth per month<br>`data_growth_gb_month` | Number (GB/month), 0 to 10,000,000; default 1 | - | 8% | 1% | 4% | 4% | 2% |
| 15 | Do people mostly look at data, or mostly add and change it?<br>`read_write` | One of 3; default About even | - | 10% | 1% | 3% | 6% | 4% |
| 16 | What kinds of data do you store?<br>`data_shapes` | Any of 8; default Tables of related records | - | 65% | 1% | 8% | 65% | 3% |
| 17 | If two people change the same thing at the same moment, must everyone see one agreed result at once?<br>`consistency` | One of 2; default Yes: exactly one wins and everyone sees it at once | - | 5% | 2% | 0% | 3% | 0% |

### B.3 User experience & reliability

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 18 | Realtime needs<br>`realtime` | One of 3; default None | yes | 27% | 4% | 15% | 7% | 8% |
| 19 | Users connected at the same moment, at peak<br>`peak_concurrent` | Number (users), 0 to 100,000,000; optional, derived when left empty | - | 15% | 3% | 4% | 2% | 7% |
| 20 | How fast must the app answer?<br>`latency_target_ms` | Number (ms), 5 to 60,000; default 300 | - | 19% | 8% | 6% | 1% | 6% |
| 21 | Search engine visibility<br>`seo` | One of 3; default Not needed | yes | 41% | 41% | 0% | 0% | 1% |
| 22 | Offline support required<br>`offline` | Yes or no; default no | yes | 12% | 11% | 2% | 4% | 0% |
| 23 | Availability target<br>`availability` | One of 4; default 99.9% | - | 36% | 5% | 2% | 5% | 33% |
| 24 | Where are your users?<br>`regions` | Any of 5; default none | - | 1% | 0% | 0% | 0% | 1% |

### B.4 Team & delivery

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 25 | Engineering team size<br>`team_size` | Number (engineers), 1 to 5,000; default 3 | yes | 36% | 7% | 27% | 2% | 7% |
| 26 | Team experience<br>`team_experience` | One of 4; default Intermediate | - | 14% | 3% | 10% | 1% | 3% |
| 27 | Someone can operate infrastructure<br>`has_devops` | Yes or no; default no | - | 5% | 1% | 3% | 0% | 3% |
| 28 | Existing team skills<br>`team_skills` | Any of 39; default none | yes | 90% | 42% | 82% | 10% | 19% |
| 29 | Time to MVP<br>`timeline_weeks` | Number (weeks), 1 to 520; default 12 | - | 11% | 3% | 7% | 1% | 2% |
| 30 | Architecture preference<br>`architecture` | One of 4; default Decide for me | - | 7% | 1% | 4% | 1% | 4% |

### B.5 Budget, infrastructure & compliance

| # | Question | Answer | Quick | Pick changed | F | B | D | H |
|---|---|---|---|---|---|---|---|---|
| 31 | Monthly infrastructure budget<br>`budget_monthly` | Number (per month), 0 to 100,000,000; default 100 | yes | 19% | 1% | 3% | 3% | 13% |
| 32 | Currency<br>`currency` | One of 2; default USD | - | names only | - | - | - | - |
| 33 | Deployment model<br>`deployment` | One of 3; default Public cloud | yes | 51% | 6% | 8% | 6% | 46% |
| 34 | We run our own VMs in the cloud<br>`self_managed` | Yes or no; default no | - | 32% | 0% | 5% | 3% | 32% |
| 35 | Air-gapped<br>`air_gapped` | Yes or no; default no | - | 63% | 3% | 8% | 8% | 63% |
| 36 | Preferred cloud<br>`cloud_preference` | One of 5; default No preference | - | 41% | 2% | 7% | 6% | 41% |
| 37 | Must use this cloud<br>`cloud_required` | Yes or no; default no | - | 6% | 0% | 0% | 0% | 6% |
| 38 | Vendor lock-in tolerance<br>`lock_in_tolerance` | One of 3; default Medium | - | 30% | 10% | 7% | 12% | 6% |
| 39 | Compliance & data residency<br>`compliance` | Any of 9; default none | yes | 11% | 0% | 2% | 3% | 10% |
| 40 | Customers sign in with their company account<br>`enterprise_sso` | Yes or no; default no | - | 1% | 0% | 1% | 0% | 0% |
| 41 | Your top 3 priorities<br>`priorities` | Any of 8; default none | - | 19% | 5% | 9% | 3% | 5% |
| 42 | Existing systems you must keep<br>`existing_systems` | Any of 6; default none | - | 30% | 1% | 4% | 27% | 1% |

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
