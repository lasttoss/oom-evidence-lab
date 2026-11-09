#!/usr/bin/env bash
# Case 5: one allocation larger than the VM limit. The heap is almost empty — this is NOT a leak.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_tools

OUT="out/case5"; mkdir -p "$OUT/classes"
"$JAVAC_BIN" -d "$OUT/classes" cases/ArrayTooLarge.java || { echo "FAIL: javac"; exit 1; }
run_case case5 -Xmx256m -- ArrayTooLarge
grep -m1 'OutOfMemoryError' "$OUT/stderr.txt" > "$OUT/oom_message.txt" 2>/dev/null || true
echo "done case5"
