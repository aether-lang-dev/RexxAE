# Native function policy and current profile

RexxJS is the behavioral reference. Its npm ecosystem is useful evidence for
what people can do, not a requirement to bundle every dependency in an
embedded native interpreter. Decisions below are provisional. No optional
function family has been permanently removed by this initial implementation.

## Function inventory

`make inventory REXXJS=../RexxJS` creates the Markdown and JSON inventories.
`make check-inventory` detects changes against that same checkout. The
generator instantiates the reference interpreter to inspect registration;
it does not call registered functions, execute scripts or load extras.

At current reference `e3bd4e9`, registration still contains 505 entries: **386 callable
language functions and 119 argument-converter helpers**. Counting converters
as functions would overstate the porting task. Source ownership is inferred
from loaded export identities and function-name matches for wrappers.
Metadata/docs alone are insufficient: they disagree with some implementations.

Extras are analyzed through 42 package manifests and conservative static
function/import candidates in 82 source files. Those candidates are not an
exhaustive export list, nor proof that a feature runs without its dependency.
Static import matching sees literal calls and declarations, including code
behind runtime guards. Dynamic import names and generated registrations need
manual analysis. Source revisions and live registration remain the baseline.

## Choosing a native route

| Family | Approach |
|---|---|
| Scalar strings and deterministic maths | Implement in Aether over std.string/std.math, with parser-level differential fixtures. 60 functions have an initial implementation. |
| Arrays, JSON, data manipulation and schema | Eleven initial typed/context functions are implemented; extend collection and schema coverage using std.list/std.map/std.json/std.schema with differential fixtures. |
| Regex and validation | std.regex is a starting point; PCRE and JS RegExp differ in flags, matches, replacements and Unicode behavior. Port with dedicated fixtures. |
| Time and randomness | Separate deterministic operations from host clock/entropy inputs. Date parsing/time zones and seeded behavior need an explicit profile. |
| Crypto, encodings and IDs | std.cryptography/std.encoding/std.uuid/std.nanoid provide candidates. Review password/JWT and security-sensitive behavior individually; names alone do not establish equivalence. |
| Filesystem, network and processes | Explicit host services or separately enabled adapters. Preserve a capability-empty default engine. Some shell-named text utilities may be pure functions and are marked for review. |
| DOM and graphics | Host UI adapters or optional rendering libraries. A native application's object/widget model determines what makes sense. |
| jq | Strong native candidate: contrib.jq is an Aether jq implementation with compile/run APIs. Compare its jq coverage with RexxJS's jq/WASM wrappers and retain useful function names. |
| minimatch | Optional native matching module; std.string.glob_match is useful but not a promise of minimatch's extglob/brace/negation semantics. |
| diff and sed | Optional algorithm ports or native adapters. Neither has a complete stdlib replacement established in this audit. |
| Excel | Optional formula algorithms; separate calculation from browser delivery and rendering. A spreadsheet application is not required for embedding tests. |
| R/NumPy/SciPy/MATLAB/SymPy | Optional numerical/symbolic modules, selected by demand. std.math/std.floatarr provide primitives, not substitutes for full numerical libraries. Large algorithms may justify native backend dependencies. |
| Graphviz | Optional native Graphviz adapter and output surface; WASM/npm loading is replaceable packaging. |
| Remote AI/cloud/container/VM ADDRESS libraries | Host-supplied adapters; keep provider SDKs, credentials, process execution and network transport outside the default engine. |

The concrete **proposed omissions** are JS runtime introspection/evaluation
(`JS_SHOW`, `INTERPRET_JS`) and browser-specific Python/WASM delivery layers.
Useful mathematical functions from those libraries can still get native
implementations. This proposal leaves Rexx `INTERPRET` in the language plan.

Webpack, Webpack CLI and Node browser polyfills account for many manifest
dependencies. They often support delivery rather than algorithms. A package
depending on them is not automatically expensive to port. Conversely,
`diff`, `sed-lite`, `minimatch`, `canvas`, `graphviz-wasm` and `jq-wasm` point
to real feature dependencies requiring an implementation or adapter choice.
Dev/test dependencies are recorded separately in JSON.

## Delivered functions

The 33 text functions cover casing, UTF-16 LENGTH, SUBSTR/SUBSTRING,
POS/INDEX/INDEXOF, membership and prefix/suffix tests, abbreviation, trimming,
stripping, reversal, word operations, spacing, repeating, padding,
LEFT/RIGHT/CENTER, translation, verification and slug creation.

The 27 deterministic math functions cover ABS/MIN/MAX and their MATH aliases,
floor/ceil/round/INT, reductions, powers, roots, logs, trigonometry, clamp,
percentages, factorial, GCD/LCM and 2D distance/angle. Random functions remain
unimplemented. Exact names and source ownership appear in the inventory.

Eleven additional functions operate on typed values and call context: JSON_PARSE,
JSON_STRINGIFY, JSON_GET, JSON_KEYS, ARRAY_GET, ARRAY_LENGTH, ARRAY_PUSH,
JOIN, TYPEOF, lazy IF and ARG. This is an initial profile, not the complete
RexxJS JSON/array API. JOIN joins text; ARRAY_JOIN is a different, relational
operation and remains unimplemented.

