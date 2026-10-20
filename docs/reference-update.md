# Current compatibility gaps

Use the [pinned references](compatibility-baseline.md) and
[README validation summary](../README.md#verification-and-references) when
assessing compatibility. The [machine-readable audit](reference-audit.json)
records additional boundary probes in
[reference_update_20261019.json](../tests/reference_update_20261019.json).
These probes include unsupported syntax and are separate from strict parity.

## Variable-led ADDRESS clauses

The reference accepts a variable or variable-led concatenation as the command
clause. RexxAE currently requires a quoted-literal-led combined clause:

```rexx
LET command = 'cell.get A1'
ADDRESS APP command
/* Currently rejected by RexxAE. Shared form: */
ADDRESS APP 'cell.get A1'
```

Implementing variable-led clauses must preserve the selected environment,
RC/RESULT/ERRORTEXT replies, budgeted stepping and host vetoes. ADDRESS remains
an application request, with no implicit shell or extra authority.

## Assigned CALL expression arguments

Use ordinary CALL for expression arguments, then copy RESULT:

```rexx
CALL pair 'a', 'b'
LET result = RESULT
EXIT
pair: PROCEDURE
ARG p,q
RETURN p || q
```

RexxAE supports assigned CALL only with simple blank-separated arguments.
For the equivalent `LET result = CALL pair 'a', 'b'`, the audited reference
returns a wrapper whose returnValue is `'a',b` rather than `ab`. Nested calls
and arithmetic expose further parser differences. Extending this form needs
an explicit reference-semantics decision; the audit records these outputs
without treating them as desired behavior.

Parenthesized ADDRESS is also unresolved: RexxAE reports an error while the
reference silently ignores the audited form. It is not supported shared syntax.

## Other limits

See [README coverage](../README.md#coverage-and-limits) for missing language
features, [function policy](function-policy.md) for builtin restrictions, and
[known differences](../tests/known_differences.json) for deliberately distinct
results. Passing boundary probes should enter strict/native fixtures when
promoted into supported coverage; mismatches must not be counted as parity.

The [dated audit](archive/2026-10-19-reference-audit.md) preserves upstream
commit analysis, spreadsheet observations and the original implementation plan.
