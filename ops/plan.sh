#!/usr/bin/env bash
# plan.sh — step 1 only: DETECT the environment, then emit the exact commands for THAT environment.
# Same six questions everywhere. Different tools per platform. Nothing is executed here.
#
# Usage: ops/plan.sh [auto|vm|docker|k8s] [pid]
set -u
cd "$(dirname "$0")/.."   # repo root, so out/ paths are stable
MODE="${1:-auto}"
PID="${2:-$(pgrep -n -f 'java|tomcat' 2>/dev/null || echo 1)}"

detect() {
  local env="vm"
  [ -n "${KUBERNETES_SERVICE_HOST:-}" ] && env="k8s"
  if [ -f /proc/1/cgroup ] && grep -qE 'docker|containerd|kubepods' /proc/1/cgroup 2>/dev/null; then
    [ "$env" != "k8s" ] && env="docker"
  fi
  [ -n "${CATALINA_BASE:-}" ] && env="tomcat"
  echo "$env"
}
[ "$MODE" = "auto" ] && MODE=$(detect)

CGROUP_V=2; [ -d /sys/fs/cgroup/memory ] && [ ! -f /sys/fs/cgroup/memory.max ] && CGROUP_V=1

echo "env=$MODE  pid=$PID  cgroup=v$CGROUP_V"
echo "Six questions. Run them in this order — the ceiling first, the leak last."
echo

echo "# Q1 CEILING — what is the real upper bound of this process?"
case "$MODE" in
  k8s)
    echo "kubectl -n <ns> get pod <pod> -o jsonpath='{.spec.containers[*].resources.limits.memory}'"
    echo "cat /sys/fs/cgroup/memory.max                       # v2, the value that actually kills you"
    echo "cat /sys/fs/cgroup/memory/memory.limit_in_bytes     # v1" ;;
  docker)
    echo "docker inspect <id> --format '{{.HostConfig.Memory}}'"
    [ "$CGROUP_V" -eq 2 ] && echo "cat /sys/fs/cgroup/memory.max" || echo "cat /sys/fs/cgroup/memory/memory.limit_in_bytes" ;;
  tomcat)
    echo "cat \$CATALINA_BASE/bin/setenv.sh | tr ' ' '\n' | grep -E 'Xmx|Xms|MaxDirect|MaxMetaspace'"
    echo "ps -o rss= -p $PID                              # compare with -Xmx + off-heap + overhead"
    echo "free -m" ;;
  vm)
    echo "ps -o rss=,vsz= -p $PID"
    echo "free -m && swapon --show"
    echo "cat /proc/$PID/limits | grep -E 'max memory|max processes'" ;;
esac
echo

echo "# Q2 USAGE NOW — heap vs off-heap vs native, kept separate"
echo "jcmd $PID GC.heap_info"
echo "jcmd $PID VM.native_memory summary                   # needs -XX:NativeMemoryTracking=summary"
echo "awk '/VmRSS|Threads/{print}' /proc/$PID/status"
echo

echo "# Q3 TREND — growth over time, the only field that separates a leak from a spike"
echo "jcmd $PID GC.class_histogram > histo-\$(date +%H%M%S).txt   # every 5-15 min, then diff"
echo "jstat -gcutil $PID 1000 10"
echo

echo "# Q4 WHERE THE CLASSES COME FROM — dynamic generation vs data growth"
echo "jcmd $PID VM.metaspace"
echo "jcmd $PID VM.classloader_stats"
echo

echo "# Q5 THREADS AND NATIVE — a thread that cannot be created is not a heap problem"
echo "jcmd $PID Thread.print | grep -c '^\"'"
case "$MODE" in
  k8s)    echo "cat /sys/fs/cgroup/pids.max /sys/fs/cgroup/pids.current" ;;
  docker) echo "docker inspect <id> --format '{{.HostConfig.PidsLimit}}'" ;;
  *)      echo "ulimit -u; cat /proc/sys/kernel/threads-max" ;;
esac
echo

echo "# Q6 THE DECISIVE SIGNAL — did the kernel kill it, or did the JVM throw?"
case "$MODE" in
  k8s)
    echo "kubectl -n <ns> get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState.terminated}'"
    echo "kubectl -n <ns> get pod <pod> -o jsonpath='{.status.containerStatuses[*].restartCount}'"
    echo "kubectl -n <ns> describe pod <pod> | grep -iE 'OOMKilled|exit code|Reason|Evicted'"
    echo "kubectl -n <ns> get events --field-selector involvedObject.name=<pod> --sort-by=.lastTimestamp"
    echo "awk '/^oom_kill/{print}' /sys/fs/cgroup/memory.events   # inside the container (kubectl exec)"
    echo "# three different deaths, three different reasons:"
    echo "#   OOMKilled   container limit was hit        -> this lab's case4"
    echo "#   Evicted     node ran out of memory/disk    -> not your heap; check node pressure"
    echo "#   probe fail  liveness/readiness restarted   -> not memory at all" ;;
  docker)
    echo "docker inspect <id> --format '{{.State.OOMKilled}} {{.State.ExitCode}}'"
    echo "dmesg -T | grep -i 'killed process' | tail -5" ;;
  tomcat|vm)
    echo "grep -E 'OutOfMemoryError|hs_err_pid' \$CATALINA_BASE/logs/catalina.out 2>/dev/null || journalctl -u <svc> -n 200"
    echo "dmesg -T | grep -iE 'out of memory|killed process' | tail -5"
    echo "ls -t hs_err_pid*.log 2>/dev/null | head -3" ;;
esac
echo

echo "# FETCH — the dump is on a volume; get it out before the pod is replaced"
case "$MODE" in
  k8s)    echo "kubectl -n <ns> cp <pod>:/dumps/$(ls -t /dumps/*.hprof 2>/dev/null | head -1 | xargs -r basename) ./  # or let the sidecar ship it to S3"
          echo "kubectl -n <ns> debug -it <pod> --image=eclipse-temurin:21-jdk --target=api -- bash  # inspect a running pod" ;;
  docker) echo "docker cp <id>:/dumps/. ./dumps/" ;;
  *)      echo "cp /var/log/java-dumps/*.hprof ./ (or read it where it already is)" ;;
esac
echo

echo "# DEEPER — only after Q1-Q6, in this order of cost"
echo "L2 jcmd      JFR.start duration=60s filename=/dumps/rec.jfr settings=profile"
echo "L3 profiler  async-profiler: asprof -d 60 -e alloc -o collapsed -f /dumps/alloc.txt $PID"
echo "L4 snapshot  jcmd $PID GC.heap_dump /dumps/live-\$(date +%H%M%S).hprof   # live objects only"
echo "L4 app-level Spring Boot Actuator: curl -s localhost:8080/actuator/heapdump -o /dumps/act.hprof"
echo "L4 app-level curl -s localhost:8080/actuator/metrics/jvm.memory.used?tag=area:heap"
