# Reference update audit, 2026-10-16

The native engine has migrated from its original `57b97c7` profile to the
updated standalone dialect. Current reference checkouts:

| Source | Revision |
|---|---|
| Standalone RexxJS | `e3bd4e975e96d674d85be5deb6b76a7c26f0deef` |
| Spreadsheet | `5bc0e29b1b236c8c71b282fda4648d8d9bfa1684` |
| Spreadsheet's vendored RexxJS | `60d6ab0168c2a568333ae88432cef40755ff0d1a` |

The vendor is three commits behind standalone. Its shared core differs only
in parser.js and interpreter-address-handling.js. Those later commits fix
next-clause IF/THEN/ELSE, command concatenation and `|`/`&` conditions. No
reference checkout was modified during this audit.

## Measured compatibility

`make reference-audit` executes all 507 strict-parity programs, and separately
reports the 24 focused migration probes (also included in that suite), against
both checkouts. Exact sources and outputs are in
[reference-audit.json](reference-audit.json). Audit completion only means the
comparison completed; `make parity` is the strict standalone gate and passes.

| Reference | Strict-suite matching | Migration probes matching | Previous reference snapshots unchanged |
|---|---:|---:|---:|
| Standalone e3bd4e9 | 507 / 507 | 24 / 24 | 7 / 7 |
| Vendored 60d6ab0 | 503 / 507 | 20 / 24 | 7 / 7 |

The four vendor differences are split IF instruction/THEN clauses, command
concatenation and logical conditions. Native behavior follows standalone's
later fixes. The five failures found in the initial update audit were resolved
by implementing uppercase unset names and substituted script tails. The Python
harness now uses `parsed_message` as its temporary, avoiding an accidental
`config.message` tail collision; a dedicated fixture still tests that collision.
None of those failures were moved into the known-difference list.

The function registry remains 386 language functions plus 119 converters,
with 42 optional manifests and 82 optional source candidates. RexxAE's reviewed
surface is unchanged at 71 builtins; this migration adds language behavior.

## Delivered migration and limits

| Area | Native behavior |
|---|---|
| Unset symbols | Uppercase derived symbol names; case-sensitive variable storage. |
| Compound tails | Independent, single substitution of each set simple tail; literal host API paths. |
| PROCEDURE/EXPOSE | Isolated script-variable generations, exposed names/roots, restored caller argv. Plain calls still share. |
| Concatenation | Blank concatenation and abuttal in assignment, SAY and parenthesized arguments. |
| Unparenthesized calls | Initial scalar-builtin profile such as `LET x = UPPER s`, respecting exact variable shadowing. Use parentheses for typed/host functions and richer argument forms. |
| Controlled DO completion | A previously unset counter retains the first value past the bound; preexisting values restore. LEAVE retains the current iteration. |
| DO OVER stem / stem. | Arrays and object values; canonical integer keys sorted before other keys. Empty objects error. String/scalar/array-like inputs remain unsupported. |
| Split IF/THEN clauses | THEN and branch instructions may start subsequent clauses. |
| CALL and commands | Audited builtin argument expressions/zero, command concatenation and logical operators match standalone. |

Native specifications cover recursive generations, EXPOSE roots, missing
exposed variables, nested plain calls, argv restoration, errors, EXIT, loop
unwinding, pending destruction and recursion limits. Both actual Aether binary
consumers exercise scoped host suspension and vetoes. Containment probes try
EXPOSE and assignments against names resembling private host registries and
grants; these remain script data with no authority.

Procedure snapshots include only `v:` script variables. Registries, grants,
pending requests, instructions and private metadata never enter a generation.
Script-derived compound names and literal host JSON property access are separate
contracts. A script variable sharing a property name cannot change a host API
path. Copied object values still differ from RexxJS's general alias semantics.

Aether 0.802 requires a fresh enforcement frame per guest event for safe repeated
trusted-service dispatch. The dev-tree compiler is currently mismatched with
its stdlib; details and a standalone reproducer are in
[aether-issues.md](aether-issues.md).

## What the updated spreadsheet actually needs

This is source analysis, not an execution of the spreadsheet's UI or tests.

`app/sheet/rexx.ts` implements a Rexx formula language separately from the
Excel parser. Expressions are wrapped in `LET CELLRESULT = ...`; statement
formulas read RESULT. It retains parsed commands, uses a variableResolver for
cells/named ranges and installs app-owned range/query/style functions. Its
`install` explicitly removes shadowed builtins and converters before mounting
host functions. Named LAMBDA calls use a fresh interpreter, inherit selected
setup variables/functions, and have a recursion limit.

`app/sheet/script.ts` uses separate interpreters for automation. It adds
SETCELL/GETCELL, app control functions, ADDRESS SHEET and ADDRESS SPREADSHEET.
The latter executes Rexx through the app's command/control surface. RUN_PROGRAM
creates a child interpreter with the same intended service functions and
collects SAY/RESULT. Any native equivalent must preserve the original service
profile, cancellation and limits on reentry.

The many new Excel formula functions live largely in the spreadsheet's own
TypeScript modules. They should not automatically become RexxAE core builtins.
RangeQuery class instances and dynamic function/variable proxies also need an
explicit native representation; JSON values alone do not reproduce arbitrary
JavaScript objects or method calls.

## Suggestions for broader embedding

1. **Separate compilation from execution.** An immutable reusable program or
   expression handle, with a fresh context per evaluation, supports cell
   recalculation, templates, rules and command workflows without reparsing.
   Share compiled code across contexts; keep variables and services isolated.
2. **Make host binding profiles explicit.** A formula profile exposes reads
   and pure computations; an automation profile mounts selected mutations and
   ADDRESS environments. Applications choose both. Registration remains
   host-only, and denied operations should return structured refusal reasons.
3. **Add resumable variable lookup and discoverable function metadata.** A
   LOOKUP-style event can resolve cells, document properties or application
   state without arbitrary callbacks across the ABI. Namespaces and declared
   arity/types/effects help completion and validation. Any host override of a
   builtin should be explicit, per-context and disabled by default.
4. **Carry structured diagnostics and execution limits through every entry.**
   Stable error categories, source spans, cancellation and source/heap/response
   limits help editors, servers and desktop apps. Nested programs and delayed
   host replies must retain the same authority and limits.
5. **Keep application algorithms in optional libraries/adapters.** Spreadsheet
   ranges, drawing objects or business services can use typed descriptors or
   context-bound opaque tokens. Never expose raw pointers or inherit ambient
   host authority to simulate a JavaScript class instance.

These suggestions generalize the spreadsheet's two roles without requiring
RexxAE to implement a spreadsheet. They preserve the containment contract and
both C and Aether library consumers.
