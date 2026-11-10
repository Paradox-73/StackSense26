# Question influence

Method: 14 preset projects and 40 seeded random projects (seed 2026). For each project and each question, the engine was re-run with every other value of that one question, all other answers held fixed (8,159 engine runs in 171.5 s). A run counts as changing the stack when at least one of the four picks differs from the base run.

Caveats: team skills and platforms are varied as whole sets, which inflates their rate compared with a single yes/no answer. Budget is varied from $0 to $10,000. Rates depend on the base projects, so the sample is part of the result.

| Question | Changed a pick | Changed only cost or warnings | Projects where it changed a pick | Frontend | Backend | Database | Hosting |
|---|---|---|---|---|---|---|---|
| Existing team skills | 90% | 0% | 100% | 42% | 82% | 10% | 19% |
| What kinds of data do you store? (pick the main kind first) | 65% | 10% | 100% | 1% | 8% | 65% | 3% |
| Air-gapped (no internet connection) | 63% | 10% | 83% | 3% | 8% | 8% | 63% |
| Deployment model | 51% | 7% | 76% | 6% | 8% | 6% | 46% |
| Client platforms | 49% | 18% | 100% | 49% | 3% | 1% | 1% |
| Search engine visibility | 41% | 16% | 69% | 41% | 0% | 0% | 1% |
| Preferred cloud | 41% | 30% | 59% | 2% | 7% | 6% | 41% |
| Availability target | 36% | 50% | 61% | 5% | 2% | 5% | 33% |
| Engineering team size | 36% | 16% | 74% | 7% | 27% | 2% | 7% |
| We run our own VMs in the cloud | 32% | 0% | 46% | 0% | 5% | 3% | 32% |
| Existing systems you must keep | 30% | 49% | 81% | 1% | 4% | 27% | 1% |
| Vendor lock-in tolerance | 30% | 2% | 46% | 10% | 7% | 12% | 6% |
| Application type | 28% | 42% | 80% | 10% | 13% | 3% | 6% |
| Realtime needs | 27% | 4% | 41% | 4% | 15% | 7% | 8% |
| Daily active users (or active devices) | 21% | 56% | 48% | 2% | 3% | 4% | 15% |
| How fast must the app answer? (slowest 1 in 20 requests, ms) | 19% | 15% | 39% | 8% | 6% | 1% | 6% |
| Monthly infrastructure budget | 19% | 43% | 41% | 1% | 3% | 3% | 13% |
| Your top 3 priorities (first = most important) | 19% | 0% | 54% | 5% | 9% | 3% | 5% |
| Work that runs in the background | 17% | 2% | 30% | 0% | 4% | 0% | 17% |
| Peak requests per second (optional) | 17% | 47% | 28% | 1% | 2% | 4% | 13% |
| Users connected at the same moment, at peak (optional) | 15% | 35% | 31% | 3% | 4% | 2% | 7% |
| Team experience | 14% | 7% | 28% | 3% | 10% | 1% | 3% |
| Offline support required | 12% | 36% | 13% | 11% | 2% | 4% | 0% |
| Compliance & data residency | 11% | 24% | 30% | 0% | 2% | 3% | 10% |
| Do several customer organisations share the app? | 11% | 0% | 20% | 1% | 2% | 8% | 2% |
| Time to MVP | 11% | 8% | 22% | 3% | 7% | 1% | 2% |
| Data volume at launch | 10% | 36% | 20% | 0% | 5% | 8% | 2% |
| Do people mostly look at data, or mostly add and change it? | 10% | 20% | 17% | 1% | 3% | 6% | 4% |
| What do users do? | 9% | 1% | 19% | 0% | 8% | 5% | 3% |
| Data growth per month | 8% | 29% | 13% | 1% | 4% | 4% | 2% |
| Architecture preference | 7% | 38% | 17% | 1% | 4% | 1% | 4% |
| Must use this cloud (hard constraint) | 6% | 0% | 7% | 0% | 0% | 0% | 6% |
| Someone can operate infrastructure | 5% | 39% | 7% | 1% | 3% | 0% | 3% |
| If two people change the same thing at the same moment, must everyone see one agreed result at once? | 5% | 7% | 6% | 2% | 0% | 3% | 0% |
| Special workloads | 5% | 47% | 17% | 0% | 2% | 0% | 4% |
| How much of the traffic can be cached? | 2% | 7% | 4% | 0% | 0% | 1% | 2% |
| Traffic pattern | 2% | 6% | 2% | 0% | 2% | 2% | 0% |
| Customers sign in with their company account (SSO) | 1% | 10% | 2% | 0% | 1% | 0% | 0% |
| Machine-learning features | 1% | 21% | 4% | 0% | 0% | 0% | 1% |
| Where are your users? | 1% | 24% | 4% | 0% | 0% | 0% | 1% |

