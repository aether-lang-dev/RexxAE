# Cron and static logging

Two families of builtins that RexxJS does not have. They are **RexxAE
extensions**, listed apart from the RexxJS surface in
`tests/guest_functions.json` and pinned in `tests/known_differences.json`
(RexxJS sends the unknown call to the default ADDRESS environment). They are
not counted as parity. TODO.md keeps the follow-up of adding the same
functions to RexxJS.

## Static logging

```rexx
LET tags.order = id
LET tags.retry = 2
CALL LOG_INFO 'payment accepted', tags
LET x = LOG_WARN('slow reply from' host)   /* in an expression */
```

`LOG_TRACE`, `LOG_DEBUG`, `LOG_INFO`, `LOG_WARN`, `LOG_ERROR` and `LOG_FATAL`
take a message and, optionally, a tags object whose values are strings,
numbers or booleans (anything else, or tags that are not an object, is a
script error, also when logging is off). Each returns `""`. They are plain
functions: there is no logger object to create, name or pass around, and a
script cannot see or change the threshold or the context's name. `LOG`
itself is not one of them: in RexxJS `LOG` is the logarithm.

`CALL` separates arguments at blanks the way RexxJS does, so
`CALL LOG_INFO 'user' name` passes `name` as the tags and fails. Write
`CALL LOG_INFO 'user' || ' ' || name`, assign the message first, or use the
function form `LET x = LOG_INFO('user' name)`.

### The host's side

| Call (C; Aether drops `aether_`) | |
|---|---|
| `aether_rexxae_set_log_level(ctx, level)` | -1 off (the default), 0 trace, 1 debug, 2 info, 3 warn, 4 error, 5 fatal. Any time. |
| `aether_rexxae_set_log_name(ctx, name)` | A label (at most 256 bytes) the host attaches to its own output. |
| `aether_rexxae_log_name(ctx)` | That label, "" until set. |
| `aether_rexxae_log_level(ctx)` | The pending LOG event's level, -1 when none. |
| `aether_rexxae_log_tags_json(ctx)` | Its tags as a JSON object (`{}` for none), NULL when none. |
| `aether_rexxae_text(ctx)` | Its message. |

A call at or above the threshold makes `aether_rexxae_step` return
`REXXAE_LOG` (5). The host reads the event and steps again; there is no
reply. A call below the threshold produces no event, so with the default
(off) an existing host sees no change. The event suspends the instruction
like a FUNCTION request does: host calls already answered in the same
expression are not repeated, registry and variable mutation is rejected
until the next step, and `aether_rexxae_cancel` ends the script.
`aether_rexxae_create_next` copies the threshold and the name.
`examples/logging.c` is a complete C host.

The worker process carries it too: `guest.log_level(&g, level)` (Aether's `std.guest`)
(a `LOGLEVEL` frame, before `start` or at any time), then `LOG` events
from `guest.next` with `code` = level, `name` = `TRACE`..`FATAL`,
`text` = the message and `tags` = the JSON object. See README "Worker
process".

## Cron

```rexx
LET now = HOST_NOW()                          /* the host's clock */
LET at = CRON_NEXT('0 30 2 * * 1-5', now)     /* weekdays 02:30:00 UTC */
IF CRON_VALID(expr) THEN SAY 'next' CRON_NEXT(expr, now)
```

`CRON_VALID(expr)` is 1 or 0. `CRON_NEXT(expr, after)` is the first
activation **strictly after** `after`, or `""` when there is none within five
years. An invalid expression in CRON_NEXT is a script error naming the field
and the problem, for example
`CRON_NEXT: invalid cron expression '61 * * * *': minutes: 61 is above the maximum 59`.

**Instants.** `after` is either an ISO 8601 UTC instant as RexxJS's `NOW`
returns it, `2026-11-03T16:49:32.123Z` (milliseconds optional, `Z`
required, no offsets), or a whole number of epoch milliseconds as RexxJS's
`NOW_TIMESTAMP` returns it (a number, or text of digits). The result has the
same form: ISO with `.000Z`, or epoch milliseconds as a number. Years run
from 0000 to 9999; anything else is an invalid instant (a script error),
and a search that would pass the end of 9999 gives `""`.

**No clock, UTC only.** The engine has no clock: a script gets "now" from a
function the host mounts. Every field is UTC; there are no time zones and
no daylight saving. Zones are to come from the host later (TODO.md, "The
host owns the clock and the time zone").

**Expressions.** Six fields, `seconds minutes hours day-of-month month
day-of-week`, or the standard five (seconds = 0), separated by blanks:

| Field | Values |
|---|---|
| seconds, minutes | 0-59 |
| hours | 0-23 |
| day-of-month | 1-31 |
| month | 1-12 |
| day-of-week | 0-6, 0 = Sunday |

Each field is `*` or a comma list of `N`, `N-M`, `N/S` (from N to the
field's maximum), `N-M/S` or `*/S`. The shorthands are `@yearly` and
`@annually` (`0 0 0 1 1 *`), `@monthly` (`0 0 0 1 * *`), `@weekly`
(`0 0 0 * * 0`), `@daily` (`0 0 0 * * *`) and `@hourly` (`0 0 * * * *`),
in any case. Names (`JAN`, `MON`), `?`, `L`, `W`, `#` and 7 for Sunday are
not accepted.

**Day-of-month and day-of-week.** When both are restricted, a day matches
if either does (the usual cron rule): `0 0 0 13 * 5` is every 13th and every
Friday. When either is a star (`*`, `*/1`, or a list containing `*`), both
must match, which means just the other one: `0 0 0 * * 5` is every Friday.
As in robfig/cron, a stepped star such as `*/2` counts as restricted.

A day that never exists (`0 0 0 30 2 *`) gives `""`; February 29 is found in
leap years only (2000 is one, 2100 is not). The port's origin and changes are
in [provenance-toit.md](provenance-toit.md).
