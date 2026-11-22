# Suggestions for RexxJS

RexxJS and RexxAE track each other's language and functions as far as that
is possible ([rexxjs-tracking.md](rexxjs-tracking.md)). This page collects
behaviour in RexxJS that looks like a bug against classic (ANSI) Rexx, and
what RexxJS could take from RexxAE, each with a test program and where in
RexxJS's source (`core/src/`, at the commit in the Makefile's `REXXJS_GREEN`)
the change would go. Nothing here has been pushed to RexxJS; each item waits
for a decision on how it lands. Where an item is pinned by a test, its name in
`tests/known_differences.json` is given: when RexxJS changes, that entry fails
and the case moves into strict parity.

Each program runs under `python3 tools/probe.py build/librexxae.so ../RexxJS '<program>'`
(newlines as `\n`), which prints both engines' answers.

## Suspected RexxJS bugs

### 1. `**` binds more loosely than `*` and `/`

```rexx
LET a = 2 * 3 ** 2
SAY a          /* classic Rexx and RexxAE: 18; RexxJS: 36 */
```

Classic Rexx evaluates prefix operators, then `**`, then `* / % //`, then
`+ -`. RexxJS's multiplicative loop in `parser.js` (around line 2792) takes
`**` at the same level as `*` and `/`. Give `**` its own, tighter level.
`2 ** 3 ** 2` is already 64 in both (left to right). Pinned:
`power_binds_tighter_than_multiply`.

### 2. `SAY` does not evaluate operators

```rexx
LET n = 5
SAY n * 2      /* classic: 10; RexxJS: 5 * 2 */
```

`SAY` (`parser.js`, the `^SAY\s+(.*)` match near line 1285) evaluates function
calls and concatenation but leaves arithmetic and comparisons as text. SAY's
operand is an ordinary expression in classic Rexx.

### 3. Comparisons and `& | &&` in an assignment are left as text

```rexx
LET r = 'abc' \= 'abd'   /* classic: 1; RexxJS: abc' \= 'abd */
LET s = 1 & 0            /* classic: 0; RexxJS: 1 & 0 */
LET t = 'b' >> 'a'       /* classic: 1; RexxJS: b' >> 'a */
```

