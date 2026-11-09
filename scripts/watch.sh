#!/usr/bin/env bash
# watch.sh — capture evidence on a schedule while the process is still alive.
# The point: a single snapshot answers nothing. Two snapshots far apart show growth.
#
# Usage: scripts/watch.sh <pid> [interval_seconds]
set -u
PID="${1:?usage: watch.sh <pid> [interval_seconds]}"
INTERVAL="${2:-60}"
OUT="out/watch/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"

echo "pid=$PID interval=${INTERVAL}s out=$OUT"
: > "$OUT/events.txt"

shot=0
while [ -d "/proc/$PID" ]; do
  shot=$((shot + 1))
  ts=$(date -u +%H:%M:%SZ)
  timeout 20 jcmd "$PID" GC.class_histogram > "$OUT/histo-$shot.txt" 2>/dev/null || true
  timeout 15 jcmd "$PID" GC.heap_info       > "$OUT/heapinfo-$shot.txt" 2>/dev/null || true
  rss=$(awk '/VmRSS/{print $2}' "/proc/$PID/status" 2>/dev/null || echo "?")
  thr=$(awk '/Threads/{print $2}' "/proc/$PID/status" 2>/dev/null || echo "?")
  oom=$(awk '/^oom_kill/{print $2}' /sys/fs/cgroup/memory.events 2>/dev/null || echo "?")
  cur=$(cat /sys/fs/cgroup/memory.current 2>/dev/null || echo "?")
  echo "$ts shot=$shot rss_kb=$rss threads=$thr cgroup_current=$cur cgroup_oom_kill=$oom" >> "$OUT/events.txt"
  sleep "$INTERVAL"
done

echo "process $PID is gone after $shot snapshot(s)"
echo "evidence: $OUT   (diff histo-1.txt vs histo-$shot.txt to see what grew)"
tail -2 "$OUT/events.txt"
