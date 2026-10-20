# Compatibility baseline

RexxJS is the dialect reference. Compatibility means matching observable
execution on the pinned interpreter, including output, typed values, host
requests and exit status. It does not imply classic Rexx conformance or
support for every registered RexxJS function.

## Reference revisions

| Source | Revision | Role |
|---|---|---|
| RexxJS | `8317bd1c2adeb966ea0eb9a91331f80c45bb79a1` | Grammar, runtime behavior and differential oracle. |
| spraedsheet | `c19848d9997fb746a077c336d50b86e739a99483` | Formula and application-control integration reference. |
| Vendored RexxJS | `b3d5e4ef7085180e2a9016ec11fb1eefccb2f5a2` | Spreadsheet's interpreter; shared core files match standalone. |

Toolchain requirements and validation totals live in the
[README](../README.md#build-and-test). The
[compatibility gaps](reference-update.md) separate unsupported syntax from
passing parity. [reference-audit.json](reference-audit.json) records the dated
standalone/vendor comparison; spreadsheet UI and CLI execution were not tested.

## Verification

```sh
make parity REXXJS=../RexxJS
make reference-audit
make check-inventory REXXJS=../RexxJS
```

`parity` is a strict equality gate for its fixtures. `reference-audit` also
characterizes unsupported boundaries; a completed audit is not a parity pass.
[Known differences](../tests/known_differences.json) assert each interpreter's
behavior separately and are excluded from matching-program totals.
The [function policy](function-policy.md) describes implemented profiles and
proposed native or application-provided routes for remaining functions.

A newer checkout can be selected with `REXXJS=/path/to/checkout`. These commands
do not fetch or modify it. A passing result applies to the tested programs
and selected revision, not to the entire dialect.

Earlier revision comparisons and spreadsheet integration analysis are retained
in the [archive](archive/README.md).