## Presets only

| Question | Changed a pick | Changed only cost or warnings | Projects where it changed a pick | Frontend | Backend | Database | Hosting |
|---|---|---|---|---|---|---|---|
| Existing team skills | 90% | 0% | 100% | 38% | 76% | 12% | 55% |
| What kinds of data do you store? (pick the main kind first) | 66% | 2% | 100% | 0% | 20% | 65% | 9% |
| Deployment model | 61% | 0% | 100% | 7% | 14% | 7% | 54% |
| Client platforms | 57% | 18% | 100% | 57% | 4% | 0% | 4% |
| Search engine visibility | 54% | 14% | 79% | 54% | 0% | 0% | 4% |
| Preferred cloud | 48% | 39% | 79% | 0% | 11% | 5% | 46% |
| Air-gapped (no internet connection) | 46% | 0% | 93% | 0% | 14% | 7% | 46% |
| We run our own VMs in the cloud | 46% | 0% | 93% | 0% | 14% | 7% | 46% |
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
| Compliance & data residency | 18% | 21% | 50% | 1% | 5% | 0% | 18% |
| Peak requests per second (optional) | 18% | 47% | 21% | 0% | 2% | 9% | 11% |
| Data volume at launch | 17% | 35% | 36% | 0% | 8% | 10% | 8% |
| Data growth per month | 16% | 22% | 21% | 0% | 6% | 6% | 10% |
| How fast must the app answer? (slowest 1 in 20 requests, ms) | 12% | 19% | 29% | 4% | 6% | 0% | 4% |
| Architecture preference | 12% | 38% | 36% | 0% | 5% | 0% | 10% |
| Special workloads | 11% | 53% | 36% | 0% | 4% | 0% | 11% |
| What do users do? | 11% | 0% | 21% | 0% | 11% | 8% | 8% |
| Your top 3 priorities (first = most important) | 10% | 0% | 43% | 2% | 3% | 0% | 7% |
| Do several customer organisations share the app? | 10% | 0% | 29% | 2% | 2% | 5% | 0% |
| Offline support required | 7% | 57% | 7% | 7% | 0% | 7% | 0% |
| Do people mostly look at data, or mostly add and change it? | 7% | 25% | 14% | 0% | 4% | 7% | 4% |
| Someone can operate infrastructure | 7% | 4% | 14% | 4% | 4% | 0% | 0% |
| Time to MVP | 6% | 13% | 14% | 0% | 0% | 0% | 6% |
| Machine-learning features | 4% | 46% | 14% | 0% | 0% | 0% | 4% |
| Team experience | 4% | 4% | 7% | 0% | 0% | 0% | 4% |
| Where are your users? | 2% | 32% | 7% | 0% | 0% | 0% | 2% |
| Customers sign in with their company account (SSO) | 0% | 11% | 0% | 0% | 0% | 0% | 0% |
| If two people change the same thing at the same moment, must everyone see one agreed result at once? | 0% | 7% | 0% | 0% | 0% | 0% | 0% |
| Traffic pattern | 0% | 7% | 0% | 0% | 0% | 0% | 0% |
| How much of the traffic can be cached? | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| Must use this cloud (hard constraint) | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
