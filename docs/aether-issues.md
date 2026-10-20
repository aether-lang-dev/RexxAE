# Aether integration status

See the [README](../README.md#build-and-test) for supported compiler versions
and validation totals. Select and check the executable, not just the source
checkout revision; rebuild libraries and consumers together when switching it.

## Open: HTTP transport sandbox checks

Inspection of Aether's `std/net/aether_http.c` at commit `7b48889a` found that
its C dial/pool paths lack the sandbox gate used by the TCP connector. This is
source evidence; a live HTTP escape has not been reproduced in this workspace.

The calculator adapter validates exact destinations, disables redirects and
proxies, and calls the internal `aether_sandbox_check_slow` only inside an
installed enforcement block before transport. Its GET and POST services cannot
widen an enclosing sandbox. Regression coverage is in
[test_calculator_service.ae](../tests/test_calculator_service.ae) and
[test_downloaded_calculator.ae](../tests/test_downloaded_calculator.ae).
Live transport verification requires the [terminal runner](calculator.md#run-the-integration-suite-in-a-terminal).

The upstream request is to gate HTTP sends, pooled reuse and every redirect or
proxy destination under the effective sandbox. A public permission-check API
would also remove the adapter's dependency on an internal runtime symbol.
No upstream issue has been filed for this follow-up.

## Resolved issues

| Issue | Status and retained check |
|---|---|
| Trusted sandbox-call lifetime | Fixed by the tested toolchain. [Standalone reproducer](../tests/repros/trusted_service_repeat.ae) and [regressions](../tests/test_trusted_service.ae) cover repeated calls, restored authority and outer denial. Run `make containment memcheck`. |
| Compiler/stdlib `@heap` annotation mismatch | Resolved; no engine workaround required. Library builds exercise the declarations. |
| EOF-aware line input | `io.fd_read_line_status(fd)` supplies `(line, eof, err)`; [console tests](../tests/test_calculator_console.py) cover blank lines, EOF, CRLF and partial final lines. |

Old compiler versions, failure traces and standalone reproduction commands are
in the [archived toolchain findings](archive/2026-10-19-toolchain-findings.md).
Remaining API requests are in [stdlib wishes](aether-stdlib-wishes.md).
