# `ops/` — the part you actually install

This folder has **no dependency on `lab/`**. Copy it into a service repo (or onto a server) and it works.
Everything here runs against a *live* Java process; nothing here starts, restarts or deletes anything.

```
classify.py    rules -> kind, 13-field alert, unknown keeps its cause + fingerprint
signature.py   normalise + fingerprint (shared by classify, store and the gap queue)
store.py       bundle · index.jsonl · docs/INCIDENTS.md; prune drops dumps, never text
collect.sh     read-only, time-boxed field collection for one pid
guard.sh       print + CHECK the JVM flags; exit 1 when the evidence is not armed
watch.sh       interval histo/heap_info/cgroup snapshots while the process is alive
plan.sh        detect the environment (vm|docker|k8s|tomcat) and print its commands
intake.sh      field set for an unrecognised OOM, before anyone decides anything
```

**Runtime requirements:** `bash`, `python3` (3.9+), and a JDK on the box (`jcmd` lives in the JDK, not the JRE).
If a server has no `python3`, `collect.sh` still captures fields; `classify.py` / `store.py` need it.

## Install guides — pick the one that matches where the JVM runs

| Where the JVM runs | Guide | The thing that breaks |
|---|---|---|
| systemd service on a VM | [`install/vm.md`](install/vm.md) | dump lands in a directory the JVM user cannot write |
| Tomcat (WAR on a host) | [`install/tomcat.md`](install/tomcat.md) | flags put in `catalina.sh` and lost on upgrade |
| Kubernetes | [`install/k8s.md`](install/k8s.md) | dump written to `emptyDir` / `/tmp`, gone on pod recreation |
| Docker (single container) | [`install/docker.md`](install/docker.md) | no bind mount, so the dump dies with the container |

The flags are identical in all four. Only **where the dump lands, who reports the kill, what survives,
and how you fetch it** change.

## Copy it in

```bash
# from this repo
cp -r ops/ /srv/<service>/ops/          # or vendor it as a git subtree
cd /srv/<service> && bash ops/guard.sh vm /var/log/java-dumps
```

`guard.sh` is the gate: it prints the exact `JAVA_OPTS` line and fails if the dump directory is missing,
unwritable, or on **tmpfs** (a tmpfs dump dies with the machine, the pod, or the container).

## The order of work after installation

```
1  arm       guard.sh in the deploy pipeline / CI — red when a flag is removed
2  watch     watch.sh (cron, systemd timer or CronJob) — the only attribution for a kernel kill
3  alert     point your alert rule at the bundle path: field 10.stored_at
4  review    make gaps once a month: new fingerprints, and nothing else
```
