#!/usr/bin/env bash
# Case 1: heap OOM caused by objects retained in a static field
source "$(dirname "$0")/lib.sh"
require_tools
OUT=out/case1; mkdir -p "$OUT"; rm -rf "$OUT/classes"; mkdir -p "$OUT/classes"
"$JAVAC_BIN" -d "$OUT/classes" lab/cases/HeapLeak.java || exit 1
rm -f "$OUT/heap.hprof" "$OUT/gc.log"
run_case case1 \
  -Xmx256m -XX:+UseG1GC \
  -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath="$OUT/heap.hprof" \
  -Xlog:gc*:file="$OUT/gc.log":time,uptime,level,tags \
  -- HeapLeak
ls -l "$OUT/heap.hprof" 2>/dev/null | awk '{print "heap_dump_bytes=" $5}' > "$OUT/dump.txt"
# the dump is ~240MB: keep it only when KEEP_DUMP=1 (to open in MAT), otherwise drop it
if [ "${KEEP_DUMP:-0}" != "1" ]; then rm -f "$OUT/heap.hprof"; fi
grep -m1 -o 'OutOfMemoryError[^"]*' "$OUT/stderr.txt" > "$OUT/oom_message.txt" 2>/dev/null || true
cat "$OUT/result.txt"
