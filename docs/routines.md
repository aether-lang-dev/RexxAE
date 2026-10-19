# Labeled routines and resumable CALL

RexxAE follows RexxJS `8317bd1`: plain routines share variables and argv;
PROCEDURE routines create a fresh script-variable generation and restore
caller arguments when they return. EXPOSE selects variables to share.

```rexx
CALL add 2, 3
SAY RESULT
EXIT 0

add:
ARG left, right
RETURN left + right
```

Labels and direct CALL targets ignore case; variable names retain case.
Forward calls, nested calls and recursion work. Labels occupy their own clause, or carry `name: PROCEDURE [EXPOSE names]`.
Other same-line statements and labels nested inside control structures are
not supported. The last duplicate label wins, matching the reference.
Main execution skips each labeled body through its first top-level RETURN or
the next label/end of source. Statements after that RETURN remain executable
in the main flow, so an explicit EXIT before routine definitions is clearest.

## Arguments, results and scope

| Form | Current behavior |
|---|---|
| `CALL name 1, 2` | Comma-separated argument expressions. |
| `CALL name 1 2` | Blank-separated arguments without a standalone binary operator. |
| `CALL name n - 1` | One expression argument, matching the reference's operator rule. |
| `CALL name n-1` | One expression argument without intervening blanks. |
| `CALL (target) 1` | Resolve the target variable, then dispatch by name. |
| `CALL TESTHOST value` | Registered application function; yield FUNCTION, then place its typed reply in RESULT. |
| `ARG a,b` / `PARSE ARG a b` | Bind successive arguments directly, including typed values; missing arguments become empty strings. Simple variable names only. |
| `ARG()` | Current argument count. Assign to a variable before combining with other SAY operands for shared parser behavior. |
| `ARG(n)` | One-based argument access; a missing position yields an empty string. |
| `ARG(n,'E')` | One if the argument exists, otherwise zero. |
| `ARG(n,'O')` | One if an existing argument is an empty string; a missing position yields zero. |
| `RETURN value` | Return a typed value; CALL places it in RESULT. |
| `RETURN` | Return an empty string. |
| Top-level RETURN | End the script with exit code zero. |
| EXIT in a routine | End the entire script with the requested exit code. |

A plain routine can change its caller's variables. Its argument list is also
shared: after a plain nested CALL, ARG()/ARG bindings see the inner arguments.
Host and builtin CALLs do not replace that list.

`PROCEDURE` must be the first instruction of a labeled routine, on the label's
line or the next clause. It hides caller script variables; exact flat names
starting `RUNTIME.` remain visible when present. `PROCEDURE EXPOSE total stem.`
shares `total` and the entire root `stem`. Names retain case and are exact,
with a final period stripped to expose a root. Dotted individual names are
not partial-object exposures. Local variables disappear on return, error or
EXIT; exposed changes propagate and the caller's argv is restored. Nested
plain calls share the current generation; recursive PROCEDURE calls each
receive independent generations. RESULT receives the returned typed value.
Snapshots contain only script variables, never private engine or host state.

```rexx
LET total = 10
CALL add 5
SAY total
EXIT
add: PROCEDURE EXPOSE total
ARG amount
total = total + amount
RETURN
```

A routine ending at the next label or end of source returns the global return
value captured at entry, or typed null before the first explicit RETURN.
This unusual default is covered by shared fixtures. RETURN from inside a loop
unwinds that routine's loop frames and restores preexisting loop variables,
while retaining the caller's active loops.

`LET x = CALL routine 2` preserves another reference quirk: x receives
`{"terminated":false,"returnValue":...}`, rather than the returned value alone.
This form supports internal and registered host routines with simple
blank-separated arguments. Commas/standalone expression operators and assigned
CALLs to builtins are diagnosed as unsupported; use an ordinary CALL followed
by `LET x = RESULT`, or a builtin function expression.

The reference parses **RETURN RESULT as a RESULT() function call**, which can
emit a default host command. RexxAE reads the variable instead. This is pinned
as a known parser difference, including both outputs and commands. Shared
syntax is:

```rexx
CALL TESTHOST input
LET answer = RESULT
RETURN answer
```

Positional PARSE templates, omitted positional slots, external script loading,
internal routines invoked as expression functions and
SIGNAL/error handlers remain outside this slice. CALL to implemented builtins
has a tested initial profile; the reference uses a separate, less consistent
conversion path there. Broad converter equivalence is not claimed.

## Execution and verification

The public C/Aether API is unchanged. Each call frame retains the return
instruction, caller's expression cache and loop-stack base. Recursion gets
separate caches even when the AST node IDs repeat. Returning restores the
caller cache and records the result of its suspended CALL, so host effects in
arguments are not repeated. Call/return transitions count toward instruction
budgets. No native recursive interpreter stack remains across a yield.

The current call-depth limit is 128. Exceeding it produces a terminal script
error at the calling line. Destroying an errored, pending or budget-suspended
context frees all active frames and caches.

`routine_cases.json` contains 44 complete programs shared by std.spec, ctypes
and RexxJS. Another 24 migration probes run natively and differentially. Native lifecycle specs additionally cover pending requests, error
locations, recursion limits, early EXIT and teardown. Actual Aether binary
consumers test both self-contained and shared-runtime libraries. The C counter
uses a routine; the Python harness uses nested routines to steer typed host
functions. Valgrind covers every native executable, including both binary
consumers.
