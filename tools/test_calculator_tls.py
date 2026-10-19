#!/usr/bin/env python3
"""Terminal-only TLS integration runner. Never skips unavailable sockets.

Run from any directory. A JSON report and server log remain under build/calculator.
Only loopback listeners are opened; no cloud resources or public endpoints are used.
"""
import argparse
import http.client
import http.server
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def environment(**settings):
    env = {k: v for k, v in os.environ.items() if not k.startswith('CALC_')}
    env.update(settings)
    return env


def certificate(directory, name):
    cert, key = directory / f'{name}.pem', directory / f'{name}.key'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt',
                    'ec_paramgen_curve:prime256v1', '-keyout', str(key), '-out', str(cert),
                    '-days', '2', '-nodes', '-subj', '/CN=localhost',
                    '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
                    '-addext', 'basicConstraints=critical,CA:TRUE'],
                   check=True, capture_output=True, text=True, timeout=30)
    key.chmod(0o600)
    return cert, key


def tls_context(cert):
    ctx = ssl.create_default_context(cafile=str(cert))
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    return ctx


def request(port, ctx, path='/health', body=None):
    connection = http.client.HTTPSConnection('127.0.0.1', port, context=ctx, timeout=6)
    try:
        connection.connect()
        version = connection.sock.version()
        connection.request('POST' if body is not None else 'GET', path, body=body,
                           headers={'Content-Type': 'application/json', 'Connection': 'close'})
        response = connection.getresponse()
        return response.status, response.read(2048).decode(), version
    finally:
        connection.close()


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ae', default='/home/paul/scm/aether/build/ae')
    parser.add_argument('--report', type=Path, default=ROOT / 'build/calculator/tls-report.json')
    args = parser.parse_args()
    args.report = args.report.resolve()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {'passed': False, 'compiler': args.ae, 'checks': [],
              'note': 'Checks explicit loopback HTTP and HTTPS. OpenSSL creates test certificates; HTTPS selects pure Aether TLS 1.3.'}

    def check(name, action):
        print(f'CHECK {name}', flush=True)
        start = time.monotonic()
        try:
            detail = action()
            report['checks'].append({'name': name, 'passed': True,
                                     'seconds': round(time.monotonic() - start, 3), 'detail': detail})
            print('  PASS', flush=True)
            return True
        except Exception as error:
            report['checks'].append({'name': name, 'passed': False,
                                     'seconds': round(time.monotonic() - start, 3), 'error': str(error)})
            print(f'  FAIL: {error}', flush=True)
            return False

    try:
        version = subprocess.run([args.ae, 'version'], text=True, capture_output=True, check=True, timeout=20)
        report['compiler_version'] = version.stdout
        report['aether_commit'] = subprocess.run(
            ['git', '-C', '/home/paul/scm/aether', 'rev-parse', 'HEAD'],
            text=True, capture_output=True, timeout=10).stdout.strip()

        def build():
            p = subprocess.run(['make', '-B', 'calculator-test', f'CALC_AE={args.ae}'], cwd=ROOT,
                               capture_output=True, text=True, timeout=300)
            build_log = args.report.with_suffix('.build.log')
            build_log.write_text(p.stdout + p.stderr)
            require(p.returncode == 0, f'build/offline tests failed; see {build_log}')
            return str(build_log)

        if not check('build and offline native tests', build):
            return 1

        def sockets():
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                return probe.getsockname()[1]

        if not check('loopback socket permission (required)', sockets):
            return 1

        with tempfile.TemporaryDirectory(prefix='rexxae-calc-tls-') as temp:
            directory = Path(temp)

            def local_http():
                port = sockets()
                endpoint = f'http://localhost:{port}/calculate'
                program = directory / 'local.rexx'
                program.write_text(f"/* @seeks http.post {endpoint} */\n/* @seeks http.get /static/calculator.rexx */\nREQUIRE \"/static/calculator.rexx\"\nSAY CALC('add','0.1','0.2')\n")
                log_path = args.report.with_suffix('.http-server.log')
                report['http_server_log'] = str(log_path)
                with log_path.open('w') as log:
                    server = subprocess.Popen([str(ROOT / 'build/calculator/calculator-service')], cwd=ROOT,
                                              env=environment(CALC_HTTP='1', CALC_HOST='localhost', CALC_PORT=str(port)),
                                              stdout=log, stderr=subprocess.STDOUT)
                    try:
                        deadline = time.monotonic() + 10
                        last = None
                        while time.monotonic() < deadline:
                            if server.poll() is not None:
                                raise AssertionError(f'HTTP server exited {server.returncode}; see {log_path}')
                            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                            try:
                                connection.request('GET', '/health')
                                response = connection.getresponse()
                                body = response.read(1024).decode()
                                require(response.status == 200 and json.loads(body) == {'status': 'ok', 'tls': 'none'}, body)
                                break
                            except (OSError, http.client.HTTPException) as error:
                                last = error
                                time.sleep(0.1)
                            finally:
                                connection.close()
                        else:
                            raise AssertionError(f'HTTP not ready: {last}; see {log_path}')
                        p = subprocess.run([str(ROOT / 'build/calculator/calculator-console')], cwd=ROOT,
                                           env=environment(CALC_ENDPOINT=endpoint, CALC_APPROVE_ENDPOINT=endpoint,
                                                           CALC_APPROVE_MODULE_URL=endpoint.removesuffix('/calculate') + '/static/calculator.rexx', CALC_PROGRAM=str(program),
                                                           HTTP_PROXY='http://127.0.0.1:1', http_proxy='http://127.0.0.1:1',
                                                           NO_PROXY='', no_proxy=''),
                                           input="\nSAY CALC('mul','6','7')", capture_output=True, text=True, timeout=20)
                        require(p.returncode == 0 and p.stdout == '0.3\n42\n' and p.stderr == '',
                                f'code={p.returncode} stdout={p.stdout!r} stderr={p.stderr!r}')
                        return {'endpoint': endpoint, 'output': p.stdout, 'ca_file': 'not required'}
                    finally:
                        server.terminate()
                        try:
                            server.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            server.kill()
                            server.wait(timeout=5)

            check('loopback HTTP server and native Rexx client without certificates or CA', local_http)
            cert, key = certificate(directory, 'localhost')
            untrusted, _ = certificate(directory, 'untrusted')
            port = sockets()
            endpoint = f'https://127.0.0.1:{port}/calculate'
            program = directory / 'client.rexx'
            program.write_text(f"/* @seeks http.post {endpoint} */\n/* @seeks http.get /static/calculator.rexx */\nREQUIRE \"/static/calculator.rexx\"\nSAY CALC('add','0.1','0.2')\n")
            server_log = args.report.with_suffix('.server.log')
            report['server_log'] = str(server_log)
            with server_log.open('w') as log:
                server = subprocess.Popen([str(ROOT / 'build/calculator/calculator-service')], cwd=ROOT,
                                          env=environment(CALC_CERT=str(cert), CALC_KEY=str(key),
                                                          CALC_HOST='127.0.0.1', CALC_PORT=str(port),
                                                          AETHER_PURE_TLS='0'),
                                          stdout=log, stderr=subprocess.STDOUT)
                try:
                    ctx = tls_context(cert)

                    def ready():
                        deadline = time.monotonic() + 15
                        last = None
                        while time.monotonic() < deadline:
                            if server.poll() is not None:
                                raise AssertionError(f'server exited {server.returncode}; see {server_log}')
                            try:
                                status, body, version = request(port, ctx)
                                require(status == 200 and json.loads(body)['status'] == 'ok', body)
                                require(version == 'TLSv1.3', version)
                                return {'tls': version, 'health': json.loads(body)}
                            except (OSError, http.client.HTTPException) as error:
                                last = error
                                time.sleep(0.15)
                        raise AssertionError(f'HTTPS not ready: {last}; see {server_log}')

                    if not check('TinyWeb HTTPS health and negotiated TLS 1.3', ready):
                        return 1

                    def arithmetic():
                        for op, a, b, expected in [('add', '0.1', '0.2', '0.3'),
                                                   ('sub', '-1', '2.5', '-3.5'),
                                                   ('mul', '6', '7', '42'),
                                                   ('div', '1', '3', '0.3333333333333333')]:
                            status, text, _ = request(port, ctx, '/calculate', json.dumps(dict(op=op, a=a, b=b)))
                            require(status == 200 and json.loads(text) == {'result': expected}, text)
                    check('HTTPS decimal arithmetic', arithmetic)

                    def module_source():
                        status, text, _ = request(port, ctx, '/static/calculator.rexx')
                        require(status == 200 and text == (ROOT / 'examples/calculator/static/calculator.rexx').read_text(),
                                f'module GET {status}: {text!r}')
                    check('TinyWeb serves the actual calculator Rexx module', module_source)

                    def bad_requests():
                        for body, expected in [('{', 400), ('[]', 400),
                                               ('{"op":"add","a":1,"b":"2"}', 400),
                                               ('{"op":"div","a":"1","b":"0"}', 400),
                                               ('x' * 513, 413)]:
                            status, text, _ = request(port, ctx, '/calculate', body)
                            require(status == expected and 'error' in json.loads(text), f'{status}: {text}')
                    check('malformed, typed and oversized HTTPS requests denied', bad_requests)

                    def rejects_untrusted():
                        try:
                            request(port, tls_context(untrusted))
                        except ssl.SSLCertVerificationError:
                            return
                        raise AssertionError('untrusted server certificate was accepted')
                    check('untrusted certificate rejected by independent client', rejects_untrusted)

                    def rejects_wrong_name():
                        try:
                            with socket.create_connection(('127.0.0.1', port), timeout=6) as sock:
                                with ctx.wrap_socket(sock, server_hostname='wrong.invalid'):
                                    pass
                        except ssl.SSLCertVerificationError:
                            return
                        raise AssertionError('wrong hostname was accepted')
                    check('wrong certificate hostname rejected', rejects_wrong_name)

                    def rejects_tls12():
                        older = ssl.create_default_context(cafile=str(cert))
                        older.minimum_version = older.maximum_version = ssl.TLSVersion.TLSv1_2
                        try:
                            request(port, older)
                        except (ssl.SSLError, ConnectionError, http.client.HTTPException):
                            return
                        raise AssertionError('server accepted TLS 1.2')
                    check('TLS 1.2 refused', rejects_tls12)

                    def console(cafile=cert, program_file=program, input_text='', url=endpoint):
                        p = subprocess.run([str(ROOT / 'build/calculator/calculator-console')], cwd=ROOT,
                                           env=environment(CALC_CA=str(cafile), CALC_ENDPOINT=url, CALC_APPROVE_ENDPOINT=url,
                                                           CALC_APPROVE_MODULE_URL=url.removesuffix('/calculate') + '/static/calculator.rexx',
                                                           CALC_PROGRAM=str(program_file), AETHER_PURE_TLS='0',
                                                           HTTPS_PROXY='http://127.0.0.1:1', https_proxy='http://127.0.0.1:1',
                                                           HTTP_PROXY='http://127.0.0.1:1', http_proxy='http://127.0.0.1:1',
                                                           NO_PROXY='', no_proxy=''),
                                           input=input_text, capture_output=True, text=True, timeout=20)
                        return p

                    def native_success():
                        p = console(input_text="\nLET total = CALC('mul','6','7')\nSAY total")
                        require(p.returncode == 0 and p.stdout == '0.3\n42\n' and not p.stderr,
                                f'code={p.returncode} stdout={p.stdout!r} stderr={p.stderr!r}')
                    check('native Rexx binary consumer, downloaded CALC, EOF and proxy isolation', native_success)

                    def native_alias():
                        alias_program = directory / 'alias.rexx'
                        alias_program.write_text(program.read_text().replace('REQUIRE \"/static/calculator.rexx\"',
                                                                            'REQUIRE \"/static/calculator.rexx\" AS remote').replace('SAY CALC(', 'SAY remote_CALC('))
                        p = console(program_file=alias_program, input_text="SAY remote_CALC('mul','6','7')")
                        require(p.returncode == 0 and p.stdout == '0.3\n42\n' and not p.stderr,
                                f'{p.stdout!r} {p.stderr!r}')
                    check('downloaded module AS uses RexxJS export-prefix semantics', native_alias)

                    def native_untrusted():
                        p = console(cafile=untrusted)
                        require(p.stdout == '' and p.stderr != '', f'untrusted CA result: {p.stdout!r} {p.stderr!r}')
                        return p.stderr
                    check('native pure TLS client refuses untrusted CA', native_untrusted)

                    # A hostile HTTPS endpoint must not cause a second request.
                    class Redirect(http.server.BaseHTTPRequestHandler):
                        requests = 0
                        mode = 'post-redirect'
                        downloads = 0

                        def do_POST(self):
                            type(self).requests += 1
                            self.rfile.read(int(self.headers.get('Content-Length', 0)))
                            self.send_response(302)
                            self.send_header('Location', f'https://127.0.0.1:{port}/health')
                            self.send_header('Content-Length', '0')
                            self.end_headers()

                        def do_GET(self):
                            type(self).downloads += 1
                            if type(self).mode == 'get-redirect':
                                self.send_response(302)
                                self.send_header('Location', f'https://127.0.0.1:{port}/static/calculator.rexx')
                                self.send_header('Content-Length', '0')
                                self.end_headers()
                                return
                            payload = (ROOT / 'examples/calculator/static/calculator.rexx').read_bytes()
                            if type(self).mode == 'modified-module':
                                payload = b"/* @exports CALC */\n/* @seeks http.post /calculate */\nCALC: PROCEDURE\nRETURN 'downloaded-code-executed'\n"
                            self.send_response(200)
                            self.send_header('Content-Length', str(len(payload)))
                            self.end_headers()
                            self.wfile.write(payload)

                        def log_message(self, *args):
                            pass

                    def native_redirect(mode='post-redirect'):
                        Redirect.mode = mode
                        Redirect.requests = Redirect.downloads = 0
                        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Redirect) as fixture:
                            fixture.daemon_threads = True
                            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                            tls.minimum_version = ssl.TLSVersion.TLSv1_3
                            tls.load_cert_chain(cert, key)
                            fixture.socket = tls.wrap_socket(fixture.socket, server_side=True)
                            worker = threading.Thread(target=fixture.serve_forever, daemon=True)
                            worker.start()
                            try:
                                url = f'https://127.0.0.1:{fixture.server_port}/calculate'
                                redirect_program = directory / 'redirect.rexx'
                                redirect_program.write_text(f"/* @seeks http.post {url} */\n/* @seeks http.get /static/calculator.rexx */\nREQUIRE \"/static/calculator.rexx\"\nSAY CALC('add','1','2')\n")
                                p = console(program_file=redirect_program, url=url)
                                if mode == 'modified-module':
                                    require(p.stdout == 'downloaded-code-executed\n' and not p.stderr,
                                            f'{p.stdout!r} {p.stderr!r}')
                                else:
                                    require(p.stdout == '' and 'HTTP status 302' in p.stderr,
                                            f'{p.stdout!r} {p.stderr!r}')
                                expected_posts = 1 if mode == 'post-redirect' else 0
                                require(Redirect.requests == expected_posts and Redirect.downloads == 1,
                                        f'{Redirect.requests} POST, {Redirect.downloads} GET requests')
                                return p.stderr
                            finally:
                                fixture.shutdown()
                                worker.join(timeout=5)
                    check('native calculator refuses POST redirect to a different service', native_redirect)
                    check('native module loader refuses GET redirect', lambda: native_redirect('get-redirect'))
                    check('native console executes modified downloaded code without a native CALC substitute',
                          lambda: native_redirect('modified-module'))
                    check('TinyWeb remains healthy after denied handshakes', ready)
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
        report['passed'] = all(item['passed'] for item in report['checks'])
        return 0 if report['passed'] else 1
    except Exception as error:
        report['runner_error'] = str(error)
        report['traceback'] = traceback.format_exc()
        print(report['traceback'], flush=True)
        return 1
    finally:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(f"{'PASS' if report['passed'] else 'FAIL'} — report: {args.report}", flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
