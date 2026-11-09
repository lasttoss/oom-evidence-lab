# Shared helpers for every case script. Each case writes artifacts into out/<case>/.
set -u
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$LAB_DIR"
JAVA_BIN="${JAVA_BIN:-java}"
JAVAC_BIN="${JAVAC_BIN:-javac}"

require_tools() {
  command -v "$JAVA_BIN"  >/dev/null || { echo "FAIL: java not found in PATH"; exit 1; }
  command -v "$JAVAC_BIN" >/dev/null || { echo "FAIL: javac not found in PATH"; exit 1; }
}

# run_case <case-name> <jvm opts...> -- <MainClass>
# Captures stdout/stderr, snapshots histograms over time, then waits for the exit code.
run_case() {
  local case_name="$1"; shift
  local out="out/$case_name"
  mkdir -p "$out"
  rm -f "$out"/histo-*.txt "$out"/heapinfo-*.txt

  local java_opts=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do java_opts+=("$1"); shift; done
  [ $# -gt 0 ] && shift
  local main_class="$1"

  "$JAVA_BIN" "${java_opts[@]}" -cp "$out/classes" "$main_class" \
      > "$out/stdout.txt" 2> "$out/stderr.txt" &
  local pid=$!
  echo "$pid" > "$out/pid.txt"

  local shot=0
  while kill -0 "$pid" 2>/dev/null; do
    sleep 3
    shot=$((shot + 1))
    timeout 20 jcmd "$pid" GC.class_histogram > "$out/histo-$shot.txt" 2>/dev/null || true
    timeout 15 jcmd "$pid" GC.heap_info       > "$out/heapinfo-$shot.txt" 2>/dev/null || true
    [ "$shot" -ge 6 ] && break
  done

  wait "$pid"; local rc=$?
  echo "$rc" > "$out/exit_code.txt"
  case "$rc" in
    0)   echo "outcome=normal_exit"                > "$out/result.txt" ;;
    137) echo "outcome=killed_by_SIGKILL(137)"     > "$out/result.txt" ;;
    *)   echo "outcome=exit_code=$rc"              > "$out/result.txt" ;;
  esac
}
