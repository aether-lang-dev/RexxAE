# Declared-endpoint calculator

This demo uses a calculator service built with TinyWeb and a calculator console importing the actual
compiled RexxAE library. Both endpoints explicitly import Aether's TLS backend
and force `AETHER_PURE_TLS=1` for HTTPS. TLS terminates in the application.
An explicit loopback HTTP mode also supports local testing without certificates.
OpenSSL is used only to generate disposable test certificates.

The core engine still targets installed Aether 0.829.0. This optional demo needs
`std.io.fd_read_line_status`, added by Aether commit
`7b48889abddb9575338d32cbf6e44f468978ce93`. The development compiler at
`/home/paul/scm/aether/build/ae` reports 0.830.0 and includes that commit.
Its library and host artifacts live separately in `build/calculator`, avoiding
mixing compilers with the existing C and Aether consumers.

## Run the integration suite in a terminal

```sh
cd /home/paul/scm/rexxae/RexxAE
python3 tools/test_calculator_tls.py --ae /home/paul/scm/aether/build/ae
cat /home/paul/scm/rexxae/RexxAE/build/calculator/tls-report.json
```

Send back `tls-report.json` and, on failure, the `.build.log`, `.http-server.log`
and `.server.log` beside it when present. No GitHub Actions, cloud account or public listener is needed. The
runner requires Python 3, make, OpenSSL for certificate generation and the
development Aether compiler. It rebuilds everything, runs offline tests, generates
temporary P-256 certificates, starts the server on an unused loopback port and
cleans up its processes and private keys. Unavailable sockets fail the run.

Checks include the native client reaching a loopback HTTP server without a CA;
independent HTTPS arithmetic; malformed and oversized requests;
TLS 1.3 negotiation and TLS 1.2 refusal; untrusted CA and wrong hostname refusal;
the native console downloading and executing the served Rexx module while ignoring ambient proxies;
RexxJS-style aliases; a modified downloaded routine returning its own value;
native rejection of an untrusted CA and GET/POST redirects; and server health after bad
handshakes. Each check is recorded separately. A build or startup failure stops
dependent checks, leaving an overall failed report.

## Local HTTP without SSL

Build the native server and console, then start the calculator service in one terminal:

```sh
make calculator CALC_AE=/home/paul/scm/aether/build/ae
CALC_HTTP=1 ./build/calculator/calculator-service
```

In another terminal, from the repository root:

```sh
CALC_ENDPOINT=http://localhost:8080/calculate \
CALC_PROGRAM=examples/calculator/calculator-local.rexx ./build/calculator/calculator-console
```

No Python, certificates or `CALC_CA` are needed. The checked-in calculator script declares
`http://localhost:8080/calculate` and calls `CALC('add', '0.1', '0.2')`.
It should print `0.3`; continue with `SAY CALC('mul', '6', '7')`, then `:quit`.
Before the script runs, the native console asks for session approval of its
exact HTTP POST request, then separately for GET of the Rexx module. Enter `y` or `yes` at each prompt to grant both; Enter or any other answer
denies execution. `CALC_ENDPOINT` sets the host's endpoint limit, not consent.
`CALC_HTTP=1` explicitly selects HTTP, defaulting to `127.0.0.1:8080`.
`CALC_HOST=localhost` also binds literal `127.0.0.1`. Nonloopback bindings are
refused in this mode. `CALC_PORT` changes the port; update both the script
declaration and `CALC_ENDPOINT` to match.

Calculator console destinations accept only the exact names `localhost` or `127.0.0.1`
and always dial literal `127.0.0.1`, avoiding hostname resolution in this mode.
The service mounts only its exact TCP grant, with no CA-file read grant. Proxy
and redirect refusal, request deadlines and result limits apply to both modes.
There is no automatic downgrade from HTTPS. The GCP workflow below uses HTTPS.

## Offline console and manual HTTPS use

```sh
make calculator-test CALC_AE=/home/paul/scm/aether/build/ae
printf '\nLET x = 40\n= x + 2' | ./build/calculator/calculator-console
```

With no configuration the console mounts no services. Blank lines continue;
EOF exits; an unterminated final line executes once. `= expression` means
`SAY expression`; `:quit` exits. Variables persist across submissions. Each line
is one submission; startup programs may contain multiline Rexx. The existing
Python `make repl` console also supports multiline collection and inspection.

To run a server with your own **ECDSA P-256** PEM key and certificate chain:

