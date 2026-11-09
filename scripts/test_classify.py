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


def main() -> int:
    failed = 0
    for stderr, code, killed, expected in CASES:
        got = run_case(stderr, code, killed)
        ok = got == expected
        failed += 0 if ok else 1
        label = stderr[:58] or f"exit={code} oom_killed={killed}"
        print(f"{'PASS' if ok else 'FAIL'}  {expected:<17} {label}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
