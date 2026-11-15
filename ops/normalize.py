#!/usr/bin/env python3
"""Compare two docs/ trees after masking the fields that are *measurements*, not facts.

Three things in the generated docs cannot be identical between two runs, because they are
read from a real process death:

  1. wall-clock timestamps     20261115T123033816114Z, 2026-11-15T12:30:33+00:00
  2. how long the JVM took to write a heap dump   "in 0.468 secs"
  3. the size of that dump in bytes               heap_dump_bytes=238530625, [238530625 bytes
  4. the per-run bundle directory name (it carries the timestamp)

Everything else — kind, exit code, the verbatim OOM message, the ordered checks, the
attribution text, the coverage and gap tables — must match byte for byte. If it does not,
the committed docs are stale and this exits 1.

Usage: normalize.py <regenerated_dir> <committed_dir>
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

MASKS: list[tuple[str, str]] = [
    (r"\d{8}T\d{12,}Z", "<RUNSTAMP>"),          # 20261115T123033816114Z
    (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", "<ISO>"),  # 2026-11-15T12:30:33+00:00
    (r"in \d+\.\d+ secs", "in <SECS> secs"),     # heap dump timing
    (r"heap_dump_bytes=\d+", "heap_dump_bytes=<BYTES>"),
    (r"\[\d+ bytes", "[<BYTES> bytes"),
    (r"\b\d+ MB\b", "<MB> MB"),                   # the same dump, rounded for the table
    (r"<RUNSTAMP>-case", "<RUNSTAMP>-case"),     # keep the case suffix comparable
]


def mask(text: str) -> str:
    for pattern, repl in MASKS:
        text = re.sub(pattern, repl, text)
    return text


def compare(regenerated: Path, committed: Path) -> int:
    failures = 0
    names = sorted({p.name for p in regenerated.glob("*.md")} | {p.name for p in committed.glob("*.md")})
    for name in names:
        a, b = committed / name, regenerated / name
        if not a.exists() or not b.exists():
            print(f"FAIL {name}: exists on one side only")
            failures += 1
            continue
        left, right = mask(a.read_text(encoding="utf-8")).splitlines(), mask(b.read_text(encoding="utf-8")).splitlines()
        if left == right:
            print(f"OK   {name}")
            continue
        failures += 1
        print(f"FAIL {name}: differs after masking the measured fields")
        for line in list(difflib.unified_diff(left, right, "committed", "regenerated", lineterm="", n=1))[:20]:
            print("     " + line)
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(compare(Path(sys.argv[1]), Path(sys.argv[2])))
