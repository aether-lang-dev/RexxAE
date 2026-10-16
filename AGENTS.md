# Working on RexxAE

RexxAE is a C-linkable Rexx engine written in Aether, maintained by Paul and
Nic. The engine must run in native, OS-installable applications without a
JavaScript runtime. C examples and ABI tests are appropriate; implement the
language and builtins in `.ae` files.

## References and scope

- `../RexxJS/core/src/` is the primary dialect reference. Read actual
  registration, argument conversion and runtime behavior as well as docs.
  Metadata can be stale and converter helpers are not language functions.
- `../spraedsheet/` supplies formula and automation integration cases.
- `/home/paul/scm/sae/` supplies embedding, explicit host APIs and control-bus
  examples. The host owns effects and transport.
- `/home/paul/scm/aether/` contains the compiler, `std/` and `contrib/`.
  Prefer these facilities to new C code or an npm dependency. The dev-tree
  `build/ae` may be newer than the installed `ae`.
- Keep reference checkouts unchanged unless the user asks otherwise.
- Preserve RexxJS compatibility where tested. Record unsupported features,
  semantic restrictions and proposed omissions explicitly. npm dependence
  alone does not decide whether a feature belongs in RexxAE.

## Tests are part of the implementation

We love tests. Use **Aether's `std.spec`** for native unit and execution
specifications. Keep them under `tests/test_*.ae`, runnable with `ae test`
or directly with `ae run`. Test observable behavior and important edge cases,
including invalid arguments, nesting, ownership and suspension/resumption.

Retain the other complementary layers:

- Python/ctypes tests exercise the public C ABI and independent contexts.
- Differential fixtures execute identical source on RexxAE and RexxJS and
  compare output, ADDRESS requests and exit status. A passing direct builtin
  test alone is not evidence of parser or function-call compatibility.
- Native C examples prove linking and application dispatch. Use Valgrind or
  an equivalent memory checker when allocation/lifetime paths change.
- Both **C and Aether binary consumers** are required. `tests/test_binary_import.ae`
  imports the compiled library with `import rexxae`, without an engine source
  import. Test self-contained and shared-runtime variants (`make binary-test`).
  Source-import specs do not substitute for this. Direct invocations need
  `--lib build` or `--lib build/aether`.
- Keep known compatibility differences in `tests/known_differences.json`, asserting
  both native and reference results. Do not count these cases as parity.

Run the relevant specs while developing and `make test parity` before
finishing a change. Use `make test parity AE=/home/paul/scm/aether/build/ae`
to verify against the development compiler. Do not hide failing fixtures,
silently skip available tests, or describe untested functionality as parity.
Do not run builds and tests against a compiler being rebuilt concurrently.

## Engine boundaries

Keep the library build capability-empty (`--emit=lib`, no grants) unless an
explicitly separate host adapter requires effects. Scripts reach application
commands through the embedding API. Future native functions, modules and
typed values must preserve explicit host authority.

RexxJS e3bd4e9 is the target. PROCEDURE/EXPOSE isolates script variables and
restores argv for PROCEDURE calls; plain calls still share. Never snapshot or
restore host registries, grants, program instructions or other private state
as procedure variables. Exercise CALL
frames with recursion, loop unwinding, suspended host requests and both binary
library variants whenever changing execution/cache ownership.

The ABI is currently experimental. Document changes in `include/rexxae.h`
and README. Inputs are copied; output payloads are borrowed. Context teardown
must free owned resources, including on errors and pending host operations.
Unsupported syntax or unavailable functions should produce useful errors.

Keep source analysis and the function disposition inventory reproducible.
Distinguish implemented, planned native, host-provided, optional and omitted
features. User decisions override provisional recommendations.

Use a small host harness to prove embedding contracts. Python/ctypes is a
valid host; recreating the spreadsheet is unnecessary. Existing applications
are integration references, not required implementation work.

## Containment is a required contract

Read `/home/paul/scm/aether/docs/containment-sandbox.md`; sae's
`docs/architecture.md`, `docs/page-services.md`, `services/files/module.ae`,
`tests/check_layers.sh` and `tests/spec_globals.ae` are embedding references.
Keep all public engine entry points @pure. Engine stdlib imports and the guest
builtin surface are deliberately pinned by `tools/check_containment.py` and
`tests/guest_functions.json`; widening them is an explicit capability review.
Do not rely on --emit=lib alone: the inspected compilers permit std.file
without an fs grant, while @pure rejects calls into it, including transitively.

Run `make containment` for both actual binary-library variants and compiler
rejection probes. Guest services must be absent unless mounted, validate
argument types/resources, and fail closed. ADDRESS is a request, never an
implicit shell. Aether service adapters should retain a service-specific
sandbox fence beneath their own validation; a trusted service cannot widen
an outer container's grants. Keep deny-all, nested grants, frozen grants,
registry isolation, dynamic-name/typed-argument spoofing and suspension tests.
Add a regression probe whenever introducing an effect-capable builtin or
adapter. Do not claim in-process containment covers native memory corruption,
complete resource quotas, or an end-to-end network path that was not tested.

Future INTERPRET, module loading and script callbacks must retain the original
context's mounted services and containment on every entry and resume. Never
inherit ambient host authority or run generated native/JS code to implement
those language features. Keep sae's completed boundaries distinct from its
roadmap when citing it as a precedent.

## Updated reference audit

RexxJS e3bd4e9 is the current target; spreadsheet 5bc0e29 vendors 60d6ab0,
three commits behind. docs/reference-update.md and docs/reference-audit.json
record the measured migration and vendor differences. `make reference-audit`
characterizes both pins; it is not a compatibility pass. `make parity` stays
strict. Keep script-derived tail substitution distinct from literal host
JSON/property access. Do not move migration failures into known differences
or weaken containment to make a newer reference appear compatible.

Current toolchain issues and a standalone trusted-service reproducer are in
docs/aether-issues.md. Record failures honestly; do not modify read-only
reference/toolchain checkouts to hide them.
