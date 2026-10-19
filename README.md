# RexxAE

An embeddable Rexx engine written in Aether, consumable as a **C library and
an Aether binary library**. RexxJS is the dialect reference; spreadsheet and
sae supply integration examples. The default library has no fs/net/os/extern
capability grants. Applications supply effects through explicit host requests;
there is no JavaScript runtime dependency.

This is a working implementation slice, not a complete port. It has typed
values, 71 builtins with limited profiles, registered application functions, labeled routines with CALL/RETURN,
comparisons, IF/ELSE, SELECT and DO loops that suspend and resume across host calls.

Current references are RexxJS `8317bd1` and spreadsheet `c19848d`
(vendoring `b3d5e4e`). All **507 existing differential programs** still match
both reference engines. A separate 28-program update audit matches 16 and
identifies variable-led ADDRESS clauses as the next native change; assigned
CALL expressions also need a reference-semantics decision. The audit includes
unsupported/boundary cases and is not counted as passing parity. See
[the reference report](docs/reference-update.md) for the concrete gaps.

## Build and test

Targets Aether **0.829.0**; requires a C compiler and make. Tests require Python 3; differential
tests and inventory generation also need Node.js and a RexxJS checkout.
No npm install is required.

```sh
make                            # self-contained library and C counter host
make aether-lib                 # shared-runtime variant for Aether consumers
make test                       # std.spec, binary linkage, ctypes, host harness
make repl                       # console session; = expression, :help, :begin / :run
make parity REXXJS=../RexxJS     # strict comparison with the selected checkout
make reference-audit             # characterize standalone and vendored targets
make binary-test                # both Aether binary-library variants
make containment                # runtime escape probes and compiler guards
make memcheck                   # requires Valgrind
make inventory check-inventory  # function/dependency analysis
```

Use `AE=/home/paul/.aether/bin/ae` to select the installed 0.829.0 compiler.
Check `ae --version` before testing; the development-tree executable may be
older than the installed release. Use `make -B` when switching compilers to
rebuild libraries and consumers together. Make keeps its Aether cache under
`build/cache`.

Linux validation targets installed Aether 0.829.0: 405 native specs, 507 RexxJS
comparisons, both binary-library variants, containment probes and Valgrind.
The previous compiler/stdlib annotation blocker is resolved. The repeated
trusted-service lifetime reproducer now passes, with three automated regression
specs protecting repeated calls and enclosing restrictions. See
[Aether findings](docs/aether-issues.md).
The Makefile has a macOS library/rpath branch; macOS and Windows remain
untested. Static/object packaging is a follow-up.

## Console REPL

`make repl` starts a Python console around the native Aether engine. Variables
persist without replaying earlier entries:

```text
rexx> LET total = 10
rexx> = total * 2
20
rexx> :show total
10
```

Use `:begin` / `:run` for multiline Rexx, `:reset` to clear session state and
`:quit` to exit. The default console mounts no effect services and vetoes
application commands. [repl.md](docs/repl.md) describes ownership, error recovery,
cancellation and session behavior.

## TinyWeb calculator demo

The optional [calculator demo](docs/calculator.md) adds a native Aether console,
an exactly approved `CALC` host function, and a TinyWeb HTTPS endpoint using
pure-Aether TLS 1.3. It needs the development stdlib containing Aether commit
`7b48889a` (the development compiler reports 0.830.0).

The [calculator script](examples/calculator/calculator.rexx) explicitly imports
its API before calling it:

```rexx
REQUIRE "calculator"
SAY CALC('add', '0.1', '0.2')
```