```sh
CALC_CERT=/absolute/path/fullchain.pem CALC_KEY=/absolute/path/key.pem \
  CALC_CHECK_CONFIG=1 ./build/calculator/calculator-service
CALC_CERT=/absolute/path/fullchain.pem CALC_KEY=/absolute/path/key.pem \
  ./build/calculator/calculator-service
```

The service reads one module asset at startup: `CALC_MODULE_FILE` defaults to
`examples/calculator/static/calculator.rexx`, relative to the working directory.
It serves only that file at the exact GET path, without exposing a directory.
Restart after changing the asset. Run these local commands from the repository root.

Defaults are `127.0.0.1:8443`. `CALC_HOST` and `CALC_PORT` change the binding.
Startup parses the leaf and key and checks that the public key matches before
binding. These are the defaults when `CALC_HTTP=1` is absent. Certificate chain
trust, name and validity are enforced by clients;
config validation is not a certificate issuance or renewal service.

For a localhost certificate trusted by the CA file you supply:

```sh
CALC_ENDPOINT=https://localhost:8443/calculate \
CALC_CA=/absolute/path/ca.pem \
CALC_PROGRAM=examples/calculator/calculator.rexx ./build/calculator/calculator-console
```

Then enter `SAY CALC('mul', '6', '7')`. The startup example prints `0.3`.
The host limits requests to `CALC_ENDPOINT`; the program's first line must match exactly:

```rexx
/* @seeks http.post https://localhost:8443/calculate */
/* @purpose Remote calculator operations */
/* @seeks http.get /static/calculator.rexx */
REQUIRE "/static/calculator.rexx"
SAY CALC('add', '0.1', '0.2')
```

This is a small declaration convention, not a general SAE manifest parser.
Declarations request access; they cannot grant it. Approval happens before any
startup instruction. Unknown or duplicate capability declarations, a different port or a missing
POST declaration refuse the program. The GET declaration separately requests the
root-relative module URL on that same origin. Endpoint and CA configuration stay in the host
and cannot be changed by script variables or later console comments.

## Permission approval in the native REPL

The console loads and validates the script, then asks before importing the calculator API
or executing any Rexx instruction. The subsequent explicit import binds the API. For example, an illustrative remote endpoint
produces a prompt of this form:

```text
"calculator.rexx" requests:
  HTTP POST https://calculator.example.com:443/calculate

Self-claimed purpose (unverified):
  "Remote calculator operations"

Destination hostname: calculator.example.com
Port: 443
Path: /calculate
Approval covers only this exact scheme, operation, hostname, port and path.
No trust is inherited from a parent domain or sibling subdomains.

Allow for this session? [y/N]
```

The purpose is optional script-supplied text, declared by a single
`/* @purpose text */` comment immediately after the first-line `@seeks` comment.
It is limited to 240 bytes and is never treated as verified identity, evidence
of safety, or permission. Missing purpose is displayed as `(not supplied)`.
The console quotes metadata and escapes controls, quotes, backslashes and
non-ASCII bytes so a purpose or filename cannot emit terminal control sequences.
The full validated destination is displayed separately by the host.

An explicit `y` or `yes` grants the request for this process's REPL session.
Blank input, any other answer, EOF or an input error denies it, and the script
does not execute. Nothing is remembered for a later launch. Approval of
`example.com` never approves `calculator.example.com`, a sibling, a wildcard,
another port, another path, or another scheme. The service's enclosing sandbox
checks still apply after consent; a user response cannot widen an outer fence.

The question requires both terminal stdin and terminal stderr. Piped input must
not answer a script's permission question. For explicit noninteractive host
approval, set `CALC_ENDPOINT` and `CALC_APPROVE_ENDPOINT` to the same
complete POST endpoint, and `CALC_APPROVE_MODULE_URL` to the complete GET URL:

```sh
CALC_ENDPOINT=http://localhost:8080/calculate \
CALC_APPROVE_ENDPOINT=http://localhost:8080/calculate \
CALC_APPROVE_MODULE_URL=http://localhost:8080/static/calculator.rexx \
CALC_PROGRAM=examples/calculator/calculator-local.rexx ./build/calculator/calculator-console </dev/null
```

This is advance approval supplied by the trusted launcher, not an instruction
the Rexx script can set. A nonempty mismatching approval fails closed. Without
advance approval, nonterminal input or redirected stderr refuses startup. The
integration runner supplies exact advance approvals for its generated scripts;
offline tests use real pseudoterminals to exercise interactive yes/no, default
denial, EOF, prompt escaping and session behavior without network access.

