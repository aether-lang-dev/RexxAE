# SELECT compatibility profile

SELECT evaluates WHEN conditions in order and executes only the first
matching branch. Later conditions and bodies are skipped, including their
host requests. If nothing matches, OTHERWISE executes; without OTHERWISE,
execution simply continues. Empty SELECTs and empty branches are valid in
the recorded RexxJS baseline.

```rexx
SELECT
WHEN mode = 'read' THEN CALL read_data
WHEN mode = 'write' THEN CALL write_data
OTHERWISE SAY 'unknown mode'
END
```

A multiline WHEN ends at the next WHEN, OTHERWISE or END. Its body can contain
nested SELECTs, actual DO loops, IFs and routine calls. A multiline OTHERWISE
runs through the matching END and must be the final clause. Inline branch
statements must finish in their own clause.

```rexx
SELECT
WHEN ready THEN
    DO i = 1 TO 3
        CALL TESTHOST i
    END
    SAY 'complete'
OTHERWISE
    SAY 'waiting'
END
```

The reference also accepts **WHEN condition THEN DO** with nothing after DO
on the header. That DO is a branch marker, not an additional nested block:
the next matching END closes SELECT. It does not require a second END.
For clarity, use bare THEN for multiline branches and introduce any actual
DO block on its own following clause. Inline OTHERWISE DO is outside the
supported profile; use a multiline OTHERWISE with a separate DO statement.

Another permissive reference behavior is preserved: inline OTHERWISE clauses
can occur before later WHEN clauses, and repeated inline OTHERWISE bodies
concatenate in source order. All WHEN conditions still run before any
fallback body. A matched WHEN skips every OTHERWISE body. Ordinary scripts
should place one OTHERWISE after the WHEN clauses.

RETURN and EXIT propagate out of either selected branch type. LEAVE and
ITERATE apply to the enclosing loop; SELECT introduces no loop scope. An
error or early return restores loop variables through the existing execution
frames. Conditions and body instructions retain their original source lines.

## Hosts and execution budgets

Conditions can call registered functions, and selected bodies can suspend
for COMMAND or FUNCTION replies. Partial expression results remain cached
while waiting, so earlier host calls in a condition are not repeated. A false
reply advances to the next WHEN. A true reply prevents later conditions from
running. Invalid JSON replies leave the request pending; accepted host errors
terminate at the condition or body line.

SELECT compiles into the existing branch and jump instructions. There is no
new public C or Aether API, and no selection frame to retain across yields.
Branch and jump instructions count toward the existing instruction budget.
The complete source still parses before any application effect is dispatched.
Malformed selections and excessive nesting therefore fail during creation.

## Reference parser limits and verification

The reference condition resolver can misread arithmetic across multiple
function calls, such as `ABS(2) + ABS(3) > 4`, as one function invocation.
RexxAE evaluates the arithmetic. This is a pinned known difference with
assertions for both implementations; it is not counted as parity. Shared
syntax assigns the sum first:

```rexx
LET magnitude = ABS(2) + ABS(3)
SELECT
WHEN magnitude > 4 THEN SAY 'match'
END
```

The SELECT fixture file contains 27 matching complete programs shared by
std.spec, ctypes and the actual RexxJS interpreter. Eight additional native
specs cover host-condition memoization, errors, parse-before-effect behavior,
EXIT/loop unwinding, nesting limits and suspended teardown. Host differential
cases compare the exact dispatch order and typed replies. Aether binary
consumers exercise both self-contained and shared-runtime libraries, including
pending conditions, errors and teardown. The C counter and Python host harness
also execute selected branches. Valgrind covers all native test executables.
