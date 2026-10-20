> Archived investigation, captured before the documentation cleanup on 2026-10-20.
> Versions, test totals and implementation status below describe that snapshot;
> use the [current documentation](../../README.md) for supported behavior.

# Reference update audit, 2026-10-19

This is a measured assessment of the new references, not an implementation of
all newly audited syntax. No engine semantics changed during this audit.
The four Aether discussion issues are outside this work.

| Source | Revision |
|---|---|
| Standalone RexxJS | `8317bd1c2adeb966ea0eb9a91331f80c45bb79a1` |
| Spreadsheet | `c19848d9997fb746a077c336d50b86e739a99483` |
| Spreadsheet's vendored RexxJS | `b3d5e4ef7085180e2a9016ec11fb1eefccb2f5a2` |
| Installed Aether | `0.829.0` |

All 61 shared core source files in the standalone and vendor checkouts are
identical. The standalone commits beyond the vendor change a VLOOKUP test,
comments and contributor instructions, not the core interpreter. Reference
checkouts were left unchanged.

## What changed since e3bd4e9

- `3288853`: ordinary CALL arguments now use expression parsing, including
  concatenation and function calls combined with arithmetic.
- `c0004b4`: doubled quotes in a combined ADDRESS literal are decoded once.
- `b3d5e4e`: combined ADDRESS accepts a variable or supported concatenation
  as the command clause, leaving the environment selected afterward.
- The remaining commits adjust contributor instructions and the Excel
  VLOOKUP test's JSON literal spelling. The extras lockfile also changed.

The registry is unchanged: 386 language functions plus 119 converters,
42 optional manifests and 82 optional source candidates. Regenerating the
inventory changes only its reference revision. No additional npm-dependent
function needs disposition because of these commits.

## Measured results

A forced rebuild with `/home/paul/.aether/bin/ae` (0.829.0) passes all 397
native std.spec cases, C/Python hosts, both Aether binary consumers, containment
checks and Valgrind. The development-tree executable still reports 0.820.0,
so it was not used. The sandbox lifetime reproducer still passes on 0.829.

| Reference | Existing strict suite | New update/boundary probes | Previous reference snapshots unchanged |
|---|---:|---:|---:|
| Standalone 8317bd1 | 507 / 507 | 16 / 28 | 7 / 7 |
| Vendored b3d5e4e | 507 / 507 | 16 / 28 | 7 / 7 |

`make parity` remains a strict passing gate for the existing 507 programs.
`make reference-audit` additionally evaluates
[reference_update_20261019.json](../../tests/reference_update_20261019.json),
including unsupported boundary cases. Audit completion is not a parity pass;
the 12 nonmatching probes were not moved into accepted differences or silently
counted as covered. Exact results are in [reference-audit.json](../reference-audit.json).
The original 24 migration probes remain in the existing strict suite.

| Probe group | Matching | Meaning |
|---|---:|---|
| Ordinary CALL expressions from the new upstream specs | 9 / 9 | Native evaluation already agrees, including first/later arguments, arithmetic, functions, blank concatenation and abuttal. |
| Quoted ADDRESS, doubled quotes, literal-led concatenation, environment-only form | 7 / 7 | Already compatible. |
| Variable-led ADDRESS and result/environment behavior | 0 / 6 | Clear native parser gap; first implementation priority. |
| Assigned CALL expression boundaries | 0 / 5 | Native rejects these; reference behavior is surprising and needs a semantics decision. |
| Parenthesized ADDRESS boundary | 0 / 1 | Native errors; reference silently ignores it. No general expression support can be inferred. |

## Next native change: variable-led ADDRESS

These now work in both reference engines and are rejected by the native
parser before execution:

```rexx
LET cmd = 'cell.get A1'
ADDRESS REC cmd

LET prefix = 'get '
LET ref = 'B2'
ADDRESS REC prefix || ref

LET command.text = 'cell.get A1'
ADDRESS REC command.text
```

The other focused gaps test an empty command variable, RC/RESULT after the
host reply, and the selected environment remaining in force for the next
quoted command. All six share the same missing clause-entry path:
`src/program.ae` only consumes a combined ADDRESS clause when its first token
is a quoted literal. The evaluator and existing host-request protocol already
provide the required mechanisms; no new Aether runtime feature is needed.

Implementation sequence:

1. Lower supported variable-led ADDRESS clauses to the existing command
   expression instruction; retain environment-only ADDRESS behavior.
2. Add the six cases to native std.spec and strict differential fixtures,
   plus both binary consumers and host-veto containment coverage. Exercise
   budgeted stepping, environment persistence and reply variables; no implicit
   shell execution or additional authority.
3. Promote the 16 newly characterized matching programs into the strict/native
   fixtures, rather than relying on an audit-only report for lasting coverage.
4. Resolve assigned CALL semantics before extending that parser path.

## Assigned CALL is not settled by the new commit

The commit description mentions ordinary CALL and `LET v = CALL`, but the
new upstream tests cover ordinary CALL. In direct execution, assigned CALL
still behaves differently. For example:

```rexx
LET result = CALL pair 'a', 'b'
SAY result.returnValue
EXIT
pair: PROCEDURE
ARG p,q
RETURN p || q
```

The intuitive ordinary-CALL equivalent returns `ab`; current RexxJS returns
`'a',b`. A nested-call case returns `('Q')2`, and arithmetic arguments produce
`5-` in the corresponding probe. RexxAE currently gives its explicit
"assigned CALL currently requires simple blank-separated arguments" error.
These observed reference outputs are recorded with notes in the audit, not
recommended as semantics to reproduce without discussion. A fix or an explicit
compatibility choice in RexxJS should precede treating this as a native port
requirement. Parenthesized ADDRESS is likewise an unresolved boundary rather
than a feature to implement by copying a silent no-op.

## Spreadsheet observations relevant to this update

The updated CLI's `sheet run` sends command lines as JSON through RUNCOMMAND.
The ADDRESS commits were motivated by this integration. Supporting the same
command-expression boundary in RexxAE is broadly useful without recreating
the spreadsheet or its command transport.

The inspected changes to `app/sheet/rexx.ts` only extend SPARKLINE_RANGE's type
and options arguments; that remains an application function, not a RexxAE
core builtin requirement. Spreadsheet UI/CLI tests were not run in this audit.

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
