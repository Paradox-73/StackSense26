# Question influence

Method: 14 preset projects and 1000 seeded random projects (seed 2026). For each project and each question, the engine was re-run with every other value of that one question, all other answers held fixed (135,321 engine runs in 5798.2 s). A run counts as changing the stack when at least one of the four picks differs from the base run.

Caveats: team skills and platforms are varied as whole sets, which inflates their rate compared with a single yes/no answer. Budget is varied from $0 to $10,000. Rates depend on the base projects, so the sample is part of the result.

| Question | Changed a pick | Changed only cost or warnings | Projects where it changed a pick | Frontend | Backend | Database | Hosting |
|---|---|---|---|---|---|---|---|
| Existing team skills | 93% | 0% | 100% | 48% | 83% | 20% | 24% |
| Deployment model | 68% | 0% | 100% | 6% | 10% | 11% | 63% |
| What kinds of data do you store? (pick the main kind first) | 66% | 8% | 100% | 2% | 6% | 65% | 5% |
| Client platforms | 55% | 8% | 99% | 55% | 3% | 1% | 0% |
| Availability target | 44% | 38% | 75% | 4% | 6% | 7% | 39% |
| Engineering team size | 43% | 14% | 80% | 15% | 30% | 6% | 10% |
| Application type | 38% | 32% | 86% | 13% | 17% | 10% | 8% |
| Existing systems you must keep | 33% | 46% | 75% | 1% | 4% | 30% | 3% |
| Search engine visibility | 32% | 25% | 48% | 31% | 1% | 1% | 0% |
| Realtime needs | 30% | 7% | 44% | 6% | 16% | 7% | 9% |
| Monthly infrastructure budget | 30% | 38% | 55% | 3% | 7% | 13% | 18% |
| Preferred cloud | 29% | 41% | 47% | 1% | 3% | 5% | 27% |
| Vendor lock-in tolerance | 26% | 1% | 39% | 9% | 7% | 12% | 7% |
| Your top 3 priorities (first = most important) | 26% | 0% | 54% | 8% | 13% | 5% | 7% |
| Daily active users (or active devices) | 24% | 57% | 52% | 2% | 8% | 10% | 14% |
| How fast must the app answer? (slowest 1 in 20 requests, ms) | 22% | 21% | 47% | 5% | 10% | 3% | 10% |
| Users connected at the same moment, at peak (optional) | 21% | 36% | 41% | 3% | 8% | 7% | 10% |
| Time to MVP | 21% | 9% | 43% | 7% | 11% | 3% | 4% |
| Work that runs in the background | 20% | 1% | 29% | 2% | 4% | 3% | 19% |
| Do several customer organisations share the app? | 18% | 0% | 29% | 2% | 5% | 12% | 4% |
| Peak requests per second (optional) | 17% | 51% | 28% | 2% | 6% | 6% | 9% |
| Offline support required | 17% | 21% | 18% | 9% | 2% | 8% | 2% |
| If two people change the same thing at the same moment, must everyone see one agreed result at once? | 16% | 10% | 17% | 1% | 1% | 15% | 2% |
| Do people mostly look at data, or mostly add and change it? | 16% | 17% | 24% | 2% | 4% | 12% | 3% |
| Compliance & data residency | 15% | 29% | 30% | 3% | 5% | 4% | 9% |
| Architecture preference | 13% | 28% | 25% | 1% | 5% | 2% | 9% |
| Data volume at launch | 12% | 33% | 24% | 1% | 2% | 10% | 3% |
| Data growth per month | 9% | 24% | 18% | 0% | 2% | 7% | 2% |
| What do users do? | 5% | 0% | 12% | 1% | 4% | 2% | 3% |
| Special workloads | 4% | 54% | 11% | 1% | 2% | 1% | 2% |
| Traffic pattern | 3% | 10% | 4% | 0% | 1% | 1% | 1% |
| How much of the traffic can be cached? | 3% | 7% | 5% | 0% | 1% | 1% | 1% |
| Where are your users? | 2% | 31% | 5% | 0% | 0% | 0% | 2% |
| Customers sign in with their company account (SSO) | 2% | 3% | 2% | 0% | 1% | 0% | 0% |

