#!/usr/bin/env python3
"""Propose rules for unknown signatures — PROPOSE, never apply.

The loop this closes:
    event -> unknown -> fingerprint -> cluster -> CANDIDATE RULE -> human merges

What is automated: clustering, candidate generation, and — the important part — VALIDATION of the
candidate against every signature already stored, so a new rule cannot silently steal an existing kind.

What is never automated: naming the kind and writing its four checks. That is a judgement about the
world, not a string transformation.

Usage: lab/report/learn.py [--min-events N]
Writes out/learn/candidates.json and prints a review sheet.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))
from signature import fingerprint, normalise, signal_line  # noqa: E402

INDEX = ROOT / "out" / "incidents" / "index.jsonl"
OUTDIR = ROOT / "out" / "learn"

# Whole-line conditions that make a candidate too vague to be a rule.
TOO_SHORT = 18
MIN_NEEDLE = 15
GENERIC = re.compile(r"^(error|failed|exception|outofmemoryerror|unknown)\W*$", re.I)


def load() -> list[dict]:
    if not INDEX.exists():
        return []
    return [json.loads(l) for l in INDEX.read_text(encoding="utf-8").splitlines() if l.strip()]


def raw_text(rec: dict) -> str:
    for name in ("stderr.txt", "stdout.txt"):
        p = ROOT / rec["bundle"] / name
        if p.exists():
            text = p.read_text(errors="replace").strip()
            if text:
                return text
    return ""


WILDCARD = {
    "<hex>": r"0x[0-9a-fA-F]+",
    "<uuid>": r"[0-9a-fA-F-]{20,}",
    "<path>": r"/\S+",
    "<ts>": r"\d{4}-\d{2}-\d{2}",
    "<str>": r'".*?"',
    "<n>": r"\d+",
}


def candidate_needle(text: str) -> str:
    """The longest stable literal run — this is what the matcher actually uses (case-insensitive)."""
    norm = normalise(text)
    runs = [r.strip() for r in re.split(r"(<hex>|<uuid>|<path>|<ts>|<str>|<n>)", norm)]
    runs = [r for r in runs if r and not r.startswith("<")]
    return max(runs, key=len) if runs else ""


def candidate_pattern(text: str) -> str:
    """Build the regex from the NORMALISED line, so every wildcard is explicit and testable."""
    norm = normalise(text)
    parts = []
    for chunk in re.split(r"(<hex>|<uuid>|<path>|<ts>|<str>|<n>)", norm):
        if chunk in WILDCARD:
            parts.append(WILDCARD[chunk])
        elif chunk:
            parts.append(re.escape(chunk))
    return "".join(parts)


def validate(pattern: str, own_fp: str, corpus: dict[str, list[dict]]) -> list[str]:
    """Reject a candidate that would steal events from a kind that is already classified."""
    conflicts = []
    rx = re.compile(pattern)
    for fp, recs in corpus.items():
        if fp == own_fp:
            continue
        kinds = {r["kind"] for r in recs}
        if any(r["kind"] != "unknown" for r in recs):
            sample = signal_line(raw_text(recs[0]))
            if rx.search(sample):
                conflicts.append(f"matches known kind {sorted(kinds)}: {sample[:90]}")
    return conflicts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-events", type=int, default=2,
                    help="occurrences before a rule is proposed (default 2: never from one sample)")
    args = ap.parse_args()

    records = load()
    if not records:
        print("no incidents stored — run `make demo` first")
        return 1

    corpus: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        corpus[r.get("fp") or "-"].append(r)

    unknown = {fp: rs for fp, rs in corpus.items() if all(r["kind"] == "unknown" for r in rs)}
    if not unknown:
        print(f"0 unknown signatures among {len(records)} stored incidents — nothing to propose.")
        print("This is not proof of completeness; it means nothing outside the rule table was captured.")
        return 0

    OUTDIR.mkdir(parents=True, exist_ok=True)
    proposals, waiting, rejected = [], [], []

    for fp, recs in sorted(unknown.items(), key=lambda kv: -len(kv[1])):
        sample = signal_line(raw_text(recs[-1]))
        norm = normalise(raw_text(recs[-1]))
        entry = {"fp": fp, "events": len(recs), "sample": sample, "normalised": norm}

        if len(recs) < args.min_events:
            waiting.append({**entry, "why": f"only {len(recs)} occurrence(s); "
                                           f"{args.min_events} required before proposing a rule"})
            continue
        if len(norm) < TOO_SHORT or GENERIC.match(norm.replace(" ", "")):
            rejected.append({**entry, "why": "signature too generic to be a rule — it would match everything"})
            continue

        needle = candidate_needle(raw_text(recs[-1]))
        if len(needle) < MIN_NEEDLE:
            rejected.append({**entry, "why": f"no stable literal run of {MIN_NEEDLE}+ chars — "
                                            f"the message is almost entirely variable"})
            continue
        pattern = candidate_pattern(raw_text(recs[-1]))
        conflicts = validate(pattern, fp, corpus)
        if conflicts:
            rejected.append({**entry, "why": "candidate steals events from a classified kind", "conflicts": conflicts})
            continue
        proposals.append({**entry, "needle": needle, "pattern": pattern})

    (OUTDIR / "candidates.json").write_text(
        json.dumps({"proposals": proposals, "waiting": waiting, "rejected": rejected}, indent=2) + "\n",
        encoding="utf-8")

    print(f"unknown signatures={len(unknown)}  proposals={len(proposals)}  "
          f"waiting={len(waiting)}  rejected={len(rejected)}")
    for p in proposals:
        print(f"\n--- PROPOSAL fp={p['fp']} events={p['events']}")
        print(f"  sample   {p['sample'][:110]}")
        print(f"  rule     (\"<kind>\", {p['needle']!r},")
        print(f"            \"<one sentence: what is actually exhausted>\"),")
        print( "  checks   four ordered checks — a thread problem is not a heap problem")
        print(f"  test     ({p['sample'][:60]!r}, \"1\", None, \"<kind>\"),")
        print(f"  regex    (reference only, not used by the matcher): {p['pattern']}")
    for w in waiting:
        print(f"\n--- WAITING fp={w['fp']} events={w['events']}: {w['why']}")
    for r in rejected:
        print(f"\n--- REJECTED fp={r['fp']} events={r['events']}: {r['why']}")
        for c in r.get("conflicts", []):
            print(f"    conflict: {c}")
    print(f"\nwrote {OUTDIR.relative_to(ROOT)}/candidates.json")
    print("Nothing was applied. Naming the kind and writing its four checks is a human step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
