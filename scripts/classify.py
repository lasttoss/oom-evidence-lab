#!/usr/bin/env python3
"""Classify an OOM event from artifacts: RULES FIRST, model second.

SCOPE: Java only. It covers the nine OutOfMemoryError messages HotSpot can throw
plus the one case where the JVM says nothing because the kernel killed it.

- Reads only files under out/<case>/ — no network, no model call.
- Every conclusion carries a verbatim evidence line taken from a real file.
- The result is always labelled UNCONFIRMED: it is a hypothesis, not a verdict.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from signature import fingerprint, normalise  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HISTO_LINE = re.compile(r"^\s*\d+:\s+(\d+)\s+(\d+)\s+(.+)$")
MODULE_SUFFIX = re.compile(r"\s+\([^)]*\)?\s*$")

RULES = [
    ("direct_buffer", "direct buffer memory",
     "Exceeded -XX:MaxDirectMemorySize. Heap can stay clean: the shortage is off-heap."),
    ("metaspace", "OutOfMemoryError: Metaspace",
     "Metaspace is full: dynamically generated classes, or ClassLoaders never closed."),
    ("compressed_class", "Compressed class space",
     "Compressed Class Space is full: same ClassLoader leak, hitting its own separate region."),
    ("array_too_large", "Requested array size exceeds VM limit",
     "One single allocation is larger than the VM can ever satisfy. This is NOT a leak."),
    ("native_thread", "unable to create native thread",
     "Cannot start a thread: hit the thread limit, pids.max, or the memory reserved for stacks."),
    ("native_thread", "unable to create new native thread",
     "Cannot start a thread: hit the thread limit, pids.max, or the memory reserved for stacks."),
    ("gc_overhead", "GC overhead limit exceeded",
     "Heap almost full and GC recovers almost nothing: live set too large, or a leak."),
    ("heap", "OutOfMemoryError: Java heap space",
     "Genuine heap exhaustion: a real leak, a burst of allocation, or one oversized allocation."),
    ("native_alloc", "Out of Memory Error (",
     "The VM aborted: it could not allocate native memory and printed hs_err_pid instead of throwing. "
     "Nothing was caught, so the exit code is a signal number, not 1."),
    ("native_alloc", "stack_trace_with_native_method",
     "A native method could not allocate. Documented in the Java troubleshooting guide as "
     "\"<reason> stack_trace_with_native_method\"; the top frame of the trace is a native method."),
    ("native_alloc", "Native memory allocation",
     "Native malloc/mmap failed. Usually a container limit, max_map_count, or an off-heap leak. The VM aborts."),
    ("swap", "Out of swap space?",
     "The OS could not commit memory for a thread stack: no swap left, or an overcommitted host."),
]

# Single source of truth for coverage: which kind has a REAL reproduction in this repo.
# A kind with no entry here is covered by a rule and a test, but has never been reproduced.
REPRO = {
    "heap": "case1",
    "direct_buffer": "case2",
    "metaspace": "case3",
    "container_kill": "case4",
    "array_too_large": "case5",
    "native_thread": "case6",
}

# Can the evidence point at WHERE the problem is? Three honest answers.
#   "in-evidence"  the artifact we already have names the site
#   "pre-captured" only something armed BEFORE the death can locate it
#   "never"        nothing in the process can locate it; the death left no location
ATTRIBUTION = {
    "heap": ("in-evidence", "with a dump: retained size + shortest path to a static field (MAT). "
                            "without a dump: diff two histograms to get the growing class, then grep for its holders"),
    "gc_overhead": ("in-evidence", "same as heap: the dump or the histogram diff names the growing class"),
    "array_too_large": ("in-evidence", "the stack trace names the allocation site directly — "
                                       "this is the one kind whose location is in the exception text"),
    "metaspace": ("in-evidence", "VM.metaspace + VM.classloader_stats give the loader count; "
                                 "with a dump, the retained ClassLoader names the generator"),
    "compressed_class": ("in-evidence", "VM.metaspace shows the Compressed Class Space row; "
                                        "the loader that grows is the suspect"),
    "direct_buffer": ("pre-captured", "BufferPoolMXBean over time gives the size, not the site. "
                                      "the allocation site needs JFR or async-profiler -e alloc armed in advance; "
                                      "a heap dump will NOT show it"),
    "native_thread": ("pre-captured", "thread count and pool names come from Thread.print; "
                                      "which code creates threads needs a thread dump taken before the limit is hit"),
    "native_alloc": ("in-evidence", "hs_err_pid: Problematic frame + the failing allocation + the memory map. "
                                    "a full native stack needs a core dump (ulimit -c + core_pattern)"),
    "swap": ("in-evidence", "hs_err_pid; the arithmetic threads x -Xss shows whether stacks are the cause"),
    "container_kill": ("never", "NO in-process location exists: SIGKILL leaves no frames, no dump, no finally. "
                                "The only attribution is what was captured BEFORE the kill — interval snapshots "
                                "(watch.sh) plus the cgroup oom_kill timestamp — and the honest answer is often "
                                "'the ceiling was too low', which is a sizing fact, not a code location"),
}

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
    "gc_overhead": [
        "1) this is a heap kind: read 02 and audit the checks for 'heap'",
        "2) compare the heap after Full GC across snapshots: if the floor rises, it is a leak",
        "3) if the floor is flat, the live set is simply too large for -Xmx: that is a sizing answer",
        "4) do not tune GC flags before you know the floor",
    ],
    "array_too_large": [
        "1) find the allocation site in the stack trace of the error",
        "2) check the input size that produced it: an upload, a batch size, a query without LIMIT",
        "3) fix by streaming or paginating; raising -Xmx will not help",
        "4) add an input guard: reject a request that needs an array above the ceiling",
    ],
    "compressed_class": [
        "1) jcmd <pid> VM.metaspace — look at the Compressed Class Space row separately",
        "2) count classes per ClassLoader: one loader with thousands of classes is the suspect",
        "3) raise -XX:CompressedClassSpaceSize only as a stopgap, then find the loader",
        "4) dump and find the retained ClassLoader: Path to GC root",
    ],
    "native_thread": [
        "1) count threads: jcmd <pid> Thread.print | grep -c '^\"' and compare with the expected pool sizes",
        "2) read the limit: pids.max (cgroup), ulimit -u, /proc/sys/kernel/threads-max",
        "3) compute stack memory: threads x -Xss — that is off-heap and counts against the container",
        "4) look for an unbounded pool or a thread created per request",
    ],
    "native_alloc": [
        "1) read hs_err_pid*.log: it names the exact allocation that failed and the memory map at death",
        "2) if it says mmap/commit failed: compare memory.max with heap + off-heap + stacks",
        "3) check vm.max_map_count for the mmap variant",
        "4) enable -XX:NativeMemoryTracking=summary ahead of time: NMT cannot be switched on after the fact",
    ],
    "swap": [
        "1) free -m and swapon --show: is there swap at all",
        "2) this is an OS-level shortage, not a Java leak",
        "3) reduce -Xss or the thread count; a thread stack is committed at creation",
        "4) on a host with no swap, the same failure surfaces as the kernel killing the process",
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
    haystack = f"{stdout}\n{stderr}".lower()

    if exit_code == "137" or oom_killed == "true":
        return ("container_kill",
                "The kernel (cgroup) killed the process. The JVM threw nothing: no Java line runs "
                "after SIGKILL, so try/catch, finally and shutdown hooks are all void.",
                [f"exit_code={exit_code or 'unavailable'}",
                 f"docker.OOMKilled={oom_killed or 'unavailable'}"])

    for kind, needle, why in RULES:
        if needle.lower() in haystack:
            evidence = [ln.strip() for ln in haystack.splitlines() if needle.lower() in ln][:2]
            return kind, why, evidence

    return "unknown", "Matched no rule. This label is mandatory: never force a guess.", []


TRIAGE = {
    "NEW_SIGNATURE": "Evidence is present and complete, but no rule matches: this is a genuinely "
                     "unseen signature. Add one rule line plus four checks; a case only if reproducible.",
    "CONFIG_GAP":    "Something that should have been armed was not (no NMT, no dump flag, no JFR). "
                     "The gap is configuration, not knowledge: fix it with guard.sh, then wait for the next event.",
    "EVIDENCE_GAP":  "No usable artifact at all: nothing to compare against. The missing piece is "
                     "collection, not a new rule.",
    "TIMING_GAP":    "Artifacts exist but are truncated or empty: the process died mid-write. The gap is "
                     "detection latency, not classification.",
}


def triage(case_dir: Path) -> tuple[str, str]:
    """An unknown has three different causes, and only one of them means 'new kind'."""
    stderr = read(case_dir, "stderr.txt")
    stdout = read(case_dir, "stdout.txt")
    exit_code = read(case_dir, "exit_code.txt").strip()
    histos = [f for f in case_dir.glob("histo-*.txt")
              if "#instances" in f.read_text(errors="replace")]
    has_error_text = "OutOfMemoryError" in stderr or "Out of Memory Error" in stderr

    if not stderr.strip() and not stdout.strip():
        return "EVIDENCE_GAP", "nothing textual was captured (no stderr, no stdout) — " \
                               "only an exit code, which cannot name a kind"
    if has_error_text and histos:
        return "NEW_SIGNATURE", "an OOM message is present, snapshots are present, no rule matches it"
    if has_error_text:
        return "TIMING_GAP", "an OOM message is present but no usable histogram snapshot survived"
    if not stderr.strip() and exit_code == "137":
        return "CONFIG_GAP", "killed with no JVM output: dump/JFR were not armed, and a SIGKILL " \
                             "cannot be dumped at all"
    return "NEW_SIGNATURE", "evidence is present, no rule matches it"


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

    if kind == "unknown":
        cause, why = triage(case_dir)
        lines.append(f"11.why_unknown     {cause} — {why}")
        lines.append(f"     triage: {TRIAGE[cause]}")
        raw = read(case_dir, "stderr.txt") or stdout
        lines.append(f"12.fingerprint     {fingerprint(raw)}   (count variants by this, not by raw text)")
        lines.append(f"     normalised: {normalise(raw) or '(no text captured)'}")

    bundle = read(case_dir, "bundle.txt").strip()
    if bundle:
        lines.append(f"10.stored_at       {bundle}/  (search: grep {kind} out/incidents/index.jsonl)")

    loc, how = ATTRIBUTION.get(kind, ("unknown", "no attribution rule for this kind"))
    lines.append(f"13.attribution     {loc} — {how}")
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