The calculator script requests two permissions: POST of calculator operations and
GET of its Rexx module. Both approvals happen before the first Rexx instruction
or network request. POST approval never grants GET, including on the same origin.
The GET prompt explicitly says that the download contains code to be executed.
Additional capabilities requested by downloaded code are refused, never silently
granted. This is a limited calculator convention, not a general manifest format.

## Importing the calculator API

The [calculator script](../examples/calculator/calculator.rexx) states where its
function comes from:

```rexx
/* @seeks http.post https://localhost:8443/calculate */
/* @purpose Remote calculator operations */
/* @seeks http.get /static/calculator.rexx */
REQUIRE "/static/calculator.rexx"
SAY CALC('add', '0.1', '0.2')
```

The relative reference resolves against the scheme, hostname and explicit port of
`CALC_ENDPOINT`: here, `https://localhost:8443/static/calculator.rexx`. TinyWeb serves
that URL from [static/calculator.rexx](../examples/calculator/static/calculator.rexx),
which defines and exports `CALC`. The console downloads and validates that Rexx
source, binds its export, then executes the downloaded routine whenever `CALC`
is called. The routine constructs the POST request and reads the result. It is
not replaced with an installed native calculation. Permissions authorize effects;
`REQUIRE` identifies the code that supplies the function.

`AS` follows RexxJS's function-prefix rules:

| Import | Exported name |
|---|---|
| `REQUIRE "/static/calculator.rexx"` | `CALC` |
| `REQUIRE "/static/calculator.rexx" AS remote` | `remote_CALC` |
| `REQUIRE "/static/calculator.rexx" AS remote_` | `remote_CALC` |
| `REQUIRE "/static/calculator.rexx" AS remote_(.*)` | `remote_CALC` |

For example, after the same declarations:

```rexx
REQUIRE "/static/calculator.rexx" AS remote
SAY remote_CALC('add', '0.1', '0.2')
```

`AS CALC` would export `CALC_CALC`. Imported functions and the validated downloaded
source remain available during the console session; further imports use that
cached source. Restart to fetch an updated module. No version pin or signature
verification is implemented yet.

This first downloaded-module profile accepts exactly `/static/calculator.rexx`,
with no authority replacement, traversal, query or alternate path. Downloads
are limited to 16 KiB and must begin with the export and POST declarations shown
in the served source. Extra capability or export declarations and initialization
code are refused. Each call runs in an independent binary-engine context with
three arguments and a 100,000-step budget. Its sole mounted function is
`HTTP_POST('/calculate', object)`; that adapter validates the calculator JSON
contract and uses the approved POST endpoint. The downloaded routine receives
no application registry, filesystem access, nested module resolver or ADDRESS
service. Mutable module variables do not persist between calls.

The legacy `REQUIRE "calculator"` resolver remains available for an installed
Aether adapter, but these examples use the explicit HTTP source above.
The engine itself emits a FUNCTION request named `REQUIRE` with the reference
and optional alias as strings. Only the calculator application supplies network
resolution; the core engine remains capability-empty. Dynamic references and
named `lib=...` forms are outside this parser profile.

RexxJS also uses `AS` to rename ADDRESS modules to an exact lowercase name and
refuses `(.*)` patterns for those modules. The shared naming helper and tests
cover those rules; this console provides a function module only.

## Wire contract and containment

`POST /calculate` accepts exactly three JSON string fields:
`{"op":"add","a":"0.1","b":"0.2"}`. Success returns
`{"result":"0.3"}`. Operators are `add`, `sub`, `mul`, `div`. Arithmetic uses
`std.decimal`; division rounds to 16 decimal places. Each operand is at most
64 bytes, with optional minus and a decimal fraction; exponents are refused.
Wrong types, extra fields and division by zero return 400. Application request
bodies over 512 bytes return 413. `/health` returns a small JSON status.

Guests see only `CALC(operation, left, right)`, requiring three strings. They
cannot supply URLs, methods, headers, CA paths, proxies or redirect policy.
ADDRESS remains vetoed. Remote endpoints require canonical HTTPS; local testing
also accepts HTTP on the two loopback names above. Every URL requires an explicit
port and exactly `/calculate`. This deliberately restricted grammar accepts
lowercase DNS names and IPv4, and refuses userinfo, wildcard hosts, IPv6, queries,
fragments and encoded authorities. It does not pretend to implement general URL
normalization. Redirects and proxies are disabled, certificate verification stays
enabled, each request has a five-second deadline and streamed responses are
limited to 512 bytes. Calculator POST results remain data. Rexx source is fetched only through the
separately approved module GET, with the same proxy, redirect, TLS and timeout
policy and a 16 KiB streaming limit.

