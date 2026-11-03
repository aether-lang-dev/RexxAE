# TODO

## One dialect with RexxJS

A server can run a script on RexxAE and send the same Rexx text to RexxJS in
a browser. Both must give the same answers, so every item below has to make
sense for RexxJS too: it is settled in one written spec and one shared set of
tests, then implemented in both engines. RexxAE does not drift on its own.

- **One spec, in one place.** RexxJS's `reference/` is the likely home. Each
  deliberate choice is written down once, e.g. "numbers are IEEE doubles,
  printed in their shortest round-trip form".
- **Shared conformance tests with checked-in expected output.** Today the
  differential tests treat whatever RexxJS prints as correct. Instead, both
  engines run the same scripts against recorded answers, so a bug in either
  engine fails, not just a difference between them.
  `tests/known_differences.json` keeps only the differences that are
  deliberate.
- **The host owns the clock and the time zone.** The engine formats and
  converts dates and times (pure arithmetic, identical in both engines). The
  host supplies the current instant and the local offset or zone: C or any
  language through the C interface, Aether, the ESP32 firmware, or the
  browser page for RexxJS (defaulting to the browser's own clock). Gains:
  - deterministic tests and recorded playback;
  - no ambient clock inside the sandbox;
  - no time-zone database in the engine.
- **One interchange form for an instant**, the same over the C interface,
  the worker protocol and HTTP to a browser. JSON has no date type, so pick
  one: an RFC 3339 string with an explicit offset
  (`2026-11-03T16:49:32.123+00:00`), or epoch milliseconds plus an offset.
  RexxJS's `NOW` (ISO, `Z`) and `NOW_TIMESTAMP` (epoch ms) are the starting
  point.
- **`DATE` and `TIME` with the classic option letters:**
  - `DATE`: `N S B D M W E U O`;
  - `TIME`: `N C L H M S E R`;
  - the ANSI conversion form `DATE(out, value, in)`;
  - the rule that every `DATE`/`TIME` call in one clause sees the same
    instant (the engine asks the host for "now" once per clause).

  RexxAE has none of these yet. RexxJS has them, with problems to fix there:
  - `DATE('B')` counts from 1901, not 0001 (JavaScript reads
    `new Date(1, 0, 1)` as 1901): 45963 instead of 739922 on 2026-11-03;
  - `D`, `U` and `W` have meanings other than the classic ones (classic:
    day of the year, `mm/dd/yy`, weekday name);
  - `E`, `O` and `M` silently fall back to the default format;
  - the reference says a bare `DATE` gives `2025-08-29` but the default
    case returns `3 Nov 2026`.

  Proposed: classic meanings in both engines.
- **Arithmetic.** RexxJS uses JavaScript doubles (`0.1 + 0.2` gives
  `0.30000000000000004`; classic Rexx gives `0.3`). Proposed: doubles by
  default in both engines, matching JSON. Classic `NUMERIC DIGITS` decimal
  arithmetic becomes a later opt-in, in both engines, for scripts that need
  exact results (money). Values that must stay exact cross the wire as
  strings.
- **Keep RexxJS's operators:** `%` is remainder and `//` starts a comment.
  Both differ from classic Rexx, but existing scripts depend on them.
- **`INTERPRET`.** RexxJS has it; RexxAE does not. Decide whether a host must
  grant it: it runs any string as code, so on a device that only accepts
  signed scripts it would let unsigned code run.
- **Not in either engine:**
  - the byte functions (`C2D D2C C2X X2C D2X X2D BITAND BITOR BITXOR`);
  - strings that can hold zero bytes.

  Both are needed only for Rexx that handles binary protocols. Until then,
  protocols (CoAP, DNS) stay native and reach scripts as host functions.

## Done: cron and logging (RexxAE extensions)

- **Logging is static** (done): `LOG_TRACE` to `LOG_FATAL` (message
  [, tags]), called as plain functions with no logger object to create or
  pass around. The host sets the threshold per context (off by default)
  and receives `REXXAE_LOG` events, through the C interface and the worker
  protocol. (`LOG` is taken: in RexxJS it is the logarithm.)
- **Cron** (done): `CRON_VALID(expr)` and `CRON_NEXT(expr, after)`, the next
  activation strictly after a given instant, in UTC. The instant comes from
  the host, as above (ISO as `NOW` gives it, or epoch milliseconds as
  `NOW_TIMESTAMP` gives it). Time zones wait for the host-owned zone item
  above.

[cron-and-logging.md](docs/cron-and-logging.md) has the contracts. Both are
RexxAE extensions until RexxJS has the same functions; they are listed as
such (`tests/guest_functions.json`, `tests/known_differences.json`, the
function inventory), not as parity.

- **Follow-up: the same functions in RexxJS**, settled in the shared spec
  and conformance tests above, so a script logs and schedules the same way
  in both engines. Then move them from the extension lists to parity.
