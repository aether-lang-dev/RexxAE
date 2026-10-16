# PARSE templates and compound values

This page describes the native profile targeting RexxJS `e3bd4e9`, including
script-derived compound tails and uppercase unset symbols. Host API paths
remain literal. See [reference-update.md](reference-update.md).

RexxJS is the baseline. Its implemented template language splits words and
matches quoted literal delimiters; numeric positions are not implemented as
positions. RexxAE diagnoses positional and relative-position templates instead
of binding variables named after those numbers.

```rexx
ADDRESS APP 'status'
PARSE VAR RESULT status ':' detail
LET response.code = status
LET response.text = detail
```

PARSE VAR takes a simple source variable. An unset, null, false or numeric-zero
source becomes empty text, following the reference's JavaScript defaulting.
The string `'0'` remains text. Each variable before another variable takes the
next word separated by an ASCII space, then skips repeated spaces. The final
variable takes the entire remainder, including trailing spaces. Initial spaces
are retained: an input starting with a space produces an empty first field.
Tabs in input are ordinary characters, not word separators.

A variable followed by a quoted delimiter takes everything up to its next
occurrence. A missing delimiter gives that variable the remaining text and
leaves subsequent variables empty. An empty delimiter matches at the cursor.
Leading or standalone delimiters do not move the cursor, matching the current
reference. Separate template names and literals with spaces. The standalone
`.` consumes a field without retaining it. Repeated target names keep their
last assigned value. Names are case-sensitive. UTF-8 literal delimiters work;
there are no byte/UTF-16 position operators in this slice.

## PARSE VALUE

The explicit form evaluates its input, including typed values, arithmetic,
functions and suspended application requests:

```rexx
PARSE VALUE TESTLINE() WITH status ':' detail
```

No template variables bind until the complete input has resolved. Earlier
host calls in a partially evaluated input are cached across suspension.
Non-string values use the same Rexx display conversion as SAY.

The simple no-WITH form preserves the reference's older behavior:

```rexx
PARSE VALUE input first rest
```

It takes one raw input token and a template of simple names. The reference
looks up that raw token as a variable and otherwise uses it literally. Quoted
input therefore retains its quote characters, and a falsey variable falls
back to its variable name. Richer no-WITH input/templates are ambiguous in the
reference parser and are diagnosed as unsupported here; use PARSE VAR or the
explicit form.

WITH is optional in RexxAE's PARSE VAR form and required for evaluated VALUE
input. This is deliberately pinned as a compatibility difference: RexxJS's
parser often treats WITH as another target, or absorbs template text into the
input. Shared simple-input syntax omits WITH. ARG/PARSE ARG retain their
separate direct positional-binding behavior.

Templates are limited to 256 fields. Compound template targets, positional
operators, PARSE UPPER, SOURCE and PULL remain unsupported. Syntax errors are
located before any host effects; input errors retain the PARSE statement line.

## Dotted names and stems

A script compound symbol derives each tail independently from an existing
simple variable, once. Numeric, empty and unset tails stay literal. Exact
flat variable names take precedence. The root name is never substituted.

```rexx
LET key = 'name'
LET record.key = 'Rexx'
SAY record.name record.key
/* Rexx Rexx */
```

Tail substitution also applies to reads and dynamic CALL targets. Storage
remains case-sensitive. Unset simple and compound symbols return their derived
uppercase name: with `i=2`, an unset `list.i` displays `LIST.2`.

Nested assignment creates missing objects and replaces scalar/null
intermediates. A scalar or array at the root becomes an object when a property
is assigned, matching the reference. An empty tail (`record.`) is an empty
property key; it is not a stem default. Numeric object keys are literal too.

Reads traverse typed objects and zero-based array indices. Arrays also expose
`.length`; `array.01` is not index 1. Missing symbol paths resolve to their derived uppercase
spelling, while an existing typed null displays `null`. There is no JavaScript
prototype chain, callable property, native pointer or hidden host object behind
these data values.

The host variable getters/setters use literal dotted paths, without script
tail substitution. A script variable `key='other'` cannot change a host lookup
of `record.key`. Choose template target names that do not accidentally match
property names when assigning parsed text into an object. Writes
through a nested array are explicitly unsupported, and a rejected write leaves
the previous root intact. Paths are bounded to 64 nested components. Classic
stem defaults, array mutation through paths, property
interpolation and compound loop/ARG targets remain outside this profile.

Objects have owned value semantics. Assigning one variable to another copies
its value; subsequent writes do not mutate the copy. RexxJS uses object aliases.
That difference is asserted independently of the matching-program suite.
Integer object-key serialization order and general JavaScript property/coercion
semantics are not established as compatible. DO OVER does enumerate canonical
integer object keys in ascending order before other keys in insertion order;
`DO v OVER stem.` strips the final period to iterate the root. Empty arrays
are accepted; empty objects error. String/scalar/array-like OVER remains outside
this profile.

The fixture file has 29 complete programs shared by std.spec, ctypes and
RexxJS. Nine additional native specs cover evaluated WITH input, no replay,
public compound access, rejected writes, depth bounds and pending teardown.
Actual Aether binary consumers test the typed boundary with both library
variants. The C and Python host examples also parse replies and use the
compound values they own.