## Presets only

| Question | Changed a pick | Changed only cost or warnings | Projects where it changed a pick | Frontend | Backend | Database | Hosting |
|---|---|---|---|---|---|---|---|
| Existing team skills | 90% | 0% | 100% | 38% | 76% | 12% | 55% |
| What kinds of data do you store? (pick the main kind first) | 66% | 2% | 100% | 0% | 20% | 65% | 9% |
| Deployment model | 61% | 0% | 100% | 7% | 14% | 7% | 54% |
| Client platforms | 57% | 0% | 100% | 57% | 4% | 0% | 4% |
| Search engine visibility | 54% | 14% | 79% | 54% | 0% | 0% | 4% |
| Preferred cloud | 43% | 40% | 64% | 0% | 10% | 2% | 43% |
| Monthly infrastructure budget | 36% | 34% | 64% | 0% | 9% | 1% | 29% |
| Availability target | 36% | 52% | 50% | 0% | 10% | 7% | 33% |
| Engineering team size | 32% | 8% | 64% | 3% | 16% | 0% | 18% |
| Work that runs in the background | 31% | 0% | 57% | 0% | 12% | 0% | 31% |
| Application type | 29% | 42% | 86% | 7% | 9% | 2% | 16% |
| Vendor lock-in tolerance | 25% | 0% | 43% | 4% | 14% | 7% | 14% |
| Daily active users (or active devices) | 22% | 63% | 36% | 0% | 6% | 7% | 16% |
| Existing systems you must keep | 21% | 55% | 71% | 0% | 10% | 13% | 5% |
| Users connected at the same moment, at peak (optional) | 21% | 21% | 36% | 0% | 7% | 7% | 11% |
| Realtime needs | 21% | 11% | 29% | 0% | 14% | 4% | 14% |
| Peak requests per second (optional) | 18% | 47% | 21% | 0% | 2% | 9% | 11% |
| Data volume at launch | 17% | 35% | 36% | 0% | 8% | 10% | 8% |
| Compliance & data residency | 17% | 24% | 50% | 0% | 6% | 0% | 17% |
| Data growth per month | 16% | 22% | 21% | 0% | 6% | 6% | 10% |
| How fast must the app answer? (slowest 1 in 20 requests, ms) | 12% | 19% | 29% | 4% | 6% | 0% | 4% |
| Architecture preference | 12% | 38% | 36% | 0% | 5% | 0% | 10% |
| Special workloads | 11% | 53% | 36% | 0% | 4% | 0% | 11% |
| What do users do? | 11% | 0% | 21% | 0% | 11% | 8% | 8% |
| Your top 3 priorities (first = most important) | 10% | 0% | 36% | 2% | 3% | 0% | 6% |
| Do several customer organisations share the app? | 10% | 0% | 29% | 2% | 2% | 5% | 0% |
| Offline support required | 7% | 57% | 7% | 7% | 0% | 7% | 0% |
| Do people mostly look at data, or mostly add and change it? | 7% | 25% | 14% | 0% | 4% | 7% | 4% |
| Time to MVP | 6% | 13% | 14% | 0% | 0% | 0% | 6% |
| Where are your users? | 2% | 32% | 7% | 0% | 0% | 0% | 2% |
| Customers sign in with their company account (SSO) | 0% | 11% | 0% | 0% | 0% | 0% | 0% |
| If two people change the same thing at the same moment, must everyone see one agreed result at once? | 0% | 7% | 0% | 0% | 0% | 0% | 0% |
| Traffic pattern | 0% | 7% | 0% | 0% | 0% | 0% | 0% |
| How much of the traffic can be cached? | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
