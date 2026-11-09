#!/usr/bin/env bash
# Case 3: Metaspace OOM (ClassLoader leak)
source "$(dirname "$0")/lib.sh"
require_tools
OUT=out/case3; mkdir -p "$OUT"; rm -rf "$OUT/classes"; mkdir -p "$OUT/classes"
"$JAVAC_BIN" -d "$OUT/classes" lab/cases/MetaspaceOOM.java lab/cases/ClassGenerator.java || exit 1
run_case case3 -Xmx256m -XX:MaxMetaspaceSize=64m -- MetaspaceOOM
grep -m1 -o 'OutOfMemoryError[^"]*' "$OUT/stderr.txt" > "$OUT/oom_message.txt" 2>/dev/null || true
cat "$OUT/result.txt"
