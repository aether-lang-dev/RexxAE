> Archived investigation, captured before the documentation cleanup on 2026-10-20.
> Versions, test totals and implementation status below describe that snapshot;
> use the [current documentation](../../README.md) for supported behavior.

# Compatibility baselines

## Updated checkouts, 2026-10-19

| Source | Current revision | Audit result |
|---|---|---|
| RexxJS standalone | `8317bd1c2adeb966ea0eb9a91331f80c45bb79a1` | 507/507 existing strict programs; 16/28 new update/boundary probes match. |
| spraedsheet | `c19848d9997fb746a077c336d50b86e739a99483` | Vendor and command/formula integration changes inspected; UI not executed. |
| Spreadsheet's vendored RexxJS | `b3d5e4ef7085180e2a9016ec11fb1eefccb2f5a2` | Same results; all 61 shared core source files match standalone. |
| Installed Aether | `0.829.0` | Forced rebuild, 397 native specs, C/Aether binary consumers, containment and Valgrind pass. |

Seven previously pinned reference snapshots are unchanged. The original
24 migration probes remain in strict parity; the new audit separately measures
28 programs in tests/reference_update_20261019.json. See
[reference-update.md](2026-10-19-reference-audit.md) and the machine-readable audit.
The historical observations below describe 57b97c7, not the new dialect.

## Initial implementation baseline, 2026-10-15

These are the local source revisions inspected for the initial implementation.
References are relative to the workspace containing RexxAE, RexxJS and
spraedsheet. Aether and sae were read from `/home/paul/scm/`.

| Source | Revision | Role |
|---|---|---|
| RexxJS | `57b97c7d8b3079f65c53d0ac6a179fe3760fe27b` | Primary grammar and runtime reference; differential test oracle. |
| spraedsheet | `93a86c1707c420277023ec6b5aa2a19692a2f013` | Real formula and application-control consumers. |
| spraedsheet/vendor/rexxjs/UPSTREAM | `6ec1ab7b9e78a4559a2a4c2f4d6c8de7df2fe3e0` | Older vendored RexxJS dependency closure. |
| sae | `f35d1d5e38b606b4315698f543f4f0b114367802` | Native app embedding, host function registration, command and control-bus examples. |

The vendor tooling mentions optional `patches/*.patch`, but no patches
directory exists in this spreadsheet checkout. Missing files in the vendor
tree mostly reflect its dependency closure, not a competing implementation.

Six files present in both core source trees differ:

| File | Changes in standalone RexxJS |
|---|---|
| `parser.js` | CALL argument expression grouping; concatenation for assignments without LET; LEAVE and ITERATE; DO FOREVER. |
| `interpreter.js` | CALL access to host functions and value resolution; propagation of loop control through IF/SELECT and command execution. |
| `interpreter-control-flow.js` | DO FOREVER and LEAVE/ITERATE handling in loops and conditional branches. |
| `interpreter-parse-subroutine.js` | CALL dispatch to host functions; argument evaluation, including expressions and zero values. |
| `interpreter-expression-value-resolution.js` | Single-pass double-quoted escapes; single-quoted backslashes preserved; required function parameter checks. |
| `interpreter-variable-stack.js` | The same double/single quoted escape distinction. |

Spreadsheet's `rexx/README.md` identifies three earlier fixes already in the
vendor baseline: CLI EXIT status, doubled literal quotes, and SAY expressions
combining blanks with `||`. RexxAE's fixtures cover the latter two and script
exit codes; it does not have a Rexx CLI yet.

RexxJS is a dialect reference, not a promise of classic Rexx conformance.
For example, at this revision variables are case-sensitive, and unset RC
reads as `RC` until assigned. Differential testing caught both assumptions
in the first implementation. Bare SAY takes RexxJS's generic-command path;
RexxAE explicitly rejects it for now. Numeric coercion, spelling, host object
values, functions and error behavior need broader fixtures before parity can
be claimed.

## Spreadsheet has two distinct uses

`spraedsheet/app/sheet/rexx.ts` evaluates cell formulas using an interpreter,
with cell references, setup variables, host functions and values which may
be arrays or objects. This needs expression/function parity, typed host
values and reusable contexts. The engine now supports typed host arguments,
replies and variable access. A generic Python harness exercises this contract;
recreating the spreadsheet is outside the integration test scope.

`spraedsheet/rexx/*.rexx` are external automation scripts. They load
`spreadsheet-address.js`, select `ADDRESS SPREADSHEET`, then send quoted
commands. That library shells to `sae-bus`, which handles discovery and
sealed transport. RexxAE's COMMAND event supplies the corresponding
application dispatch seam. Conditions, SELECT, a subset of functions, loops and labeled CALL/RETURN routines
are implemented; REQUIRE and expectation assertions still prevent
running these complete scripts unchanged.

## Aether facilities reviewed

- `docs/emit-lib.md`: C exports, shared libraries, binary import catalogs,
  object/static output and capability gates. Builds use `--emit=lib` without
  capability grants. Both self-contained and `--shared-runtime` libraries
  are tested through actual Aether binary imports as well as C/ctypes.
- `std.string`, `std.map`, `std.strbuilder`: the initial implementation's
  text, owned context storage and literal construction. `std.json` supplies
  the typed host boundary and internal expression representation; `std.spec`
  supplies native tests. Valgrind covers all eleven native spec executables
  and the C example, including suspended teardown.
- `std.decimal` and `std.bignum`: available numeric machinery if a language
  profile needs exact decimal arithmetic. Default numeric behavior should
  be established against RexxJS before choosing a different representation.
- `contrib.quickjs` and `contrib.host`: useful embedding precedents; neither
  is a runtime dependency of RexxAE. `contrib.parsers` currently contains
  XML/Expat support, not a Rexx grammar to reuse.

`make parity REXXJS=/path/to/checkout` tests the checkout provided by the
caller. It deliberately does not fetch or alter upstream repositories. A
passing run against a newer checkout is evidence for those cases only.

Containment was reviewed again on 2026-10-16 against Aether's
`docs/containment-sandbox.md` and sae's current architecture, page-services,
file service, import-layer checks and guest-global specs. sae's documented
future entry-wide runtime enforcement and OS-process isolation are not treated
as completed features. See containment.md for RexxAE's independent evidence.