`REQUIRE "calculator" AS remote` instead exports `remote_CALC`, matching
RexxJS's prefix semantics. Permission approval and module import are separate.
See [importing the calculator API](docs/calculator.md#importing-the-calculator-api)
for alias rules and the remaining work on relative HTTP module loading.

### Local integration checks

```sh
make calculator-test CALC_AE=/home/paul/scm/aether/build/ae
python3 tools/test_calculator_tls.py --ae /home/paul/scm/aether/build/ae
```

The terminal runner writes `build/calculator/tls-report.json` and logs. Offline
specs cover protocol validation, endpoint policy, enclosing sandbox restrictions,
native EOF/session behavior and TLS keypair validation. Live TLS checks require
socket permission; this workspace cannot perform them. Deployment templates
under `deploy/calculator` are not installed or provisioned automatically.

For local testing without SSL, start the Aether server in one terminal:

```sh
make calculator CALC_AE=/home/paul/scm/aether/build/ae
CALC_HTTP=1 ./build/calculator/calculator-service
```

In a second terminal, run the native REPL and the local test script:

```sh
CALC_ENDPOINT=http://localhost:8080/calculate \
CALC_PROGRAM=examples/calculator/calculator-local.rexx ./build/calculator/calculator-console
```

The native console first asks for session approval of the exact HTTP endpoint.
After an explicit `y` or `yes`, the script prints `0.3`; then try
`SAY CALC('mul', '6', '7')`. No certificates,
CA file or Python are needed. Plain HTTP is restricted to `localhost` and
`127.0.0.1`; HTTPS remains required for remote endpoints.

### Always-on GCP calculator through the native REPL

**Public GCP URL: to be announced.** In this mode the TinyWeb calculator runs
continuously on a GCP VM. Your local Aether console runs the test Rexx script
and sends `CALC` requests to that service. The client path uses the compiled
RexxAE library and Aether TLS 1.3. It requires no Python or local server.

Once the URL is announced, replace `calculator.example.com:8443` below with
its hostname and explicit port. The CA file shown is the usual Debian/Ubuntu
trust bundle; use an absolute path to the appropriate CA bundle on your OS.

```sh
make build/calculator/calculator-console CALC_AE=/home/paul/scm/aether/build/ae
calc_endpoint='https://calculator.example.com:8443/calculate'

# Give the test script the exact endpoint the host will approve.
printf '/* @seeks http.post %s */\n' "$calc_endpoint" > build/calculator/gcp-calculator.rexx
tail -n +2 examples/calculator/calculator.rexx >> build/calculator/gcp-calculator.rexx

CALC_ENDPOINT="$calc_endpoint" \
CALC_CA=/etc/ssl/certs/ca-certificates.crt \
CALC_PROGRAM=build/calculator/gcp-calculator.rexx ./build/calculator/calculator-console
```

The script requests HTTP access in its first-line declaration. The host checks
that declaration against `CALC_ENDPOINT` and asks for session approval before
execution. The prompt labels the script's purpose as **self-claimed** and
**unverified**; trust in a parent domain or sibling subdomain is never inherited.
After an explicit `y` or `yes`, `REQUIRE "calculator"` loads `CALC` for that exact endpoint.
The startup calculation should print `0.3`. The native REPL
then waits for input; try:

```text
SAY CALC('mul', '6', '7')
42
LET fraction = CALC('div', '1', '8')
SAY fraction
0.125
:quit
```

Each `CALC` call reaches the GCP service. Variables remain local to the Rexx
session. See [GCP client and service setup](docs/calculator.md#always-on-gcp-service-and-native-repl)
for the deployment model and endpoint configuration.

Enter, denial or EOF prevents the script from running. Piped input cannot
approve requests; automation must explicitly set `CALC_APPROVE_ENDPOINT` to
exactly `CALC_ENDPOINT`. See [permission approval](docs/calculator.md#permission-approval-in-the-native-repl)
for the prompt and the host policy contract.

## Embed through the C interface

Include [rexxae.h](include/rexxae.h) and link `librexxae`.
[examples/counter.c](examples/counter.c) demonstrates ADDRESS commands.
[examples/host.py](examples/host.py) is a Python/ctypes host harness running
[host.rexx](examples/host.rexx):

```sh
python3 examples/host.py build/librexxae.so
```

It registers three functions, passes arrays/objects, accepts typed replies,
executes nested CALL/RETURN and SELECT/DO and asserts the resulting host-call sequence. It does not
replicate a spreadsheet.

Create a context, register function names and arities, optionally seed typed
variables, then call `aether_rexxae_step(ctx, instruction_budget)`:

| Status | Host action |
|---|---|
| `REXXAE_SAY` | Read text, display/capture it, then step again. |
| `REXXAE_COMMAND` | Read address/text; reply with RC, RESULT and ERRORTEXT. |
| `REXXAE_FUNCTION` | Read function name/JSON arguments; reply with JSON or an error. |
| `REXXAE_RUNNABLE` | The instruction budget was used; schedule another step. |
| `REXXAE_DONE` | Read the exit code, then destroy the context. |
| `REXXAE_ERROR` | Read the error and source line, then destroy the context. |

Use `aether_rexxae_register_function`, `aether_rexxae_function`,
`aether_rexxae_arguments_json` and `aether_rexxae_reply_value` for application
functions. Names are case-insensitive; implemented builtins cannot be replaced.
Host functions currently take positional arguments.

Typed arguments/replies use JSON numbers, strings, booleans, null, arrays and
objects. Variable getters/setters use the same representation. Convenience
argument getters expose JSON type codes and Rexx display text. JSON excludes
nonfinite numbers: those remain internal numeric values and cannot be
exported as typed host arguments.

Pending events repeat until answered. Expression results are memoized until
an instruction completes, so resumption does not repeat an earlier host
effect. Malformed JSON replies leave the call pending for correction; an
accepted application error terminates the script. Registry/variable mutation
is rejected while a request is pending.

Inputs are copied. Getter payloads are borrowed; copy them before retaining
across another context call. A context belongs to one host thread; concurrent
use is not established. Destruction releases pending expressions and loop
state. This ABI is experimental.

## Link from Aether

An Aether application imports the compiled library through its catalog:

```aether
import std.string
import rexxae

main() {
    ctx = rexxae.rexxae_create("LET n = 6 * 7\nSAY n")
    defer rexxae.rexxae_destroy(ctx)
    status = rexxae.rexxae_step(ctx, 100)
    if status == 1 {
        println(string.copy(rexxae.rexxae_text(ctx)))
    }
}
```

After `make aether-lib`, compile with:

```sh
ae build consumer.ae --lib /path/to/RexxAE/build/aether -o consumer
```

`build/aether/librexxae.so` uses `--shared-runtime`, allowing an Aether host
and its libraries to share one runtime. The self-contained `build/librexxae.so`
can also be imported; it is the default C/ctypes artifact. Both use the same
engine and API. Aether's importer supplies native link/rpath wiring.

[test_binary_import.ae](tests/test_binary_import.ae) tests both variants using
`import rexxae`, with no engine source import. Source-import std.spec tests
are a separate layer.

## Coverage and limits

Supported now:

- Assignments, arithmetic, signs, parentheses and concatenation.
- Script-derived compound tails, nested property assignment, uppercase unset
  symbols, zero-based array reads and literal host property access.
- PARSE VAR word/literal-delimiter templates and explicit PARSE VALUE
  expressions WITH templates, including suspended host input.
- Typed numbers, strings, booleans, arrays, objects and JSON/host nulls.
- 60 scalar functions plus JSON_PARSE, JSON_STRINGIFY, JSON_GET, JSON_KEYS,
  ARRAY_GET, ARRAY_LENGTH, ARRAY_PUSH, JOIN, TYPEOF, lazy IF and ARG.
- Positional/nested calls and recognized named scalar arguments.
- Labeled routines with optional PROCEDURE/EXPOSE, CALL (including dynamic targets), RETURN,
  RESULT, ARG() and simple ARG/PARSE ARG argument binding. Routine calls
  preserve pending expressions across host requests and cooperative yields.
- Comparisons, IF/THEN/ELSE, conditional DO blocks, and SELECT/WHEN/OTHERWISE
  with nested branches and first-match execution.
- DO ranges/BY, repeat, WHILE, UNTIL, FOREVER and array/object OVER;
  innermost LEAVE/ITERATE, with existing loop variables restored as in RexxJS.
- SAY, ADDRESS/quoted commands, integer EXIT, clause separators, comments,
  CRLF and doubled quotes. Keywords/functions ignore case; variables retain it.

Still needed: positional PARSE templates, classic stem defaults, interpolation,
double-quoted escapes, INTERPRET, language error handlers, modules and many
remaining functions. Missing symbols return their derived uppercase names;
ARRAY_GET/JSON_GET missing properties still error rather than returning JS
undefined. Nested writes through arrays are diagnosed as unsupported. JSON_GET supports direct object keys, not full paths.
Named typed/host arguments are incomplete. Text functions remain ASCII-only
except UTF-16-aware LENGTH; numeric coercion/formatting has tested profiles,
not full JS equivalence.

Bare `null` resolves to the unset symbol `NULL`; typed null comes
from JSON_PARSE or a host. Seven compatibility differences are pinned in
[known_differences.json](tests/known_differences.json), not counted as parity.
For shared syntax, assign composite values to variables before function
calls and use double-quoted JSON object keys. Copy RESULT into another variable before
RETURN; the reference parses RETURN RESULT as a function call. Assign compound
function arithmetic before WHEN for shared condition syntax. See
[routines.md](docs/routines.md) for CALL forms, PROCEDURE scopes and
argument-list behavior. [select.md](docs/select.md) explains SELECT forms,
including the reference's THEN DO marker and closing END behavior.
[parse-and-compounds.md](docs/parse-and-compounds.md) records PARSE input
quirks, explicit WITH behavior and owned values versus reference aliases.

The complete program parses before execution, so syntax errors precede host
dispatch. Runtime failures do not roll back earlier application effects.
Budgets count instructions, including control flow, not elapsed time or
memory; initial parsing is not budgeted.

Containment is an explicit host/guest service boundary. Engine entry points
are @pure, its reviewed imports contain no fs/net/os module, and no Rexx
syntax reaches native symbols. Hosts mount selected functions, validate typed
arguments and veto unmounted ADDRESS environments. The Aether host example
combines seal except, sandbox.enforce, trusted service injection and a
service-specific file grant. Its escape probes run against both compiled
library variants. See [containment.md](docs/containment.md), including the
observed std.file library-gate gap and the distinction between this boundary
and OS containment of a memory-safety failure.

## Verification and references

`make test` runs 405 native std.spec cases (including both binary variants),
ctypes protocol checks, twelve Python session/console tests, the C example
and Python host harness. `make parity`
compares 507 programs, including host-call arguments/results, with RexxJS
`8317bd1` and the spreadsheet vendor. All pass. Seven documented compatibility differences remain
separately asserted, and are not counted as parity. The same 125
function fixtures run natively, through ctypes and on RexxJS. Valgrind covers
the C example and all thirteen native spec executables. Eleven compiler
rejection probes and the pinned guest/import surfaces protect the containment
contract.

See [design.md](docs/design.md), [compatibility-baseline.md](docs/compatibility-baseline.md),
[function-policy.md](docs/function-policy.md) and the generated
[function inventory](docs/function-inventory.md). The inventory covers 386
core functions, 119 converter helpers and 42 optional manifests.
[AGENTS.md](AGENTS.md) records contributor and testing rules.
