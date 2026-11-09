#!/usr/bin/env bash
# Case 2: direct buffer OOM (off-heap)
source "$(dirname "$0")/lib.sh"
require_tools
OUT=out/case2; mkdir -p "$OUT"; rm -rf "$OUT/classes"; mkdir -p "$OUT/classes"
"$JAVAC_BIN" -d "$OUT/classes" lab/cases/DirectBufferOOM.java || exit 1
run_case case2 -Xmx256m -XX:MaxDirectMemorySize=64m -- DirectBufferOOM
grep -m1 -o 'OutOfMemoryError[^"]*' "$OUT/stderr.txt" > "$OUT/oom_message.txt" 2>/dev/null || true
cat "$OUT/result.txt"
