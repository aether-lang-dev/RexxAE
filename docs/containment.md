# RexxAE containment contract

An application can own filesystem, network and process authority without
passing it to Rexx. RexxAE follows Aether's native-bindings containment model:
Rexx has no ambient system API. Its only effect routes are explicit FUNCTION
and COMMAND events, and the host decides whether each request is mounted and
valid. A context is a data-only interpreter, not a native execution namespace.

The design references are Aether's
`/home/paul/scm/aether/docs/containment-sandbox.md` and sae's
`/home/paul/scm/sae/docs/architecture.md`, `docs/page-services.md`,
`services/files/module.ae`, `tests/check_layers.sh`, and
`tests/spec_globals.ae`. The sae precedents carried here
are absent ungranted bindings, a service per effect, exact import/surface
checks, typed boundary validation and a runtime service fence beneath its
own policy. sae's planned entry-wide runtime enforcement and separate-process
containment are not assumed to be finished or inherited by RexxAE.

## Authority flow

| Boundary | Held by |
|---|---|
| Engine's native dependencies | Capability-empty library builds, @pure entry points, reviewed import list. |
| Guest builtin surface | `tests/guest_functions.json`, checked against the actual builtin name lists. New names require review. |
| Functions a context can request | Host-only registration; one context does not inherit another's registry. |
| Valid arguments/resources | The service gate checks types, arity, logical keys and resources before acting. |
| ADDRESS environments | Host router allowlist. An unmounted environment is vetoed, never dispatched to a shell by default. |
| Aether runtime authority | `sandbox.enforce` around every step, reply and dispatch; nested scopes intersect. |
| Deliberately injected privileged operation | Named trusted Aether service call, with its own narrow runtime fence. |
| Host lexical state | `seal except`/`hide` around the hosting scope; guest values never expose native state or handles. |

FUNCTION errors use reply_value's
error argument. COMMAND vetoes return a nonzero RC/ERRORTEXT through reply.
Ordinary script assignments, including names such as `policy.fs` or
`h.READ_CONFIG`, affect only script variables. They cannot change the registry,
grants, native symbols or the host's routing policy. Calling a dotted property
is not an escape to an Aether function or a JavaScript constructor.

## Executable example and escape probes

`tests/test_containment.ae` imports the **compiled** Rexx library, without an
engine source import. It is built and run against both self-contained and
shared-runtime artifacts. The surrounding application can read the private
fixture; the deny-all worker cannot. It injects READ_CONFIG, which accepts one
string key, `public`. Filesystem paths, traversal strings and coercible arrays
are refused. Only the logical public configuration is returned.

`examples/services/config.ae` is the injected effect service. Its imports are
pinned to file/sandbox/map/string; @no_net and @no_os prevent a transitive
call into those effects. It validates the key, then performs its fixed file
read inside a service-specific fs_read grant. Trusting it cannot widen an
outer sandbox that already denied that read. The outer hosting scope is sealed
before entering the trusted enforce callback; trusted names may only be called
inside that callback, not passed around as values.

Each step/event runs in a fresh sealed deny-all enforcement frame, with the
same host-owned grants and service routing. Independent trusted-service
regressions also exercise repeated calls within one long-lived frame, checking
restored authority and refusal by an enclosing sandbox. See
[toolchain status](aether-issues.md) for resolved defects and retained checks.

The test gate deliberately also mounts broad **probe-only** wrappers for file,
environment, process and socket access. Those wrappers are not trusted and
run under deny-all; every attempted acquisition is refused and audited. They
are test adversaries, not recommended application bindings. Production hosts
should leave those bindings unregistered.

The binary containment specs cover:

- Positive host file access and the injected service's successful read.
- Unmounted functions, native names, loaders and dynamic constructor attempts.
- Direct file, environment, process and socket requests, including traversal.
- ADDRESS shell/socket attempts and nonzero refusal RCs.
- Registry/policy spoofing through guest object fields and dynamic CALL names.
- Service argument type spoofing and unapproved logical keys.
- Denials inside nested routines and suspended PARSE expressions.
- PROCEDURE/EXPOSE spoofing, mounted service resumes and restored scope isolation.
- Nested grants, frozen-grant mutation and attempted widening through trust.
- Context registry isolation, inaccessible host lexical state and bounded loops.
- Host session continuation retaining mounted services while preserving deny-all authority.

[Trusted-service specs](../tests/test_trusted_service.ae) also run without
the engine. They assert repeated reads in one frame, restoration after success
and early refusal, and repeated vetoes by an enclosing sandbox. They run in
`make containment` and under Valgrind in `make memcheck`.

The socket positive control asserts an **allowed Aether audit decision** for
one endpoint and a denial for another port. This execution environment refuses
socket creation at the OS level; a successful real connection is not claimed.
Denial tests inspect the audit trail so an OS failure cannot masquerade as an
Aether permission veto. Other tests assert exact host dispatch counts and
that no forbidden command marker file appears.

```sh
make containment
make memcheck
```

The C/ctypes protocol uses the same explicit boundary, but C hosts must provide
their own service policy/enforcement; Aether lexical directives do not travel
into C or Python. The Python example is a small functional harness, not an
OS sandbox for arbitrary Python code.

## Compiler guards and observed gaps

All public engine entry points are @pure. Builds pass no --with grants.
The containment checker verifies those tags, the reviewed guest surface and
engine/service import boundaries. Negative compilation probes check
fs/net/os gates, direct foreign symbols, direct and transitive @pure violations,
sealed reads/mutations/nested reads, escaped trusted-function values, and
trusting an extern C function. A failed probe must contain the expected
permission diagnostic; unrelated syntax/build failures do not count as denials.

Untagged std.file calls compiled under --emit=lib without an fs grant on the
inspected toolchains. The broad std.fs import is rejected. RexxAE therefore does not rely on that gate alone: engine imports
are pinned without std.file, public entry points are @pure, and runtime
backstops are tested independently. Both direct and transitive file.read
calls from @pure probes are rejected.

## Practical limits

This is a language/service authority boundary inside the host process.
A native memory-safety bug in the interpreter or its dependencies is not
contained by these checks. OS-process isolation remains the stronger boundary
for that threat, as sae's architecture also explains. Arbitrary handwritten
native externs in a trusted application can bypass stdlib checks; guests cannot
declare or invoke them through Rexx syntax.

Instruction budgets let the host regain control from loops and recursion is
bounded. Parsing and expression internals are not timed; complete heap, source,
wall-clock and response-size quotas remain work. The current tests do not
prove those resource guarantees, cross-thread isolation, or every platform's
runtime implementation. No listener or external process is needed by the
Rexx engine itself.
