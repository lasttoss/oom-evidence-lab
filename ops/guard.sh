#!/usr/bin/env bash
# guard.sh — arm the JVM BEFORE anything goes wrong. Two jobs:
#   1. print the flag set for this environment (copy-paste ready)
#   2. CHECK the flag set you already have: dump path, free space, NMT, exit behaviour
# Nothing here starts, stops or restarts a process. Exit 1 = the guard is not armed.
#
# Usage: ops/guard.sh [auto|vm|docker|k8s|tomcat] [dump_dir]
set -u
cd "$(dirname "$0")/.."   # repo root, so out/ paths are stable
MODE="${1:-auto}"
DUMP_DIR="${2:-/var/log/java-dumps}"

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

FLAGS="-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=$DUMP_DIR -XX:+ExitOnOutOfMemoryError -XX:NativeMemoryTracking=summary -Xlog:gc*:file=$DUMP_DIR/gc.log:time,uptime,level,tags:filecount=5,filesize=20m"

echo "env=$MODE  dump_dir=$DUMP_DIR"
echo
echo "# The flag set (same for every environment — the JVM does not care where it runs)"
echo "JAVA_OPTS=\"\${JAVA_OPTS:-} $FLAGS\""
echo
case "$MODE" in
  k8s)   echo "# k8s: mount a real volume at $DUMP_DIR and raise the PVC — a dump can be as large as the live set"
         echo "#   volumeMounts: [{name: dumps, mountPath: $DUMP_DIR}]" ;;
  docker) echo "# docker: bind-mount a host dir at $DUMP_DIR (-v /data/java-dumps:$DUMP_DIR)" ;;
  tomcat) echo "# tomcat: put JAVA_OPTS in \$CATALINA_BASE/bin/setenv.sh, not in catalina.sh" ;;
  vm)    echo "# vm: put JAVA_OPTS in the systemd unit (Environment=) or /etc/default/<svc>" ;;
esac
echo

FAIL=0
check() { if eval "$2" >/dev/null 2>&1; then echo "OK    $1"; else echo "FAIL  $1  → $3"; FAIL=1; fi; }

check "dump directory exists and is writable" "mkdir -p '$DUMP_DIR' && [ -w '$DUMP_DIR' ]" "create it and give the JVM user write access"
FS_TYPE=$(stat -f -c %T "$DUMP_DIR" 2>/dev/null || echo unknown)
if [ "$FS_TYPE" = "tmpfs" ]; then
  echo "FAIL  dump directory is on tmpfs ($DUMP_DIR)"
  echo "      → a tmpfs dump dies with the pod. Mount a real volume."
  FAIL=1
else
  echo "OK    dump directory is on a persistent filesystem ($FS_TYPE)"
fi
FREE_MB=$(df -Pm "$DUMP_DIR" 2>/dev/null | awk 'NR==2{print $4}')
[ -n "${FREE_MB:-}" ] && [ "$FREE_MB" -gt 0 ] && echo "INFO  free space: ${FREE_MB} MB (a heap dump can be as large as the live set)" || true
echo
echo "check_oom_events:"
if [ -r /sys/fs/cgroup/memory.events ]; then
  awk '/^oom_kill/{printf "  cgroup oom_kill=%s (raise over time = the kernel is killing this cgroup)\n", $2}' /sys/fs/cgroup/memory.events
else
  echo "  cgroup v1: /sys/fs/cgroup/memory/memory.oom_control ; or docker inspect .State.OOMKilled"
fi
echo
[ "$FAIL" -eq 0 ] && echo "RESULT guard=armed" || echo "RESULT guard=NOT_ARMED (see FAIL lines)"
exit "$FAIL"
