# OOM Evidence Lab

Reproduces **four kinds of OOM** and turns each death into **one evidence bundle** —
instead of a ticket that only says "the pod restarted".

## Result in three lines

- All four kinds are reproducible, one command each, **about 25 seconds** in total on a 16-core host.
- Every death produces a bundle plus a **9-field alert** (exit code, verbatim evidence, fastest-growing class, ordered checks).
- Classification is **rules first, model second** — no model is called anywhere in this repo.

Measured numbers from the last run: see [`docs/RESULTS.md`](docs/RESULTS.md).

## Reproduce in one command

```bash
make demo               # ~25s, needs docker; no Java on the host
make report             # re-print alerts + rebuild docs/RESULTS.md
make incidents          # print the incident index
make prune DAYS=30      # delete old heap dumps, KEEP all text
make KEEP_DUMP=1 case1  # keep the heap dump (~240 MB) to open in MAT
```

Requires `docker` (image `eclipse-temurin:21-jdk`) and `python3`.

## The problem

OOM happens **once every few months**. You cannot wait for it and you cannot reproduce it in test.
When it does happen, the pod restarts 40 seconds later, service comes back, and **the evidence is gone**.
So every occurrence starts from zero.

With a 4 GB heap and one OOM every 3 months, the leak rate is roughly **45 MB/day** — clearly
visible on a weekly chart. If nobody sees it, that is a monitoring failure, not a slow leak.

## Four kinds of OOM — and why the distinction matters

| Case | Kind | Decisive signal | What "fixing it" means |
|---|---|---|---|
| 1 | `heap` | `OutOfMemoryError: Java heap space` + heap dump | find **what retains** (retained size, shortest path) |
| 2 | `direct_buffer` | `... direct buffer memory (allocated: N, limit: N)` | compare `MaxDirectMemorySize` with real traffic |
| 3 | `metaspace` | `OutOfMemoryError: Metaspace` | find the **ClassLoader that never closes** |
| 4 | `container_kill` | exit **137** + `OOMKilled=true`, JVM prints **nothing** | compare `memory.max` with `Xmx + off-heap` |

Case 4 is the one that gets misdiagnosed most often: **no Java line runs** after the kernel sends
SIGKILL, so every `try/catch`, `finally` and shutdown hook is void. It cannot be caught in code —
it must be caught from cgroup or kubelet level.

## Scope: Java only

This is **one system with one job**: detect an out-of-memory event on a Java process, collect the
evidence automatically, and classify it into one of ten kinds. Nothing else.

**Covered (10 kinds).** The nine `OutOfMemoryError` messages HotSpot can throw —
`heap` · `gc_overhead` · `array_too_large` · `metaspace` · `compressed_class` · `direct_buffer` ·
`native_thread` · `native_alloc` · `swap` — plus `container_kill`, where the kernel kills the process
and the JVM prints nothing. Anything unrecognised is stored as `unknown`: never guessed.

`python3 scripts/test_classify.py` checks the whole table against synthetic signatures (14 cases).

**Explicitly out of scope** — not "later", simply not this system:

- other runtimes (Go, Node, .NET, Python) — different signals, different tools;
- serverless — no dump is possible, the contract would have to change;
- fixing the leak or tuning the JVM — this system produces evidence and a hypothesis, a human decides;
- an LLM in the classification path — the rules are complete enough that a model would only add noise.

Java is where the rules can be exhaustive, which is why the scope is drawn here on purpose.

## Step 1 is environment-dependent, step 2 is not

The same six questions are asked everywhere; only the tool changes:

```
Q1 CEILING    what is the real upper bound        k8s limit / docker Memory / Xmx / ulimit
Q2 USAGE      heap vs off-heap vs native          jcmd GC.heap_info + VM.native_memory + RSS
Q3 TREND      leak or spike                       class_histogram over time, jstat
Q4 CLASSES    who generates them                  VM.metaspace, VM.classloader_stats
Q5 THREADS    can a thread still be created       Thread.print, pids.max, ulimit -u
Q6 SIGNAL     kernel killed it, or JVM threw      OOMKilled, cgroup memory.events, hs_err_pid
```