Calls work inside expressions, with nesting and positional arguments:

```rexx
LET label = UPPER(SUBSTR('abcdef', 2, 3)) || LOWER('Z')
LET magnitude = ABS(-3) + MAX(4, 5 * 2)
```

Named calls also work, for the recognized parameter aliases:

```rexx
LET part = SUBSTR string='abcdef' start=2 length=3
LET power = MATH_POWER base=2 exponent=5
```

Current restrictions and behavior:

- Text operations other than LENGTH explicitly reject non-ASCII arguments.
  Aether byte-indexed strings, Unicode graphemes and JavaScript UTF-16 units
  differ. LENGTH counts UTF-16 units for valid UTF-8 input, including two for
  supplementary characters; Unicode casing/slicing/search are still pending.
- Owned values support null, booleans, numbers, strings, arrays and objects.
  Converter defaults distinguish numeric zero from the string `'0'`.
  Undefined, reference identity and general JavaScript coercion remain
  outside this initial profile. JSON_GET currently accepts a direct key;
  missing keys/indices produce errors rather than undefined.
- Numeric results use floating point. Finite numeric-prefix parsing matches
  the tested parseFloat cases. Infinity input text, all extreme magnitudes,
  parseInt radix variants and exact JS shortest-number formatting need more
  work. Integer indices/counts currently use signed 32-bit parsing.
- REPEAT/COPIES and padding reject requested output sizes above 1 MiB. This
  is a local implementation limit, not a complete script memory quota.
- Duplicate named arguments, unknown aliases, malformed argument lists and
  mixed positional/named calls are diagnosed. Arbitrary named-parameter
  combinations are not established as compatible. Typed and registered host
  functions currently use positional arguments. Parenthesized and
  unparenthesized named calls are distinct parser paths and need fixtures
  when extended.
- Function domain errors terminate the current execution. RexxJS-compatible
  SIGNAL/error-handler behavior remains part of the execution-frame work.

## Compatibility findings that tests preserve

- POS is data-first (`POS(haystack, needle)`), unlike classic Rexx's order.
- SUBSTR starts at one; SUBSTRING starts at zero. Both inherit JavaScript
  substring's endpoint swapping when given a negative length.
- INT is Math.floor: `INT(-1.2)` gives `-2`. Rounding ties go toward positive
  infinity: `MATH_ROUND(-1.5)` gives `-1`.
- Math reductions ignore invalid numeric inputs; numeric strings may contain
  trailing text because the reference uses parseFloat.
- Converter defaults are observable. `MATH_PERCENTAGE(25, 0)` gives `25`,
  while `MATH_PERCENTAGE(25, '0')` gives `0`. `MATH_POWER(2, 0)` gives `2`,
  while its quoted-zero counterpart gives `1`. Types persist through
  variables and nested calls in the native implementation.
- LEFT/RIGHT's numeric zero length is defaulted to one by conversion, while
  other padding functions can return an empty result. INDEX's empty
  positional needle falls into its array-style converter defaults, unlike
  POS. The differential boundary matrix captures these paths.

- ARRAY_PUSH's positional converter includes the first array argument among
  the appended items: ARRAY_PUSH([1,2],3), when the array is supplied through
  a variable, yields [1,2,[1,2],3]. JSON_STRINGIFY's converter defaults null,
  false, numeric zero and the empty string to an empty object. Fixtures
  preserve these observed quirks.
- Seven compatibility differences are recorded separately in
  `tests/known_differences.json`: direct boolean literals in TYPEOF,
  single-quoted object keys, and direct composite arguments containing
  commas, RETURN RESULT being parsed as a function call, and compound
  function arithmetic in conditions, PARSE WITH handling and object aliases.
  Tests assert both implementations'
  results; these cases are not counted as matching programs.

These are reference behaviors, not prescriptions for a redesigned language.
If a quirk should be corrected, change the reference or explicitly introduce
a versioned compatibility policy instead of silently changing the port.

## Tests

`make test` runs 382 std.spec cases: 125 shared function fixtures, 35
behavior/lifecycle/typed specs, 80 routine/migration specs, 35 SELECT specs, 38 PARSE and
compound specs, fourteen binary-import specs per library variant, and nineteen
containment specs per variant, plus three standalone trusted-service lifetime specs. It also runs Python/ctypes checks, a native C
host and a Python host harness. Actual binary consumers use `import rexxae`.

`make parity` compares 507 complete programs with RexxJS e3bd4e9, including host-call
arguments/results. All match. See reference-update.md for the vendor comparison.
Seven known differences have separate native/reference
assertions and are not counted as matching programs. `make containment` also
runs eleven compiler rejection probes, checks @pure entry points and pins
the guest-function/import surfaces. `make memcheck` checks the C example and
all twelve native spec executables, including recursive and suspended teardown.

The engine imports std.json but builds without filesystem/system grants and
with @pure public entry points. Host service tests deliberately import effect
modules outside the engine and enforce narrow runtime grants. Only fixture
runners read golden files. Make places cache files under build/cache.
