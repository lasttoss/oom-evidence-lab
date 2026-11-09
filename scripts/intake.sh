#!/usr/bin/env bash
# intake.sh — someone reported an OOM we do not recognise. Collect the standard field set first,
# decide later. This never guesses and never edits the rule table; it only gathers.
#
# Usage: scripts/intake.sh <pid> [label]
set -u
PID="${1:?usage: intake.sh <pid> [label]}"
LABEL="${2:-report}"
OUT="out/intake/$(date -u +%Y%m%dT%H%M%SZ)-$LABEL"
mkdir -p "$OUT"

echo "intake_dir=$OUT"
bash "$(dirname "$0")/collect.sh" "$PID" > "$OUT/resource-fields.txt" 2>&1 || true
[ -r "/sys/fs/cgroup/memory.events" ] && cp /sys/fs/cgroup/memory.events "$OUT/cgroup-memory.events"
cat /proc/"$PID"/cgroup            > "$OUT/cgroup-path.txt" 2>/dev/null || true
cat /proc/"$PID"/limits            > "$OUT/limits.txt"      2>/dev/null || true
cat /proc/"$PID"/status            > "$OUT/proc-status.txt" 2>/dev/null || true
ps -o pid,rss,vsz,nlwp,etime,cmd -p "$PID" > "$OUT/ps.txt"  2>/dev/null || true
dmesg -T 2>/dev/null | grep -iE 'out of memory|killed process' | tail -20 > "$OUT/dmesg.txt" 2>/dev/null || true
ls -t hs_err_pid*.log 2>/dev/null | head -3 > "$OUT/hs-err-index.txt" || true
timeout 30 jcmd "$PID" VM.flags > "$OUT/vm-flags.txt" 2>/dev/null || true

cat > "$OUT/README.txt" <<TXT
Intake bundle for one unrecognised OOM event ($(date -u +%FT%TZ)).

Collected, not interpreted. Do these five things, in this order:
  1. read resource-fields.txt: ceiling first, then the signal, then usage
  2. find the verbatim signature in the log and add one line to scripts/classify.py RULES
  3. add its four ordered checks to CHECKS
  4. reproduce it in cases/ if a container can: add a case and register it in REPRO
     (if it cannot be reproduced, leave REPRO alone — the coverage table will show level B)
  5. add one line to scripts/test_classify.py, then run:
       python3 scripts/test_classify.py && python3 scripts/coverage.py
TXT

echo "collected: $(ls -1 "$OUT" | tr '\n' ' ')"
echo "next: read $OUT/README.txt"
