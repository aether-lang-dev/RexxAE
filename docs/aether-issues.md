# Toolchain findings, 2026-10-19

RexxAE now targets installed **Aether 0.829.0**. Use
`/home/paul/.aether/bin/ae` (or `ae` while that version is selected).
A forced 0.829 rebuild passes all 397 native specs, C and both Aether binary
consumers, containment probes, 507 strict reference comparisons and Valgrind.
The standalone trusted-service reproducer and three regressions still pass.
The development-tree executable at `/home/paul/scm/aether/build/ae` currently
reports 0.820.0, so it was not used for this validation. The source checkout
revision alone does not identify the compiler executable being tested.

## Trusted sandbox-call lifetime: fixed by 0.823, still passes on 0.829

A fresh 0.829 build of the original standalone
[reproducer](../tests/repros/trusted_service_repeat.ae) now returns public
configuration three times. Valgrind exits zero with no invalid reads, no
errors and no leaked blocks. This reproducer imports only std.sandbox,
std.audit and the configuration service; it does not link or run RexxAE.

Run from `/home/paul/scm/rexxae/RexxAE`:

```sh
AETHER_CACHE_DIR=build/cache /home/paul/.aether/bin/ae build tests/repros/trusted_service_repeat.ae -o build/repro_trusted_service_repeat
AETHER_SANDBOX_AUDIT=stderr ./build/repro_trusted_service_repeat
valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/repro_trusted_service_repeat
```

[tests/test_trusted_service.ae](../tests/test_trusted_service.ae) promotes the
issue into three regular std.spec regressions, run by `make containment`
and `make memcheck`:

- Repeated trusted reads within one long-lived enforcement frame succeed.
- Successful and early-refused service calls restore deny-all authority;
  an untrusted private-file read is vetoed, and another trusted read succeeds.
- Repeated trusted calls cannot widen an enclosing deny-all sandbox.

The binary host retains a fresh sealed enforcement frame per engine event.
This remains a valid embedding pattern, but is no longer required to avoid
this lifetime issue on the tested 0.829 compiler. The independent regression
uses one long-lived frame so this host structure cannot mask a recurrence.

Historical results: installed 0.802.0 and development 0.819.0 (Aether commit
`ed6dbb0d`) returned one successful read followed by two `DENIED` results.
Valgrind reported six invalid reads from three contexts. The checker reached
`list_size` / `list_get_raw` through `_aether_sandbox_check_impl` and
`file_open_raw`, reading grant-list storage freed by `sandbox_enforce`.
Those older denials were not evidence of safe containment.

## Previous compiler/stdlib annotation mismatch: resolved

Development 0.815.0 previously rejected std.string declarations such as:

```text
error[E0100]: @heap on extern return is only valid on `-> string`
extern string_from_int(value: int) -> ptr @heap
```

The engine and stdlib built together on 0.819.0 and now build on installed
0.823.0 and 0.829.0. No annotation workaround in the engine is needed.

The host-test helper uses
`contained_event(ctx: @keep ptr, worker: sandbox.Grants)`: its enforcement
callback captures the opaque context, and the caller owns the context until
the synchronous helper returns. This meets the raw-pointer capture contract
introduced in the newer compiler. Public engine ABI and effect guards are
unchanged.

The Aether reference checkout and installed toolchains were left unchanged.
Full verification totals are recorded in README.md.
