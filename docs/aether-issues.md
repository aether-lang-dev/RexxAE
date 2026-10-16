# Toolchain findings, 2026-10-16

## Repeated trusted service call consumes authority storage on 0.802

The standalone [reproducer](../tests/repros/trusted_service_repeat.ae) imports
only std.sandbox, std.audit and the configuration service. It does not import,
link or execute RexxAE. Run from the repository root:

```sh
AETHER_CACHE_DIR=build/cache ae build tests/repros/trusted_service_repeat.ae -o build/repro_trusted_service_repeat
AETHER_SANDBOX_AUDIT=stderr ./build/repro_trusted_service_repeat
valgrind --leak-check=full --error-exitcode=99 ./build/repro_trusted_service_repeat
```

Expected: three public configuration reads, each allowed by the service's
own fixed-path fence. Observed on installed Aether 0.802.0: one successful read,
then two `DENIED` results. Audit records allow/deny/deny for the same path.
Valgrind reports six invalid reads from three contexts, with no leaked blocks.
The reads pass through `list_size` / `list_get_raw`,
`_aether_sandbox_check_impl`, `aether_sandbox_check_slow` and `file_open_raw`.
The list was allocated and freed inside the containing closure. This supports
a consumed/dangling trusted-authority snapshot diagnosis; no upstream source
fix has been attempted here. An observed denial is insufficient evidence of
safe containment when the checker reads freed memory.

The binary containment host now creates a fresh sealed enforcement frame per
engine step/event. Its grants and dispatcher stay host-owned; only READ_CONFIG
is trusted, and that service retains its own fixed-path sandbox. Every frame
inherits any enclosing restriction. A repeated mounted-service call followed
by an untrusted filesystem request exercises both successful reentry and veto.
This avoids reusing the consumed snapshot; it does not widen authority or
disable any memory checks. Both library variants must pass `make memcheck`.

The reproducer intentionally preserves the failing long-lived-frame pattern
and is separate from the passing engine suite. Rerun it after an Aether fix;
do not infer that an ordinary deny-only test has verified the lifetime issue.

## Current development compiler and stdlib do not build together

The development executable reports 0.815.0. Building the engine, or a minimal
program importing only std.string, fails on its checkout's stdlib declarations:

```text
error[E0100]: @heap on extern return is only valid on `-> string`
extern string_from_int(value: int) -> ptr @heap
```

Similar errors include `*StringSeq @heap` returns. The minimal program is:

```aether
import std.string
main() { println(string.to_upper("rexx")) }
```

This migration is validated with installed 0.802.0. The previous implementation
passed development 0.815.0 before this checkout/compiler mismatch arose; that
historical result does not validate the new code on the current dev tree.
The read-only Aether checkout and installed toolchains were left unchanged.
