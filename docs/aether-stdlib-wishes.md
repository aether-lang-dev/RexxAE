# Aether stdlib requests

These requests arise from the engine and calculator adapters. They concern
public APIs; Rexx parsing, declarations and approval policy remain RexxAE's
responsibility. Source observations refer to Aether commit `7b48889a`.

## HTTP sandbox enforcement and public checks

Gate HTTP sends, pooled connections and redirect/proxy destinations on the
current effective grants. A public `sandbox.check(category, resource)` would
let adapters check authority without an internal runtime symbol.
[Integration status](aether-issues.md#open-http-transport-sandbox-checks)
describes the source finding, current adapter fence and verification limits.

## Owned JSON deep clone

`std/json/module.ae` exposes constructors, setters and parsing, but no public
owned deep copy. The C implementation already contains `deep_copy_into_arena`.
RexxAE's value copying currently serializes and parses to obtain independence.

A clone should work on roots and parsed subtrees, survive freeing its source,
preserve integer and string contents including embedded NUL, and leave the
source unchanged on failure. This would reduce conversion overhead in routine
and session value copying.

## Whole-URL parsing and resolution

`std/url/module.ae` exposes component encoding and query parsing. A public
whole-URL parser and relative-reference resolver would let adapters share the
HTTP implementation's parsing rather than build independent grammars.

Expose scheme, normalized host, effective port, userinfo presence and path.
Cover default ports, bracketed IPv6, mixed-case hosts, malformed authorities
and relative references. Parsing supplies facts; application policy decides
which destinations are approved. The calculator currently uses a deliberately
restricted endpoint grammar and refuses redirects.

## Optional terminal line editing

A `contrib` helper for cursor editing, completion and history would improve the
native REPL. It should distinguish input, EOF and interruption, fall back for
piped input, and make persistent history an explicit filesystem choice.
This is an ergonomics request, not a blocker.

## Already supplied

EOF-aware `io.fd_read_line_status(fd)` is used by the calculator console.
HTTP deadlines, explicit CA files, proxy/redirect controls, streaming reads,
exact TCP grants and strict JSON parsing already support the demo. See the
[calculator guide](calculator.md) for usage and the
[archived review](archive/2026-10-19-stdlib-review.md) for the original EOF probe.
