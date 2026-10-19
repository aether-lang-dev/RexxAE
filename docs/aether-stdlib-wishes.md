# Concrete stdlib wishes for the console and declared-endpoint demo

Inspected installed Aether 0.829.0 and `/home/paul/scm/aether/std` on
2026-10-19. These are stdlib API requests, not new language constructs or
claims that the underlying runtime operations are absent. No upstream issue
was filed as part of this inspection.

## 1. Line input with a distinct EOF result

**Resolved in Aether commit `7b48889abddb9575338d32cbf6e44f468978ce93`.**
`io.fd_read_line_status(fd)` now returns `(line, eof, err)` with owned line
storage. The optional native calculator console consumes it, with tests for
empty input, blank lines, CRLF and an unterminated final line. The development
compiler reports 0.830.0; installed 0.829.0 still has the older API described
below. See [the calculator demo](calculator.md) for build and terminal tests.

Source: `/home/paul/scm/aether/std/io/module.ae`, `fd_read_line`.

The existing `(line, err)` API returns `("", "")` both for an empty input line
and for EOF before any byte. A REPL needs an empty line to keep the session
alive and EOF to exit. An additive `read_line_status` returning line, EOF and
error (or an equivalent tagged result) would remove that ambiguity without
breaking the old function. Retain partial last-line behavior and CRLF handling.

This was reproduced with 0.829: feeding one newline to a program that calls
`io.fd_read_line(0)` twice produces `len=0 err=[]` for both calls. A minimal
probe is:

```aether
import std.io
import std.string
main() {
    a, ea = io.fd_read_line(0)
    b, eb = io.fd_read_line(0)
    println("first: len=${string.length(a)} err=[${ea}]")
    println("second: len=${string.length(b)} err=[${eb}]")
}
```

Run it with a single newline on stdin, then EOF. The implementation can also
use lower-level byte reads to distinguish EOF today; this is not a reason to
block the demo.

## 2. A public owned JSON deep-clone function

Source: `/home/paul/scm/aether/std/json/module.ae` and `aether_json.c`.

The public API has constructors, setters and strict parsing, but no exported
`json.clone`/deep-copy operation. There is already an internal
`deep_copy_into_arena` in the C implementation. RexxAE's `src/values.ae` currently
obtains an independent value by stringify followed by parse.

An owned clone should survive freeing its source, preserve integer and string
contents (including embedded NUL), work for parsed subtrees as well as roots,
and fail without changing the source. This would remove text conversion from
routine value copying and future compiled-program/session optimizations.

## 3. Public whole-URL parsing and resolution

Source: `/home/paul/scm/aether/std/url/module.ae`.

The current exports cover component encoding/decoding and query parsing.
They do not expose a whole-URL `parse` or relative-reference `resolve` API.
The HTTP implementation necessarily parses URLs internally; the wish is a
reusable public representation, not another independent parser.

The declared calculator service needs scheme, normalized host, effective port,
userinfo presence and path as separate fields. A redirect requires resolution
against the current URL before policy validation. Tests should cover default
ports, IPv6 brackets, mixed-case hosts, userinfo and malformed authorities.
Parsing supplies facts; the host still decides which endpoints are approved.
An allowlist should not depend on ad hoc string-prefix matching.

## 4. Optional terminal line editing

Basic fd line reading exists; I did not find an exported stdlib line editor
with cursor editing, history and completion callbacks. This could be a
`contrib` helper instead of a core std module. It should distinguish submitted
input, EOF and interruption, and fall back cleanly for piped input. Persistent
history should be opt-in rather than an implicit filesystem effect.

This is an ergonomics improvement, not a prerequisite. The current Python
console deliberately keeps native evaluation separate from terminal handling.

## Facilities already available

### New containment follow-up from the calculator adapter

Source inspection of `/home/paul/scm/aether/std/net/aether_http.c` at the cited
commit found that the HTTP client's C dial/pool paths do not call the sandbox
checker used in `/home/paul/scm/aether/std/net/aether_net.c`'s TCP connector.
Please gate HTTP sends, including pooled reuse, on the effective host/port and
recheck every redirect/proxy destination under the current sandbox. A public
`sandbox.check(category, resource)` would also help host adapters express
validation without depending on an internal runtime symbol.

RexxAE's demo currently uses `aether_sandbox_check_slow` solely inside an
installed enforce block, validates a fixed URL, and disables proxies/redirects.
`tests/test_calculator_service.ae` verifies outer deny-all refusal without
opening a socket. End-to-end network behavior still needs the terminal runner;
this source finding is not a reproduced live HTTP escape in this workspace.
No upstream issue was filed for this follow-up.

- `std.io.fd_read_line` and byte reads provide basic terminal input.
- `std.http.client` already provides explicit timeouts, redirect controls,
  TLS verification controls, proxy controls and streaming reads. Streaming
  lets a service enforce a response-size limit while consuming it.
- `std.url` already encodes components and parses queries.
- `std.sandbox.grant_tcp(host, port)` already expresses exact endpoint grants.
- `std.json.parse_strict` already distinguishes parse/OOM/input failures.

The seeks-declaration schema, required/optional approval policy, Rexx session
semantics and calculator function belong to RexxAE and its embedding host.
None requires Aether to implement a Rexx parser or to expose general networking
to the guest.