`scripts/plan.sh` detects the environment (vm · docker · k8s · tomcat) and prints the exact
commands for that environment — it never guesses at a pod limit with a host command:

```bash
make plan                  # auto-detect
make plan ENV=k8s PID=17
```

**Q6 comes first in practice.** If the kernel killed the process, every step-2 tool is pointless:
there is no process left to ask. Order is: ceiling → signal → usage → trend → classes.

## How it works

**Rules first, model second.** Known signatures are matched by rules (cheap, precise, no invention).
A model is only used for unknown signatures, and always labelled *unconfirmed*.

**An alert is an evidence bundle, not a conclusion.** Nine fields:

```
01 kind (heap / direct_buffer / metaspace / container_kill / unknown)
02 note: UNCONFIRMED — hypothesis, not verdict
03 one-line explanation
04 exit_code
05 progress marker (how far the process got)
06 heap dump: present or not, how many bytes
07 evidence: verbatim line from stderr
08 fastest-growing class between two histogram snapshots
09 four ordered checks, specific to the kind
10 bundle path — so the alert leads straight back to the artifacts
```

**Four rules for the collector** ([`scripts/collect.sh`](scripts/collect.sh)):

1. **Read-only** — no restart, no deletes, nothing written outside `out/`.
2. **Time-boxed** — every `jcmd` runs under `timeout`; the collector may never hang.
3. **Never invent** — a field that cannot be read is reported as `unavailable` plus the reason.
4. **Always keep an `unknown` label** — a system with no "I don't know" label will guess.

## Where the evidence is stored — three tiers

Every death produces **one bundle**, not a pile of loose files.

```
out/incidents/<UTC>-<case>/     tier 1: BUNDLE — raw artifacts of that one event
out/incidents/index.jsonl       tier 2: INDEX — one line per incident, small, greppable
docs/INCIDENTS.md               tier 3: TABLE — generated from the index, for humans
```

One index line looks like this:

```json
{"ts":"2026-11-09T12:37:54+00:00","case":"case1","kind":"heap","exit_code":"1",
 "oom_killed":null,"dump_bytes":0,"dump_recorded_bytes":238534436,
 "bundle":"out/incidents/20261109T123754102841Z-case1","host":"...","lab_commit":"13587e9",
 "files":["stderr.txt","exit_code.txt","histo-1.txt","gc.log","dump.txt"]}
```

**Retention rules:**

| Artifact | Kept | Where |
|---|---|---|
| text (stderr, histo, gc.log, exit_code) | **forever** — tens of KB per incident | safe in git |
| heap dump / JFR | time-limited (`make prune`) | volume or object storage, **not** git |
| index.jsonl | forever | safe in git (it is the map) |

**Three requirements before this runs in production:**

1. **Dump to a real volume, never `/tmp`** — inside a container `/tmp` is usually tmpfs; a pod restart loses it.
2. **The index must outlive the pod** — write it outside the pod (object storage or a small db).
3. **One named owner** — without an owner, six months later the bundle sits there and nobody opens it.

Querying:

```bash
grep '"kind": "heap"' out/incidents/index.jsonl   # every heap OOM
python3 scripts/store.py list                     # everything
ls out/incidents/*-container_kill/                # bundles by kind
```

## Evidence

- [`docs/RESULTS.md`](docs/RESULTS.md) — result table, raw evidence, and the alert for the last run.
- [`docs/INCIDENTS.md`](docs/INCIDENTS.md) — log of every stored death, generated from the index.
- `out/case*/histo-*.txt` — `jcmd GC.class_histogram` over time (diff them to find steady growth).
- `out/case*/gc.log` — GC log for case 1 (`-Xlog:gc*`).
- `make KEEP_DUMP=1 case1` — keep the ~240 MB heap dump for MAT.

## What this repo does NOT prove

- **It has never run under real traffic.** This is a controlled reproduction, not production data.
- **There is no labelled dataset**, so the accuracy of the classification step is not measured.
- **It does not handle SIGKILL in time to write a dump** — when the kernel kills a container there is
  no dump, which is exactly why the signal has to come from cgroup rather than from the JVM.
