#!/usr/bin/env bash
# upstream.sh — check our rule table against the authoritative source: the JDK source tree.
#
# There is no vendor-published "OOM error code table" for Java. The de facto canonical list IS the
# string literals in HotSpot, so the honest way to keep the table current is to read them from source
# and notice when they change. This script does exactly that, and nothing else.
#
# Usage: scripts/upstream.sh [--offline]
set -u
REF="${JDK_REF:-master}"
BASE="https://raw.githubusercontent.com/openjdk/jdk/$REF/src"
OFFLINE=0
[ "${1:-}" = "--offline" ] && OFFLINE=1

# literal | file it lives in (verified by fetching the file, not remembered)
MANIFEST=$(cat <<'M'
Java heap space|hotspot/share/memory/universe.cpp
GC overhead limit exceeded|hotspot/share/memory/universe.cpp
Requested array size exceeds VM limit|hotspot/share/memory/universe.cpp
Metaspace|hotspot/share/memory/universe.cpp
Compressed class space|hotspot/share/memory/universe.cpp
bytes of direct buffer memory|java.base/share/classes/java/nio/Bits.java
Native memory allocation|hotspot/share/utilities/vmError.cpp
M
)

# Literals we have NOT pinned to a file yet. Listed openly instead of guessed.
UNPINNED="unable to create native thread|Out of swap space?"

echo "jdk=${JDK_REF:-master}(${REF})  mode=$([ $OFFLINE -eq 1 ] && echo offline || echo network)"
echo
fail=0
while IFS='|' read -r literal file; do
  [ -z "$literal" ] && continue
  if [ "$OFFLINE" -eq 1 ]; then printf "SKIP  %-42s (%s)\n" "$literal" "$file"; continue; fi
  body=$(curl -sS --max-time 25 "$BASE/$file" 2>/dev/null)
  if [ -z "$body" ]; then printf "ERROR %-42s cannot fetch %s\n" "$literal" "$file"; fail=1; continue; fi
  if printf '%s' "$body" | grep -qF "$literal"; then
    printf "OK    %-42s %s\n" "$literal" "$file"
  else
    printf "DRIFT %-42s NOT FOUND in %s  -> the wording changed upstream; update RULES\n" "$literal" "$file"
    fail=1
  fi
done <<< "$MANIFEST"

echo
echo "not pinned to a file yet (checked by eye, not by this script):"
printf '%s\n' "$UNPINNED" | tr '|' '\n' | sed 's/^/  - /'

echo
echo "human cross-check (documents 7 of the 10 kinds, in words, with cause and action):"
echo "  https://docs.oracle.com/javase/8/docs/technotes/guides/troubleshoot/memleaks002.html"
echo "  see docs/UPSTREAM.md for the reconciliation table"
echo
echo "new messages arrive here first — check when a JDK upgrade lands:"
echo "  https://bugs.openjdk.org/issues/?jql=text%20~%20%22OutOfMemoryError%22%20ORDER%20BY%20created%20DESC"
echo "  https://github.com/openjdk/jdk/commits/$REF/src/hotspot/share/memory/universe.cpp"

[ "$fail" -eq 0 ] && echo "RESULT upstream=match" || echo "RESULT upstream=DRIFT (see lines above)"
exit "$fail"
