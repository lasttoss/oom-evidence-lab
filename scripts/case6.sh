#!/usr/bin/env bash
# Case 6: cannot create a native thread — the heap stays free, thread stacks exhaust the limit.
# The limit here is pids.max (docker --pids-limit), which is the realistic production cause.
set -u
LAB_DIR="$(cd "$(dirname "$0")/.." && pwd)"; cd "$LAB_DIR"
OUT=out/case6; mkdir -p "$OUT"
command -v docker >/dev/null || { echo "FAIL: docker not found"; exit 1; }

rm -rf "$OUT/classes"; mkdir -p "$OUT/classes"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/lab" -w /lab eclipse-temurin:21-jdk \
  javac -d out/case6/classes cases/NativeThreadOOM.java || exit 1

set +e
docker run --rm --pids-limit 200 --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/lab" -w /lab \
  eclipse-temurin:21-jdk java -Xmx512m -Xss1m -cp out/case6/classes NativeThreadOOM \
  > "$OUT/stdout.txt" 2> "$OUT/stderr.txt"
rc=$?
set -e
echo "$rc" > "$OUT/exit_code.txt"
grep -m1 'OutOfMemoryError' "$OUT/stderr.txt" > "$OUT/oom_message.txt" 2>/dev/null || true
echo "outcome=exit_code=$rc" > "$OUT/result.txt"
cat "$OUT/result.txt"; cat "$OUT/oom_message.txt"
