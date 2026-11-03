# Provenance: cron parsing and search from Toit

`src/cron.ae` (CRON_VALID and CRON_NEXT) is a port, with adaptations, of
Toit's cron schedule.

| | |
|---|---|
| Upstream | [toitlang/toit](https://github.com/toitlang/toit) |
| Commit | `ec8860aa25d35e54f5cb3bcd437133054eccae8c` |
| Path read | `lib/cron/cron.toit` (and `lib/LICENSE` for the licence text) |
| Copyright | "Copyright (C) 2019 Toitware ApS" in `lib/cron/cron.toit`; "Copyright (c) 2021 Toit contributors" in `lib/LICENSE` |
| Licence | MIT (`lib/LICENSE`; the full notice is reproduced at the top of `src/cron.ae`) |
| Lineage | Toit's file says it implements [robfig/cron](https://github.com/robfig/cron)'s `spec.go`, which is also MIT. robfig/cron was not read for this port. |
| Local destination | `src/cron.ae`; wired into the evaluator in `src/evaluate.ae` (`cron_call`) |

Nothing else in the Toit checkout was read or copied. In particular its
`tests/` (including `tests/cron-test.toit`) and `src/` are LGPL and were not
used: `tests/test_cron.ae` is written from scratch, with expected instants
worked out from the calendar.

## What was ported

- The field model: six fields with bounds seconds 0-59, minutes 0-59,
  hours 0-23, day-of-month 1-31, month 1-12, day-of-week 0-6; a per-field set
  of values plus a "star" flag.
- The predefined schedules `@yearly`/`@annually`, `@monthly`, `@weekly`,
  `@daily`, `@hourly` and their six-field expansions.
- Field parsing: comma lists of `*`, `N`, `N-M`, each with an optional `/S`;
  `N/S` running to the field's maximum; a step above 1 clearing the star
  flag; the range and step checks.
- The day rule: when day-of-month or day-of-week is a star, both must
  match; otherwise either may.
- The search: find the first matching month, then day, hour, minute and
  second, starting one second after the given time with its fraction
  dropped, giving up after five years.

## Adaptations

- **Language and representation.** Aether, not Toit. A field is a 64-character
  `0`/`1` mask plus a star marker instead of a 64-bit integer (with its top
  bit as the star), so no 64-bit bit operations are needed.
- **Time.** Toit's `Time` is replaced by a day number (days since
  1970-01-01) and a second of the day, with Howard Hinnant's public-domain
  `days_from_civil` / `civil_from_days` for the proleptic Gregorian
  calendar. UTC only, as in the original (which notes it ignores time zones
  and daylight saving). Instants are limited to years 0000 to 9999.
- **Search steps.** Each mismatch jumps straight to the start of the next
  month, day, hour, minute or second and restarts the field checks, instead
  of Toit's "reset the lower fields once, then increment" (`added`). This
  finds the same first activation. It also avoids two problems in the Toit
  file: the month loop restarts on reaching February (`month == 2`) where
  robfig/cron restarts on January, and the day loop's restart appears to
  have lost its `continue` (the line reads `if start-over:/// Parse
  field`).
- **Five-year bound.** An activation is returned only if it is before the
  start instant plus five years (Toit tests the bound at the top of each
  pass, so a result found within a pass could lie past it). "No activation"
  is "" rather than `null`.
- **Five-field form.** The standard five-field cron form is accepted, with
  seconds fixed at 0. Toit accepts only six fields.
- **Parsing details.** Fields may be separated by runs of spaces and tabs
  (Toit splits on single spaces); shorthands are case-insensitive; `*-5`,
  empty list items, signs and non-digit text are errors with a message
  naming the field; numbers are limited to nine digits before the range
  check. Errors are returned as text (a script error from CRON_NEXT, 0 from
  CRON_VALID) rather than thrown.
- **Not taken from robfig/cron:** `?`, month and weekday names, `L`, `W`,
  `#`, 7 as Sunday, `@every`, `TZ=` prefixes. They are rejected.
