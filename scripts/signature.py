#!/usr/bin/env python3
"""Normalise an OOM signature into a fingerprint, so unknown events can be counted.

Why: "50 unknown events" may be 3 distinct signatures, or 50. Without a fingerprint you cannot
tell whether the taxonomy is growing or whether one rule is simply too narrow.

Normalisation drops everything that varies between two occurrences of the SAME problem:
numbers, hex ids, UUIDs, quoted strings, absolute paths, timestamps.
"""
from __future__ import annotations

import hashlib
import re

UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
HEX = re.compile(r"\b0x[0-9a-f]+\b", re.I)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?")
QUOTED = re.compile(r'"[^"]{0,120}"')
PATH = re.compile(r"(?<![\w.])/(?:[\w.\-]+/)*[\w.\-]+")
NUM = re.compile(r"\b\d[\d_,.]*\b")

# The first line that actually names the failure. Anything before it is noise.
SIGNAL = re.compile(
    r"(java\.lang\.OutOfMemoryError.*|Out of Memory Error.*|"
    r"Native memory allocation \([^)]*\) failed.*|Out of swap space\?.*|"
    r"Could not reserve enough space.*|Could not allocate.*|"
    r"fatal error.*|SIGSEGV.*|Aborted.*)",
    re.I,
)


def signal_line(text: str) -> str:
    """Return the line that names the failure, else the last non-empty line."""
    for line in (text or "").splitlines():
        if SIGNAL.search(line):
            return line.strip()
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def normalise(text: str) -> str:
    s = signal_line(text).lower()
    s = ISO.sub("<ts>", s)
    s = UUID.sub("<uuid>", s)
    s = HEX.sub("<hex>", s)
    s = PATH.sub("<path>", s)
    s = QUOTED.sub("<str>", s)
    s = NUM.sub("<n>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:300]


def fingerprint(text: str) -> str:
    return hashlib.sha1(normalise(text).encode("utf-8")).hexdigest()[:12]


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:] or [sys.stdin.read()]:
        print(f"{fingerprint(arg)}  {normalise(arg)}")
