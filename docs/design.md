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
| src/builtins.ae | Scalar functions and converter profiles. |
| src/engine.ae | Program counter, loop/call frames, lifecycle and embedding API. |
| src/state.ae | Owned context storage, serialization and diagnostics. |
| src/variables.ae | Script tail substitution, literal host paths and owned object-path replacement. |
| src/scopes.ae | PROCEDURE variable generations and EXPOSE sharing. |
| src/templates.ae | PARSE word/delimiter cursor rules and input conversion. |

The complete program parses before execution. Instructions have source lines;
expression nodes have stable IDs. Branches/jumps use an explicit program
counter. DO headers/tails and stacked loop frames retain range/count state
and restore preexisting loop variables, including on early termination.
SELECT uses the same branch/jump instructions: false conditions advance to
the next WHEN, a matched body jumps past the selection, and fallback jumps
link OTHERWISE bodies in source order. Expression caching preserves partial
host conditions; RETURN/EXIT/LEAVE/ITERATE use the same call and loop machinery.

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
for the current generation too. Explicit RETURN sets RESULT when the caller resumes; bare RETURN yields an empty string.
An implicit return uses the global return value captured at call entry (null
if none). Top-level RETURN stops execution with exit code zero. See
[routines.md](routines.md) for syntax and reference parser restrictions.

PARSE expression input also uses the instruction cache: no template variable
binds until the complete input resolves. Compound writes rebuild owned
containers and commit the new root only after success. Variables have value
ownership rather than RexxJS object aliases.

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

`build/librexxae.so` is self-contained for C/ctypes. The same source compiled
with `--shared-runtime` produces `build/aether/librexxae.so`, allowing an Aether
host to share one runtime with other libraries. Both are capability-empty.

Aether hosts use `import rexxae`. The compiler reads the binary catalog,
synthesizes declarations and links the artifact. Internal root helpers have
private suffixes to exclude them from that catalog.
[test_binary_import.ae](../tests/test_binary_import.ae) tests both variants
without an engine source import.

The pointer/string/scalar public surface avoids a cross-library closure ABI.
Applications handle callbacks through events from C, Python or Aether.

## Sessions and imported code

`rexxae_create_next` accepts terminal contexts and copies script values, mounted
function registrations and ADDRESS selection. Each submission has fresh
instructions and caches. Code definitions, argv, pending requests and private
call state do not carry forward. Contexts are independently owned; a host can
discard an interrupted candidate and retain the previous state. See
[REPL sessions](repl.md) for error and cancellation behavior.

REQUIRE emits a function request to an explicitly mounted application resolver.
It grants no filesystem or network authority. The
[calculator resolver](calculator.md#importing-the-calculator-api) downloads one
separately approved Rexx module and executes its CALC export in a child context
with only an endpoint-bound HTTP_POST function. General module discovery and
resolution remain application responsibilities.

## Authority and remaining work

The core library opens no listeners, files or OS commands. Applications own
effects, credentials, transport and scheduling. Public engine entry points are
`@pure`; import and builtin snapshots pin the engine boundary. Aether services
retain narrow runtime fences beneath argument validation. See the
[containment contract](containment.md) for enforcement and practical limits.

Current language limits are listed in [README coverage](../README.md#coverage-and-limits);
[compatibility gaps](reference-update.md) describe unresolved reference behavior.
Recognized named scalar arguments and PROCEDURE/EXPOSE are implemented.

Embedding work still includes reusable compiled programs, application variable
lookup, discoverable function metadata, structured diagnostics, cancellation
and complete resource quotas. ABI versioning, static/object packaging,
cross-platform validation and concurrency guarantees are also open. Application
algorithms and effect adapters should remain separately selectable.
