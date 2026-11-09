# Install on Kubernetes

The flags do not change. Four things do. Full reasoning: [`docs/K8S.md`](../../docs/K8S.md);
manifests: [`deploy/k8s/`](../../deploy/k8s/).

## 1. A volume that outlives the pod

```yaml
volumes:
  - name: dumps
    persistentVolumeClaim: {claimName: java-dumps}
containers:
  - name: api
    volumeMounts:
      - {name: dumps, mountPath: /dumps}
    env:
      - name: JAVA_OPTS
        value: >-
          -Xmx1g -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/dumps
          -XX:+ExitOnOutOfMemoryError -XX:NativeMemoryTracking=summary
          -Xlog:gc*:file=/dumps/gc.log:time,uptime,level,tags:filecount=5,filesize=20m
    resources:
      limits:
        memory: 1536Mi        # Xmx + off-heap + stacks + overhead. NOT Xmx.
```

`emptyDir` and `/tmp` are the same mistake: both die with the pod.

## 2. Who reports the kill

```bash
kubectl -n <ns> get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.reason}'
kubectl -n <ns> get pod <pod> -o jsonpath='{.status.containerStatuses[*].restartCount}'
kubectl -n <ns> describe pod <pod> | grep -iE 'OOMKilled|Evicted|exit code'
```

Three different deaths, only one is an OOM: `OOMKilled` (container limit) · `Evicted` (node pressure) ·
probe failure. **`lastState`, not `state`** — the container is usually running again by the time you look.

## 3. Snapshots as a CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata: {name: oom-watch, namespace: prod}
spec:
  schedule: "*/5 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: watch
              image: eclipse-temurin:21-jdk
              command: ["bash", "-c"]
              args:
                - pid=$(jcmd -l | awk '/api/{print $1; exit}'); [ -n "$pid" ] && bash /opt/oom-lab/ops/watch.sh "$pid" 240
              volumeMounts: [{name: dumps, mountPath: /dumps}]
          volumes:
            - name: dumps
              persistentVolumeClaim: {claimName: java-dumps}
```

Cross-check before deploying: `make plan ENV=k8s PID=<pid>` prints the kubectl commands for this
environment instead of host commands.

## 4. Fetch and keep

```bash
kubectl -n <ns> cp <pod>:/dumps/java_pid1.hprof ./
# or let a sidecar ship it: deploy/k8s/deployment.yaml has an uploader that copies to S3 then frees the PVC
```

**The trap:** the Deployment recreates the pod, and the container filesystem goes with it. If nobody
copies the dump out and the index lives inside the pod, the incident leaves **no trace at all** — which is
exactly the failure this lab exists to prevent.
