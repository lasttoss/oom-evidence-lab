#!/usr/bin/env python3
"""Rule table test: every HotSpot OOM message maps to exactly one kind.

Synthetic signatures only — no JVM is started. Run: python3 scripts/test_classify.py
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("classify", Path(__file__).with_name("classify.py"))
classify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classify)

CASES = [
    # (stderr line, exit_code, oom_killed, expected kind)
    ("java.lang.OutOfMemoryError: Java heap space", "1", None, "heap"),
    ("java.lang.OutOfMemoryError: GC overhead limit exceeded", "1", None, "gc_overhead"),
    ("java.lang.OutOfMemoryError: Requested array size exceeds VM limit", "1", None, "array_too_large"),
    ("java.lang.OutOfMemoryError: Metaspace", "1", None, "metaspace"),
    ("java.lang.OutOfMemoryError: Compressed class space", "1", None, "compressed_class"),
    ("java.lang.OutOfMemoryError: Cannot reserve 1 bytes of direct buffer memory", "1", None, "direct_buffer"),
    ("java.lang.OutOfMemoryError: unable to create native thread: possibly out of memory", "1", None, "native_thread"),
    ("java.lang.OutOfMemoryError: unable to create new native thread", "1", None, "native_thread"),
    ("Out of Memory Error (allocation.cpp:505), pid=1, tid=1", "134", None, "native_alloc"),
    ("Native memory allocation (mmap) failed to map 12288 bytes", "1", None, "native_alloc"),
    ("java.lang.OutOfMemoryError: Out of swap space?", "1", None, "swap"),
    ("", "137", "true", "container_kill"),
    ("", "137", None, "container_kill"),
    ("something nobody has seen before", "1", None, "unknown"),
]


def run_case(stderr: str, exit_code: str, oom_killed) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "stderr.txt").write_text(stderr + "\n")
        (d / "exit_code.txt").write_text(exit_code + "\n")
        if oom_killed is not None:
            (d / "oom_killed.txt").write_text(oom_killed + "\n")
        (d / "stdout.txt").write_text("progress=1\n")
        return classify.classify(d)[0]


TRIAGE_CASES = [
    # (stderr, exit_code, histo?, expected triage cause)
    ('Exception in thread "main" java.lang.OutOfMemoryError: something new', "1", True, "NEW_SIGNATURE"),
    ('Exception in thread "main" java.lang.OutOfMemoryError: something new', "1", False, "TIMING_GAP"),
    ("", "1", False, "EVIDENCE_GAP"),
]


def run_triage(stderr: str, code: str, with_histo: bool) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "stderr.txt").write_text(stderr + "\n")
        (d / "exit_code.txt").write_text(code + "\n")
        (d / "stdout.txt").write_text("progress=1\n" if stderr else "")
        if with_histo:
            (d / "histo-1.txt").write_text(" #instances #bytes class name\n1: 5 80 [B\n")
        return classify.triage(d)[0]


def main() -> int:
    failed = 0
    for stderr, code, killed, expected in CASES:
        got = run_case(stderr, code, killed)
        ok = got == expected
        failed += 0 if ok else 1
        label = stderr[:58] or f"exit={code} oom_killed={killed}"
        print(f"{'PASS' if ok else 'FAIL'}  {expected:<17} {label}")
    for stderr, code, with_histo, expected in TRIAGE_CASES:
        got = run_triage(stderr, code, with_histo)
        ok = got == expected
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  triage:{expected:<14} histo={with_histo}")
    total = len(CASES) + len(TRIAGE_CASES)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
