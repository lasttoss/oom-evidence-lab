# Two references, and why both are needed

A fingerprint is **not** a global identifier for an OOM. It is a grouping key over the *text* of one
message, computed with our own normalisation — comparable inside this repo's index, and not comparable
with Sentry's fingerprints, Elastic's `fingerprint` field, or anyone else's. Same idea, different keys.

To **check** a classification you need references outside the repo. There are two, and they do not
agree, which is the point.

## Reference 1 — the documentation (for humans)

Oracle Java SE Troubleshooting Guide, *Understand the OutOfMemoryError Exception*:
<https://docs.oracle.com/javase/8/docs/technotes/guides/troubleshoot/memleaks002.html>

It documents seven detail messages, with cause and action for each.

## Reference 2 — the source (for the machine)

The string literals in HotSpot. `make upstream` fetches them and asserts they still exist, because a
JDK upgrade can reword a message and silently invalidate a rule.

## The reconciliation table

| Kind | In the doc | In the source | Note |
|---|---|---|---|
| `heap` | yes | `memory/universe.cpp` | |
| `gc_overhead` | yes | `memory/universe.cpp` | doc gives the exact thresholds: >98% GC time, <2% recovered, 5 consecutive collections |
| `array_too_large` | yes | `memory/universe.cpp` | doc is explicit: independent of how much heap is free |
| `metaspace` | yes | `memory/universe.cpp` | |
| `compressed_class` | yes | `memory/universe.cpp` | doc: only `klass` metadata lives here, the rest is Metaspace |
| `swap` | yes — as "request size bytes for reason. Out of swap space?" | `utilities/vmError.cpp` | doc notes the VM then writes a fatal error log |
| `native_alloc` | yes — as "<reason> stack_trace_with_native_method" | `utilities/vmError.cpp` | top frame is a native method; this form was **missing from our rules until this cross-check** |
| `direct_buffer` | **no** | `java.nio.Bits` | message is composed in Java (`Cannot reserve N bytes of direct buffer memory (allocated: …, limit: …)`) |
| `native_thread` | **no** | not yet pinned | documented only in bug reports and forum threads; the wording changed across JDKs ("unable to create new native thread" → "…: possibly out of memory or process/resource limits reached") |
| `container_kill` | n/a — not a Java message | kernel | exit 137, `OOMKilled=true`; no Java line runs |

**What this table proves:** the doc is authoritative but incomplete (it stops at the messages the
HotSpot team chose to document), and the source is complete but unreadable to a human. A rule table
built from only one of them is either wrong or unmaintainable.

**And it already paid off once:** cross-checking the doc surfaced `stack_trace_with_native_method`,
a documented message that our rule table did not match. It now maps to `native_alloc` and has a test.
