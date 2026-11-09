# The same flags in three places — VM, Docker, Kubernetes

The JVM flags never change. What changes is **where the dump lands, who reports the kill, what
survives the death, and how you fetch it afterwards.** Getting this wrong is why a Kubernetes OOM
looks like "no evidence at all" while the identical Java process on a VM leaves a 240 MB dump.

| Question | VM / systemd | Docker | Kubernetes |
|---|---|---|---|
| Where do flags go | `Environment=JAVA_OPTS=...` in the unit | `-e JAVA_OPTS=...` | `env: JAVA_OPTS` in the container spec |
| Where the dump lands | `/var/log/java-dumps` on the host | bind mount `-v /data/dumps:/dumps` | **PVC** mounted at `/dumps` (`emptyDir` = lost) |
| Who reports the kill | `dmesg`, `journalctl`, `hs_err_pid*.log` | `docker inspect .State.OOMKilled` | `containerStatuses[].lastState.terminated.reason` |
| What survives | everything | dump survives if the host dir survives | only the PVC survives; the container filesystem does not |
| How to fetch | `cp` | `docker cp` | `kubectl cp`, or a sidecar that ships to object storage |
| Danger | none specific | restarting with `--rm` drops the container filesystem | **the Deployment recreates the pod and you lose the container filesystem** |

## Three different deaths in Kubernetes — only one is this lab's case 4

```
OOMKilled    .lastState.terminated.reason == "OOMKilled"   the container hit memory.limit
Evicted      .status.reason == "Evicted"                   the NODE ran out of memory or disk
probe fail   restartCount rising, reason "Error"           liveness/readiness killed it, memory is innocent
```

Reporting "OOM" for an evicted pod sends everyone hunting for a leak that does not exist.

## The four practical traps

1. **`emptyDir` and `/tmp` are the same mistake.** Both die with the pod. A heap dump on `emptyDir`
   survives exactly until the next `kubectl delete pod`.
2. **`lastState` is not `state`.** After a restart the container is running again and `state` shows
   a healthy process. The evidence of the kill is in `lastState.terminated`, and it disappears after
   a few restarts if nobody queries it. This is why the index must be written outside the pod.
3. **The limit must be `Xmx + off-heap + stacks + overhead`, never `Xmx`.** With `-Xmx1g` and
   `memory: 1Gi`, the kernel kills the container long before the heap is full — the JVM never throws,
   so no dump is written and the classification must come from `memory.events`, not from Java.
4. **`+ExitOnOutOfMemoryError` turns a silent OOM into a fast, visible restart.** Without it the JVM
   may limp along with a broken heap, the liveness probe fails, and the death is mislabelled as a probe failure.

## Files

- [`deploy/k8s/dumps-pvc.yaml`](../deploy/k8s/dumps-pvc.yaml) — the volume that outlives the pod.
- [`deploy/k8s/deployment.yaml`](../deploy/k8s/deployment.yaml) — flags, limits, PVC, and an optional
  sidecar that ships dumps to S3 so they survive even a PVC reset.
- [`scripts/plan.sh`](../scripts/plan.sh) — `make plan ENV=k8s PID=17` prints the exact
  `kubectl` commands for this environment instead of host commands.

## What still cannot be done

A `SIGKILL` from the kernel cannot be intercepted: no shutdown hook, no dump, no `finally`. On
Kubernetes the only reliable signals are `lastState.terminated.reason`, the restart count, and
`memory.events` read from inside the container *before* it is recreated. Any design that expects
Java code to report its own kernel-kill is wrong by construction.