The same operators work after `IF`. The assignment path (`parser.js`, the
`name = expression` match near line 1348, and
`interpreter-expression-value-resolution.js`) does not reach the comparison
and logical operators when an operand is a quoted string, nor `&`, `|`, `&&`,
`>>`, `<<`, `\<`, `\>` at all. In `IF`, `\` as a prefix (`IF \ (1 = 2)`) is
reported as an unknown comparison operator, and `&&` is read as and, where
classic Rexx has exclusive or.

### 4. `DO i = a TO b FOR n`, `... WHILE` and `... UNTIL`

```rexx
DO i = 1 TO 10 FOR 2; SAY i; END      /* classic: 1 2; RexxJS: 1 .. 10 */
DO i = 1 TO 5 WHILE i < 3; SAY i; END /* classic: 1 2; RexxJS: 1 .. 5 */
DO i = 1 TO 5 UNTIL i = 2; SAY i; END /* classic: 1 2; RexxJS: 1 0 */
```

`parser.js` (the controlled-loop matches near lines 1918 and 1939) takes
everything after `TO` (or `BY`) as one expression, so `FOR` and `WHILE` are
lost and `UNTIL i = 2` becomes part of the bound. Classic Rexx allows `TO`,
`BY` and `FOR` in any order, each once, then one `WHILE` or `UNTIL`. RexxAE's
`do_statement` in `src/program.ae` is a model. Pinned: `do_for_count`,
`do_range_while`, `do_range_until`.

### 5. `SIGNAL label` runs on into the clauses it skipped

```rexx
SIGNAL done
SAY 'skipped'
done:
SAY 'here'      /* classic: here; RexxJS: here, then skipped */
```

`SIGNAL` (`interpreter.js` near line 1291, `interpreter-error-handling.js`
near line 165) runs the label's clauses and returns to the clause after the
`SIGNAL`; classic `SIGNAL` transfers control and does not come back.

### 6. `PULL` keeps the case, and takes one variable only

```rexx
PUSH 'b'
PULL x
SAY x           /* classic and RexxAE: B; RexxJS: b */
```

Classic `PULL template` is `PARSE UPPER PULL template`.
`interpreter-variable-stack.js` `executePull` (line 356) assigns the line to
one variable as it is; `parser.js` (`^PULL\s+(\w+)`, line 619) takes one
name. Uppercase, and parse a template as PARSE does. Pinned: `pull_uppercases`.

### 7. `PARSE VALUE 'a b c' WITH x y` splits the literal wrongly

```rexx
PARSE VALUE 'a b c' WITH x y
SAY x '|' y     /* classic and RexxAE: a | b c; RexxJS: b | c' */
```

The match in `parser.js` (`^PARSE\s+VALUE\s+(.+?)\s+...`, line 565) is not
aware of quotes and splits inside the string. Positional templates
(`PARSE VAR s 1 a 3 b`) and variable patterns (`(d)`) also give empty fields
in RexxJS; RexxAE does not have them yet either (see the tracking table).

### 8. `DATATYPE`: classic option letters, and JavaScript number syntax

```rexx
LET a = DATATYPE('12', 'W')   /* classic and RexxAE: 1; RexxJS: false */
LET b = DATATYPE('0x1F')      /* classic and RexxAE: CHAR; RexxJS: NUM */
```

`validation-functions.js` `DATATYPE` (line 469) compares the option with its
own type names (`NUM`, `CHAR`, ...) and so answers false for every classic
letter (A B L M N S U W X); `getDataType` (line 27) uses `isFinite`, which
accepts `0x1F`, `0b11` and `0o7`. RexxAE keeps RexxJS's type-name form and
adds the letters (answered 1 or 0); `classic_number_` and `datatype_` in
`src/library.ae` are a model. Pinned: `datatype_classic_option`,
`datatype_hex_text`.

### 9. `SYMBOL('12')` is `BAD`

```rexx
LET a = SYMBOL('12')    /* classic and RexxAE: LIT; RexxJS: BAD */
```

`interpreter-builtin-functions.js` `SYMBOL` (line 1110) accepts only names
starting with a letter or underscore. Classic Rexx answers `LIT` for a
constant symbol (one starting with a digit or a point), and allows `!` and
`?` in symbols. Pinned: `symbol_constant`.

### 10. The positional argument converter loses arguments

```rexx
LET a = JSON_PARSE('[3,1,2,4]')
LET r = ARRAY_SLICE(a, 1, 3)      /* RexxAE: [1,2]; RexxJS: [3,1,2,4] */
LET i = ARRAY_INDEXOF(a, 1)       /* RexxAE: 1; RexxJS: -1 */
LET u = ARRAY_UNSHIFT(a, 0)       /* RexxJS: [[3,1,2,4],0,3,1,2,4] */
```

`parameter-converter.js` (the cases near lines 455 to 500) reads
`params.start || 0` and `params.item || ... || null` after the positional
arguments have been named, and the names do not match, so the bounds and the
item are lost; for `ARRAY_PUSH` and `ARRAY_UNSHIFT` the array is added again
as an item. The named forms (`start=`, `end=`, `item=`) work. Pinned:
`array_slice_positional`, `array_includes_positional`.

### 11. `EXIT UNLESS`'s message is not evaluated

```rexx
x = 5
EXIT UNLESS x > 9, 'x is' x     /* RexxAE: x is 5; RexxJS: 'x is' x */
```

`interpreter-exit-unless.js` evaluates the message only when it contains
`||`, and otherwise prints its source text. Evaluate it as an expression.
Pinned: `exit_unless_message_expression`.

### 12. Smaller ones

- Nested comments: `SAY 'a' /* x /* y */ z */ 'b'` gives `a Z */ b`; classic
  comments nest.
- A comma at the end of a line continues the clause in classic Rexx;
  RexxJS prints the two lines separately (`SAY 'a',` then `'b'`).
- `NUMERIC DIGITS 5` is accepted and ignored (`2 / 3` stays
  `0.6666666666666666`). Either implement it (TODO.md proposes decimal
  arithmetic as a later opt-in in both engines) or reject it, so a script that
  depends on it fails visibly.
- `ARRAY_POP` and `ARRAY_SHIFT` of an empty array give JavaScript's
  `undefined`, which prints as `undefined`; RexxAE gives the empty string.
- `AND('1', 1)` is false: text counts as true only when it reads `true`.
  Rexx programs write truth as `1`; consider counting `'1'` as true.
- `push = 3` (an instruction keyword followed by `=`) runs the instruction
  instead of assigning; classic Rexx assigns.
- `BASE64_ENCODE` throws on a character above U+00FF (node's `btoa`);
  encoding the UTF-8 bytes, as RexxAE does, would accept any text.

## What RexxJS could take from RexxAE

- `PARSE UPPER`, `PARSE LOWER` and `PARSE PULL` (classic): RexxJS sends these
  clauses to the default ADDRESS environment. Pinned: `parse_pull`,
  `parse_upper_var`.
- `DATATYPE`'s classic option letters, and `DO ... FOR / WHILE / UNTIL` (above).
- `TRACE` with the `?` and `!` prefixes (RexxJS sends `TRACE ?R` to the
  default environment).
- The RexxAE extensions `LOG_TRACE` .. `LOG_FATAL`, `CRON_VALID` and
  `CRON_NEXT` (docs/cron-and-logging.md), if RexxJS wants the same static
  logging and cron (already recorded as `rexxae_extension` differences).
- Classic builtins neither engine has yet, to add to both together: the
  tracking table's "Classic Rexx builtin functions" lists them (`LASTPOS`,
  `CHANGESTR`, `COUNTSTR`, `INSERT`, `OVERLAY`, `DELSTR`, `WORDINDEX`,
  `WORDLENGTH`, `JUSTIFY`, `COMPARE`, `XRANGE`, `FORMAT`, `TRUNC`, `SIGN`,
  `QUEUED`, `DIGITS`, ...). `QUEUED()` would be `STACK_SIZE()` under its
  classic name.
