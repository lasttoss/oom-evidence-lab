#!/usr/bin/env bash
# Collect 9 evidence fields for ONE JVM process. READ-ONLY: no restart, no delete.
# Every field is time-boxed; anything unavailable is reported as unavailable + why.
# Usage: scripts/collect.sh <pid>
set -u
PID="${1:-}"
[ -z "$PID" ] && { echo "usage: collect.sh <pid>"; exit 2; }
[ -d "/proc/$PID" ] || { echo "unavailable=process $PID does not exist"; exit 3; }

field() { printf '%s=%s\n' "$1" "$2"; }
get()   { timeout 15 "$@" 2>/dev/null; }

field "01.collected_at"          "$(date -Is)"
field "02.pid"                   "$PID"
field "03.uptime_sec"            "$(awk '{printf "%d", systime() - $22/100}' /proc/$PID/stat 2>/dev/null || echo unavailable)"
field "04.rss_kb"                "$(awk '/VmRSS/{print $2}' /proc/$PID/status 2>/dev/null || echo unavailable)"
field "05.threads"               "$(awk '/Threads/{print $2}' /proc/$PID/status 2>/dev/null || echo unavailable)"
field "06.exit_signal"           "still_alive"
field "07.cgroup_memory_current" "$(cat /sys/fs/cgroup/memory.current 2>/dev/null || awk '/total_rss/{print $2}' /sys/fs/cgroup/memory/memory.stat 2>/dev/null || echo unavailable)"
field "08.cgroup_memory_max"     "$(cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || echo unavailable)"
field "09.cgroup_oom_kill"       "$(awk '/^oom_kill/{print $2}' /sys/fs/cgroup/memory.events 2>/dev/null || echo unavailable)"

echo "--- jcmd GC.heap_info ---"
get jcmd "$PID" GC.heap_info || echo "unavailable=jcmd GC.heap_info"
echo "--- jcmd VM.native_memory summary ---"
get jcmd "$PID" VM.native_memory summary || echo "unavailable=NMT not enabled (-XX:NativeMemoryTracking=summary)"
echo "--- jcmd VM.metaspace ---"
get jcmd "$PID" VM.metaspace || echo "unavailable=jcmd VM.metaspace"
echo "--- jcmd VM.flags ---"
get jcmd "$PID" VM.flags || echo "unavailable=jcmd VM.flags"
echo "--- /proc/PID/maps: anonymous vs file-backed mappings ---"
if [ -r "/proc/$PID/maps" ]; then
  awk '{ if ($6 == "" || $6 == "[heap]" || $6 == "[stack]") anon++; else file++ }
       END { printf "anon_vma=%d\nfile_vma=%d\n", anon, file }' "/proc/$PID/maps"
else
  echo "unavailable=/proc/$PID/maps"
fi
