# Current compatibility gaps

Use the [pinned references](compatibility-baseline.md) and
[README validation summary](../README.md#verification-and-references) when
assessing compatibility. The [machine-readable audit](reference-audit.json)
records additional boundary probes in
[reference_update_20261019.json](../tests/reference_update_20261019.json).
These probes include unsupported syntax and are separate from strict parity.

## Variable-led ADDRESS clauses

RexxAE accepts variable-led commands in the combined form, including compound
variables and terms joined by blanks, abuttal or `||`.

```rexx
LET command = 'cell.get '
LET cell = 'A1'
ADDRESS APP command || cell
```

The clause sets the selected environment and emits the usual host request.
The host retains control over dispatch and replies through RC, RESULT and
ERRORTEXT. The supported variable-led form consists of terms joined by
concatenation.

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
With those, `LET x = CALL f ...` gives f's RETURN value on both engines
(RexxJS `5d96050`). For the equivalent `LET result = CALL pair 'a', 'b'`, the
audited reference returns `'a',b` rather than `ab`. Nested calls
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
