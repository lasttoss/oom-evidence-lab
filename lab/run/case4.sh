#!/usr/bin/env bash
# Case 4: killed by the KERNEL via cgroup (no JVM error thrown)
set -u
LAB_DIR="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$LAB_DIR"
OUT=out/case4; mkdir -p "$OUT"
command -v docker >/dev/null || { echo "FAIL: docker not found"; exit 1; }
docker image inspect eclipse-temurin:21-jdk >/dev/null 2>&1 || {
  echo "FAIL: missing image eclipse-temurin:21-jdk"; exit 1; }

rm -rf "$OUT/classes"; mkdir -p "$OUT/classes"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/lab" -w /lab eclipse-temurin:21-jdk \
  javac -d out/case4/classes lab/cases/ContainerKill.java || exit 1

docker rm -f oomlab-kill >/dev/null 2>&1 || true
set +e
docker run --name oomlab-kill --memory=128m --memory-swap=128m \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/lab" -w /lab eclipse-temurin:21-jdk \
  java -Xmx200m -cp out/case4/classes ContainerKill \
  > "$OUT/stdout.txt" 2> "$OUT/stderr.txt"
rc=$?
set -e
echo "$rc" > "$OUT/exit_code.txt"
docker inspect --format '{{.State.OOMKilled}}' oomlab-kill > "$OUT/oom_killed.txt" 2>/dev/null || echo unknown > "$OUT/oom_killed.txt"
docker inspect --format '{{.State.ExitCode}}' oomlab-kill > "$OUT/docker_exit_code.txt" 2>/dev/null || true
docker rm -f oomlab-kill >/dev/null 2>&1 || true
if [ "$rc" -eq 137 ]; then echo "outcome=killed_by_SIGKILL(137)" > "$OUT/result.txt"
else echo "outcome=exit_code=$rc" > "$OUT/result.txt"; fi
cat "$OUT/result.txt"; echo "oom_killed=$(cat "$OUT/oom_killed.txt")"
