# Engine and host design

RexxAE is an Aether interpreter library with a C ABI and Aether binary
imports. Other languages call the same engine. RexxJS supplies compatibility
fixtures instead of an embedded JavaScript runtime.

## Current implementation

| Module | Responsibility |
|---|---|
| src/lex.ae | Tokens, comments, clauses and source lines. |
| src/program.ae | Expression trees and flat control-flow instructions. |
| src/values.ae | Owned tagged values, containers and JSON boundary conversion. |
| src/evaluate.ae | Typed evaluation, builtin dispatch, lazy IF, ARG and host/routine requests. |
| src/builtins.ae | Initial scalar functions and converter profiles. |
| src/engine.ae | Program counter, loop/call frames, lifecycle and embedding API. |
| src/state.ae | Owned context storage, serialization and diagnostics. |
| src/variables.ae | Literal dotted lookup and owned object-path replacement. |
| src/templates.ae | PARSE word/delimiter cursor rules and input conversion. |

The complete program parses before execution. Instructions have source lines;
expression nodes have stable IDs. Branches/jumps use an explicit program
counter. DO headers/tails and stacked loop frames retain range/count state
and restore preexisting loop variables, including on early termination.
SELECT uses the same branch/jump instructions: false conditions advance to
the next WHEN, a matched body jumps past the selection, and fallback jumps
link OTHERWISE bodies in source order. No additional runtime frame or public
API is needed. Existing expression caching preserves partial host conditions;
RETURN/EXIT/LEAVE/ITERATE use the existing call and loop machinery.

Values are tagged JSON trees internally. Numeric text payloads retain
NaN/Infinity independently of strings. Containers own tagged children.
Variables, instructions and frames are stored as owned serialized strings;
replacement frees obsolete storage instead of accumulating JSON arena
replacements for the life of a context.

The expression cache belongs to one instruction. Evaluated nodes, including
host replies, are copied into it. Resuming a later suspended call reads
earlier results from that cache, so host effects occur once. It clears when
the instruction completes; a loop then evaluates its body afresh. No foreign
or recursive interpreter stack survives a yield.

Labeled CALL instructions resolve arguments through the same evaluator. An
internal request pushes a bounded call frame (return PC, loop-stack base,
result node and implicit-return default), saves the caller's expression cache
and starts a fresh cache. RETURN unwinds only the callee's loops, restores
the caller's cache and memoizes the result at the suspended CALL node. This
also isolates recursive invocations that execute identical AST node IDs.
Internal transitions consume instruction budget and never become public host
events. The call-depth limit is 128; teardown frees every saved cache.

Plain routines share variables and argv. PROCEDURE creates a fresh generation
of only v: script entries; EXPOSE shares selected roots/names. Its frame saves
caller variables and argv. Return, EXIT and errors unwind each generation's
loops before restoring its caller. Host registries, permission data and program
instructions never enter these snapshots. A plain nested CALL changes argv
for the current generation too. Explicit RETURN
sets RESULT when the caller resumes; bare RETURN yields an empty string.
An implicit return uses the global return value captured at call entry (null
if none). Top-level RETURN stops execution with exit code zero. See
routines.md for the tested forms and reference parser restrictions.

Serialization and copying favor straightforward ownership, not performance.
An optimized value arena/IR can replace them behind the opaque context after
measurement and equivalence tests.

## Host protocol

```text
create/parse -> RUNNABLE -> step -> SAY -> step ...
                             -> COMMAND -> reply -> RUNNABLE
                             -> FUNCTION -> reply_value -> RUNNABLE
                             -> DONE or ERROR -> destroy
```

The host registers function names/arity ranges and handles typed positional
arguments. Replies are JSON values or application errors. Invalid JSON does
not consume a pending request. Registry/variable mutation is rejected while
waiting. A host may destroy a pending context. ADDRESS retains its separate
text/RC/RESULT/ERRORTEXT protocol.

Instruction budgets yield during loops, including FOREVER. They do not bound
expression internals, parsing, memory or time. Runtime failures do not undo
application work already performed.

## Both library consumers

build/librexxae.so is self-contained for C/ctypes. The same source compiled
with --shared-runtime produces build/aether/librexxae.so, allowing an Aether
host to share one runtime with other libraries. Both are capability-empty.

Aether hosts use import rexxae. The compiler reads the binary catalog,
synthesizes declarations and links the artifact. Internal root helpers have
private suffixes to exclude them from that catalog. test_binary_import.ae
runs against both variants, covering typed values, commands/functions, error
locations, nested/recursive routines and pending teardown without importing engine source. Source-import
specs are complementary, not proof of binary linkage.

The pointer/string/scalar public surface avoids a cross-library closure ABI.
Applications handle callbacks through events from C, Python or Aether.

## Integration and remaining work

Sae owns its contexts, registers a specific API and implements authorized
effects in services. RexxAE uses the same explicit-host model. Discovery,
credentials, sealed transport and UI scheduling belong to host adapters.
The library opens no listeners or OS commands by itself.

A small Python harness proves these contracts; neither sae nor the
spreadsheet was changed or recreated.

Next work: expand typed builtins and resolve documented parser differences;
add full JSON paths, named arguments, Unicode and numeric formatting;
implement positional PARSE, classic stem semantics if selected, language errors, INTERPRET
and modules while preserving resumability. PROCEDURE/EXPOSE now follows the
8317bd1 reference; plain routines retain shared variables. See reference-update.md
for measured compatibility and embedding requirements. Reusable compiled programs,
application variable lookup, ABI versioning, static/object packaging,
cross-platform CI, resource accounting and concurrency remain to establish.

Judge compatibility using the actual reference runtime and differential
fixtures. Keep differences visible in documentation and tests.

PARSE expression input uses the existing instruction cache; no variables bind
until the complete input has resolved. Template tokens compile before effects.
Compound writes rebuild independent containers and commit the new root only
after success. This avoids mutating parsed JSON interiors on older runtimes;
variables have value ownership rather than RexxJS object aliases.

Containment is tested through the compiled artifacts, with the host retaining
fs/net/os authority and injecting only checked service calls. All 18 engine
entry points are @pure. Import and guest-function snapshots hold the layer
boundary; explicit service fences and std.sandbox audit assertions hold runtime
authority. See containment.md for the sae precedents, compiler findings and
what remains outside in-process protection.


Host console sessions use rexxae_create_next on terminal contexts. Only script
values, existing mounted-function registrations and ADDRESS selection carry
forward. New instructions and caches prevent replay; code definitions, argv,
pending requests and private call state never cross an entry boundary. The
previous context is independently owned so a host can discard an interrupted
candidate without rerunning it. See repl.md for the public contract and limits.
