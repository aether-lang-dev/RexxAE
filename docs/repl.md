# Console REPL and the calculator demo

Select the [supported compiler](../README.md#build-and-test), then run from the
repository root:

```sh
make repl
```

The console is a small Python/ctypes host for the compiled Aether engine.
Python handles terminal input and host dispatch. Rexx parsing, arithmetic,
variables, routines and evaluation all execute in native RexxAE. No Python
or JavaScript evaluation implements Rexx expressions.

```text
rexx> LET total = 10
rexx> = total * 2
20
rexx> :begin
... DO i = 1 TO 3
... total = total + i
... END
... SAY total
... :run
16
rexx> :show total
16
rexx> :quit
```

Use `SAY expression` for ordinary Rexx output; the leading `=` is a console
shortcut that submits `SAY expression`. It is not a new Rexx grammar rule.
`:help` lists the commands. `:reset` clears variables and selected ADDRESS
environment; the host's mounted service set remains the same. `:show name`
prints the value as JSON using literal host property paths. It distinguishes
typed null (`null`) from an unset variable (`(unset)`).

`:begin` collects a complete multiline program, `:run` submits it once, and
`:cancel` discards the collected input. EOF discards an unfinished block and
reports it. The host does not guess whether a partial program is complete.
Routine definitions belong to that submitted program: define and CALL them
in the same block. Variables persist across entries; routine definitions,
argv and execution stacks do not. EXIT ends the submitted program, while
`:quit` exits the console.

Input can also be piped to `python3 examples/repl.py build/librexxae.so`.
Nonterminal input produces no banner or prompts.

## Session behavior and ownership

`rexxae_create_next(previous, source)` is a host-only C/Aether API. It accepts
a DONE or ERROR context and creates a separately owned context for the next
program, copying script values, existing host function registrations and the
selected ADDRESS environment. Destroy each context independently. Active,
SAY-paused, budget-paused and host-request-pending contexts are rejected.
The new context does not contain old instructions, labels, caches or private
call/loop state, and it never reexecutes previous source.

The Python host retains the previous context while a candidate entry runs:

- Syntax errors discard the candidate before effects and retain prior state.
- Normal completion adopts the new context and destroys the previous one.
- Runtime errors adopt the engine's unwound state: earlier assignments remain;
  scoped routine locals are restored according to ordinary execution rules.
- Ctrl-C or the instruction limit discards the candidate and retains the prior
  entry's bindings. This cannot undo output or host effects already performed.

The default instruction limit is 100,000 per submission, adjustable with
`--instruction-limit`. It counts interpreter steps. It is not a wall-clock,
parser, individual-builtin or memory quota. Ctrl-C is cooperative with return
from native calls. Resets and teardown release owned contexts.

The public API permits the host to preserve or branch terminal session state;
it does not give guest Rexx a context handle or registry access. Script data
named `h.EXEC`, `permissions.net`, etc. remains data in later entries.

## Native declared-endpoint calculator

The separate [calculator demo](calculator.md) uses a native Aether console
and the compiled RexxAE library. Its startup script explicitly imports the
function it calls:

```rexx
REQUIRE "/static/calculator.rexx"
SAY CALC('add', '0.1', '0.2')
```

The complete [startup script](../examples/calculator/calculator.rexx) also
declares calculator POST and module GET requests. The console asks separately
for both permissions before executing Rexx or downloading code. The relative
reference resolves against the configured calculator origin, and the
[served Rexx source](../examples/calculator/static/calculator.rexx) defines CALC.
It executes with only the approved calculator POST adapter.

The calculator guide covers local HTTP, HTTPS with Aether TLS 1.3, deployment
and the terminal integration runner. The Python console above mounts no effect
services by default and does not provide this network resolver.