For HTTPS, the adapter adds an exact TCP grant and one literal CA-file read grant inside
`sandbox.enforce`. The source audit found that `std.http.client`'s C dial path
lacks the sandbox gate in `std.net.tcp_connect_raw`. Until Aether supplies that
gate, the adapter explicitly calls the runtime's `aether_sandbox_check_slow`
**only inside its installed enforce block**, before requesting transport. This
internal ABI dependency is confined to the example host. Native specs confirm
an enclosing deny-all container still refuses the service. It is not a fix for
other applications calling the HTTP client directly.

Console submissions have a 100,000-step budget. Discarding a submission cannot
undo network requests already made. There is no per-session request quota yet.
The server's 512-byte validation occurs after TinyWeb has received the body;
it is not a 512-byte transport allocation cap. Public deployment still needs
an ingress request/rate budget and measured resource limits. No arbitrary Rexx
source is evaluated by the server.

## Always-on GCP service and native REPL

**Service URL: to be announced.** The deployment model is one GCP VM running
the Aether TinyWeb calculator continuously under systemd. Clients connect to
that existing HTTPS service; they do not start a local server. The native
Aether console loads the compiled RexxAE library, runs a Rexx startup script
and then accepts further Rexx input. This client workflow uses no Python.

The README's [GCP REPL commands](../README.md#always-on-gcp-calculator-through-the-native-repl)
prepare `build/calculator/gcp-calculator.rexx` from the checked-in
`examples/calculator/calculator.rexx`, replacing its localhost declaration with
the announced endpoint. Set `CALC_ENDPOINT` to exactly that same URL, including
the explicit port and `/calculate` path, and set `CALC_CA` to an absolute path
to a trust bundle that validates the VM's certificate chain. The sample
`calculator.example.com` hostname is a placeholder, not the deployed service.

After its `REQUIRE "/static/calculator.rexx"` import, the startup script's `SAY CALC('add', '0.1', '0.2')` should print `0.3` after
calling the VM. Subsequent `CALC` calls in the REPL use the same approved
service; ordinary Rexx variables and arithmetic execute locally. The console
waits for one submission per line without a prompt. Use `:quit` or EOF to exit.
The declaration requests the service, and host configuration bounds it. The
user's session approval (or exact explicit advance approval) authorizes it;
changing only the declaration or endpoint limit refuses startup. A script cannot choose another
destination by passing a URL to `CALC`.

### VM service setup

`deploy/calculator/rexxae-calculator.service` and `calculator.env.example` are
reviewable templates, not an installed service. Build on the target architecture
and compatible OS, copy the server binary to `/opt/rexxae/bin/calculator-service`,
copy `examples/calculator/static/calculator.rexx` to
`/opt/rexxae/share/calculator.rexx` (the template sets `CALC_MODULE_FILE` to that
path), create the `rexxcalc` service account, and install the config and P-256 keypair
under `/etc/rexxae`. Keep the key readable only by root and the service group.
The unit runs without root, with a read-only filesystem, a private temporary
directory and CPU/memory/task limits. Adjust limits after measurement.

Binding `0.0.0.0:8443` requires a deliberate host/cloud firewall rule. For an
initial demo restrict source addresses to your client. Real use needs a domain
and a trusted P-256 certificate chain; arrange renewal and restart the service
after certificate replacement. Never deploy the generated test certificates
as public trust anchors. Validate the real hostname and chain with the native
client before opening access more widely. Authentication and Internet-facing
rate controls are not implemented by this calculator sample.

An eligible GCP `e2-micro` VM is a possible small host. Google's Free Tier covers
eligible VM time in specified US regions and limited standard disk/egress, but
that does not make every component free: a standard VM's external IPv4 address
is separately priced. Check the current [Free Tier limits](https://docs.cloud.google.com/free/docs/free-cloud-features)
and [network pricing](https://cloud.google.com/vpc/network-pricing) before choosing
a project, region, address and DNS arrangement. No VM, firewall rule, account,
certificate order or billable resource is created by these files.
