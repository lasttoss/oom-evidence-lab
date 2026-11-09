# From lab to real numbers — a 30-day pilot

The lab cannot produce the numbers that matter most (time-to-evidence on a real incident, alert
precision on real traffic). It produces the **mechanism** and the **reasoning order**. This page is the
honest bridge: what the lab already proves, what only production can prove, and how to get those
numbers in 30 days without asking for a budget.

## Two kinds of numbers — do not mix them

| Number | Valid beyond this lab? | How to say it |
|---|---|---|
| Dump size ≈ live set (238 MB for a 4 GB heap case) | **yes** — it is how heap dumps work | "a dump can be as large as the live set" |
| Exit 137 + `OOMKilled=true` means no dump is possible | **yes** — kernel semantics | "a SIGKILL cannot be dumped" |
| Thread = ~1 MB stack off-heap at `-Xss1m` | **yes** — arithmetic | "threads × Xss is memory you must budget" |
| 179 threads before `pids.max=200` fails | **no** — depends on the limit | "it dies at the limit you set, not at a magic number" |
| `jcmd` snapshot latency, histogram cost | **no** — depends on heap size, host | never quote as a production figure |
| "23 seconds for 6 cases" | **no** — it is lab speed | "reproducible in under a minute" |

Rule: quote **mechanism** numbers freely; never quote **environment** numbers as if they were production.

## What the lab already proves (no traffic needed)

- the ten kinds exist and are distinguishable by rules;
- which kinds can produce a dump and which cannot, by construction;
- the order of checks is different per kind (a thread OOM is not a heap OOM);
- the storage contract works: bundle + index + table, text kept, dumps pruned;
- an `unknown` can state its own cause (new signature vs config gap vs collection gap vs timing gap).

## What only production can prove

1. **Detection latency** — how long between the death and a bundle that a human can use.
2. **Alert precision** — of the alerts fired, how many were actionable. Unknown until real traffic.
3. **Coverage in practice** — what share of services are actually armed, measured, not assumed.
4. **Cost** — dump volume per month, PVC size, S3 lifecycle.

## The pilot: 30 days, one service, no new tooling

| Week | Action | Success criterion |
|---|---|---|
| 1 | arm the flags on **one** non-critical service (`make guard` in its CI as a check) | the guard check passes in CI, and is red if the flag is removed |
| 2 | schedule `watch.sh` (or a CronJob) at 15-minute intervals; ship bundles to object storage | at least one bundle exists and opens |
| 3 | wire the alert to carry the bundle path (`10.stored_at`) | an on-call engineer can go alert → bundle in one click |
| 4 | review: did anyone use a bundle? what was missing? | a written list of the top 3 missing facts |

**Metrics to report after 30 days** — all four are cheap and honest:

```
services_armed / services_total          coverage
median(time from death to bundle)        detection latency
bundles_used_by_a_human / bundles        usefulness, not volume
unknown triaged as NEW_SIGNATURE         real knowledge gaps vs config gaps
```

## What not to promise

- Not "fewer incidents". The lab does not prevent a single OOM.
- Not "faster MTTR" before the pilot has measured it once.
- Not "AI-driven diagnosis". The rules are exhaustive for the ten kinds; a model adds noise before it adds value.

The honest claim is narrow and defensible: **when a Java process dies of memory, the evidence is
already written down and classified — or it says precisely why it could not be.**
