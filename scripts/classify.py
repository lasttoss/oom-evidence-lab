#!/usr/bin/env python3
"""Classify an OOM event from artifacts: RULES FIRST, model second.

- Reads only files under out/<case>/ — no network, no model call.
- Every conclusion carries a verbatim evidence line taken from a real file.
- The result is always labelled UNCONFIRMED: it is a hypothesis, not a verdict.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTO_LINE = re.compile(r"^\s*\d+:\s+(\d+)\s+(\d+)\s+(.+)$")
MODULE_SUFFIX = re.compile(r"\s+\([^)]*\)?\s*$")

RULES = [
    ("direct_buffer", "direct buffer memory",
     "Exceeded -XX:MaxDirectMemorySize. Heap can stay clean: the shortage is off-heap."),
    ("metaspace", "OutOfMemoryError: Metaspace",
     "Metaspace is full: dynamically generated classes or ClassLoaders that are never closed."),
    ("metaspace", "OutOfMemoryError: Compressed class space",
     "Compressed Class Space is full: same ClassLoader leak, hitting its own separate region."),
    ("heap", "OutOfMemoryError: Java heap space",
     "Genuine heap exhaustion: a real leak, a burst of allocation, or one oversized allocation."),
    ("heap", "OutOfMemoryError: GC overhead limit exceeded",
     "Heap almost full and GC recovers almost nothing: live set too large, or a leak."),
]

CHECKS = {
    "heap": [
        "1) open the dump: % of live heap, your class or a JDK class, any Shortest Path to a static field",
        "2) compare 08: a class growing steadily across snapshots is suspect #1",
        "3) no dump available: enable -XX:+HeapDumpOnOutOfMemoryError to a real volume and wait for the next event",
        "4) also rule out a non-leak cause: one query returning millions of rows, image processing, humongous objects",
    ],
    "direct_buffer": [
        "1) jcmd <pid> VM.flags | grep MaxDirectMemorySize — compare with real traffic",
        "2) BufferPoolMXBean: count and capacity of 'direct' over time",
        "3) check the source: Netty pooled allocator, NIO temporary buffers per thread (IOUtil)",
        "4) if Netty: check leaked refCnt (buffers never released)",
    ],
    "metaspace": [
        "1) jcmd <pid> VM.metaspace — used / committed / max, including Compressed Class Space",
        "2) track jvm_classes_loaded per day: steady growth means dynamic class generation",
        "3) find the generator: CGLIB/proxies, JSP, hot-reload, Groovy, script engines",
        "4) dump and find the retained ClassLoader: Path to GC root",
    ],
    "container_kill": [
        "1) compare cgroup memory.max with Xmx + off-heap + overhead (do NOT hunt for a leak yet)",
        "2) read /sys/fs/cgroup/memory.events: how much did oom_kill increase",
        "3) check HPA/limits: was the limit lowered below real demand",
        "4) only after ruling out 1-3, look for a leak",
    ],
    "unknown": [
        "1) add evidence: exit code, cgroup oom_kill, stderr, two histogram snapshots",
        "2) never force a guess: 'unknown' is a legitimate result",
    ],
}


def read(case_dir: Path, name: str) -> str:
    p = case_dir / name
    return p.read_text(errors="replace") if p.exists() else ""


def parse_histo(path: Path) -> dict[str, tuple[int, int]]:
    """Parse `jcmd GC.class_histogram`. Skip files truncated by the process dying mid-write."""
    out: dict[str, tuple[int, int]] = {}
    if not path.exists():
        return out
    text = path.read_text(errors="replace")
    if "#instances" not in text:
        return out
    for line in text.splitlines():
        m = HISTO_LINE.match(line)
        if not m:
            continue
        inst, size, cls = int(m.group(1)), int(m.group(2)), m.group(3).strip()
        cls = MODULE_SUFFIX.sub("", cls).strip()
        if cls:
            out[cls] = (inst, size)
    return out


def histo_growth(case_dir: Path) -> list[tuple[str, int, int]]:
    files = sorted(case_dir.glob("histo-*.txt"), key=lambda p: int(p.stem.split("-")[1]))
    files = [f for f in files if "#instances" in f.read_text(errors="replace")]
    if len(files) < 2:
        return []
    first, last = parse_histo(files[0]), parse_histo(files[-1])
    growth = []
    for cls, (inst2, size2) in last.items():
        inst1, size1 = first.get(cls, (0, 0))
        if size2 - size1 >= 1024 and inst2 >= inst1:
            growth.append((cls, size2 - size1, inst2 - inst1))
    growth.sort(key=lambda t: t[1], reverse=True)
    return growth[:3]


def classify(case_dir: Path) -> tuple[str, str, list[str]]:
    stdout, stderr = read(case_dir, "stdout.txt"), read(case_dir, "stderr.txt")
    exit_code = read(case_dir, "exit_code.txt").strip()
    oom_killed = (read(case_dir, "oom_killed.txt").strip() or "").lower()
    haystack = f"{stdout}\n{stderr}"

    if exit_code == "137" or oom_killed == "true":
        return ("container_kill",
                "The kernel (cgroup) killed the process. The JVM threw nothing: no Java line runs "
                "after SIGKILL, so try/catch, finally and shutdown hooks are all void.",
                [f"exit_code={exit_code or 'unavailable'}",
                 f"docker.OOMKilled={oom_killed or 'unavailable'}"])

    for kind, needle, why in RULES:
        if needle in haystack:
            evidence = [ln.strip() for ln in haystack.splitlines() if needle in ln][:2]
            return kind, why, evidence

    return "unknown", "Matched no rule. This label is mandatory: never force a guess.", []


def fmt_bytes(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def alert_for(case_dir: Path) -> str:
    kind, why, evidence = classify(case_dir)
    stdout = read(case_dir, "stdout.txt")
    exit_code = read(case_dir, "exit_code.txt").strip() or "unavailable"
    dump = read(case_dir, "dump.txt").strip()
    marker = ([ln for ln in stdout.splitlines() if "=" in ln] or ["unavailable"])[-1]

    lines = [
        f"===== ALERT — {case_dir.name} =====",
        f"01.kind            {kind}",
        f"02.note            UNCONFIRMED — this is a hypothesis, not a verdict",
        f"03.explanation     {why}",
        f"04.exit_code       {exit_code}",
        f"05.progress_marker {marker}",
        f"06.heap_dump       {dump or 'none (not enabled, or not written in time)'}",
    ]
    for i, ev in enumerate(evidence, 1):
        lines.append(f"07.evidence_{i}     {ev}")

    growth = histo_growth(case_dir)
    if growth:
        lines.append("08.fastest_growing_classes (first snapshot vs last)")
        for cls, dbytes, dinst in growth:
            lines.append(f"     +{fmt_bytes(dbytes):>10}  +{dinst:>8} instance  {cls}")
    else:
        lines.append("08.histo           fewer than two usable snapshots")

    lines.append("09.checks_in_order")
    lines.extend(f"     {c}" for c in CHECKS.get(kind, []))

    bundle = read(case_dir, "bundle.txt").strip()
    if bundle:
        lines.append(f"10.stored_at       {bundle}/  (search: grep {kind} out/incidents/index.jsonl)")
    return "\n".join(lines)


def main() -> int:
    targets = [Path(a) for a in sys.argv[1:]] or sorted(
        p for p in (ROOT / "out").glob("case*") if p.is_dir())
    if not targets:
        print("no artifacts under out/ — run `make demo` first")
        return 1
    for t in targets:
        if t.is_dir():
            print(alert_for(t))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
