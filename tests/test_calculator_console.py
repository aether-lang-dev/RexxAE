"""Offline checks of the Aether binary host, including the new EOF API."""
import os
from pathlib import Path
import select
import subprocess
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / 'build/calculator/console'


def run_console(source='', settings=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('CALC_')}
    env.update(settings or {})
    return subprocess.run([str(CONSOLE)], input=source, text=True, env=env,
                          capture_output=True, timeout=15)


class ConsoleTests(unittest.TestCase):
    def test_empty_eof(self):
        p = run_console()
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, '', ''))

    def test_blank_crlf_and_partial_final_line(self):
        p = run_console('\n\r\nLET total = 40\r\n\n= total + 2')
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, '42\n', ''))

    def test_unmounted_function(self):
        p = run_console("SAY CALC('add','1','2')\nSAY 'alive'\n")
        self.assertIn('unknown or unavailable function', p.stderr.lower())
        self.assertEqual(p.stdout, 'alive\n')

    def test_address_is_vetoed(self):
        p = run_console("ADDRESS SYSTEM 'touch /tmp/rexxae-should-not-exist'\nSAY RC\n")
        self.assertEqual(p.stdout, '13\n')
        self.assertEqual(p.stderr, '')

    def test_loop_budget_recovers_session(self):
        p = run_console('LET x = 7\nDO FOREVER; END\nSAY x\n')
        self.assertIn('instruction limit', p.stderr)
        self.assertEqual(p.stdout, '7\n')

    def test_missing_preflight_configuration(self):
        p = run_console(settings={'CALC_ENDPOINT': 'https://localhost:8443/calculate'})
        self.assertEqual(p.returncode, 1)
        self.assertIn('required', p.stderr)

    def test_wrong_declaration_runs_no_source(self):
        with tempfile.TemporaryDirectory() as d:
            program = Path(d) / 'client.rexx'
            program.write_text("/* @seeks http.post https://localhost:9999/calculate */\nSAY 'ran'\n")
            p = run_console(settings={'CALC_ENDPOINT': 'https://localhost:8443/calculate',
                                      'CALC_CA': '/no/such/ca.pem', 'CALC_PROGRAM': str(program)})
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, '')
        self.assertIn('exact host-approved', p.stderr)

    def test_argument_types_and_operators_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            program = Path(d) / 'client.rexx'
            program.write_text('/* @seeks http.post https://localhost:8443/calculate */\n')
            p = run_console("SAY CALC('add', {url:'evil'}, '2')\nSAY CALC('exec', '1', '2')\nSAY 'alive'\n",
                            {'CALC_ENDPOINT': 'https://localhost:8443/calculate',
                             'CALC_APPROVE_ENDPOINT': 'https://localhost:8443/calculate',
                             'CALC_CA': '/no/such/ca.pem', 'CALC_PROGRAM': str(program)})
        self.assertIn('requires three strings', p.stderr)
        self.assertIn('unknown operation', p.stderr)
        self.assertEqual(p.stdout, 'alive\n')

    def test_local_http_mount_needs_no_ca(self):
        with tempfile.TemporaryDirectory() as d:
            program = Path(d) / 'local.rexx'
            program.write_text('/* @seeks http.post http://localhost:8080/calculate */\n')
            p = run_console("SAY CALC('exec', '1', '2')\nSAY 'alive'\n",
                            {'CALC_ENDPOINT': 'http://localhost:8080/calculate',
                             'CALC_APPROVE_ENDPOINT': 'http://localhost:8080/calculate',
                             'CALC_PROGRAM': str(program)})
        self.assertEqual(p.returncode, 0)
        self.assertIn('unknown operation', p.stderr)
        self.assertEqual(p.stdout, 'alive\n')

    def test_remote_http_preflight_runs_no_script(self):
        with tempfile.TemporaryDirectory() as d:
            program = Path(d) / 'remote.rexx'
            program.write_text("/* @seeks http.post http://example.com:8080/calculate */\nSAY 'ran'\n")
            p = run_console(settings={'CALC_ENDPOINT': 'http://example.com:8080/calculate',
                                      'CALC_PROGRAM': str(program)})
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, '')
        self.assertIn('plain HTTP is restricted', p.stderr)


class ConsentTests(unittest.TestCase):
    endpoint = 'https://calculator.example.com:443/calculate'

    def program(self, directory, purpose='Remote calculator operations'):
        path = Path(directory) / 'calculator.rexx'
        path.write_text(f'/* @seeks http.post {self.endpoint} */\n'
                        f'/* @purpose {purpose} */\nSAY "SCRIPT_STARTED"\n')
        return path

    def settings(self, path, **extra):
        return {'CALC_ENDPOINT': self.endpoint, 'CALC_PROGRAM': str(path),
                'CALC_CA': '/host-configured-ca.pem', **extra}

    def test_piped_yes_cannot_authorize_or_execute_a_script(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.program(directory)
            p = run_console('y\nSAY "INJECTED"\n', self.settings(path))
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout, '')
        self.assertIn('terminal stdin and stderr', p.stderr)
        self.assertIn('script was not executed', p.stderr)

    def test_exact_advance_approval_for_headless_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.program(directory)
            p = run_console('SAY "NEXT"\n', self.settings(path, CALC_APPROVE_ENDPOINT=self.endpoint))
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, 'SCRIPT_STARTED\nNEXT\n', ''))

    def test_advance_approval_never_expands_domains_or_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.program(directory)
            for approval in ('*', 'https://example.com:443/calculate',
                             'https://other.example.com:443/calculate',
                             'https://calculator.example.com:8443/calculate',
                             'https://calculator.example.com:443/other',
                             'http://calculator.example.com:443/calculate'):
                with self.subTest(approval=approval):
                    p = run_console(settings=self.settings(path, CALC_APPROVE_ENDPOINT=approval))
                    self.assertEqual(p.returncode, 1)
                    self.assertEqual(p.stdout, '')
                    self.assertIn('exact requested endpoint', p.stderr)

    def interactive(self, answer, purpose='Remote calculator operations'):
        with tempfile.TemporaryDirectory() as directory:
            path = self.program(directory, purpose)
            master, slave = os.openpty()
            attributes = termios.tcgetattr(slave)
            attributes[3] &= ~termios.ECHO
            termios.tcsetattr(slave, termios.TCSANOW, attributes)
            env = {k: v for k, v in os.environ.items() if not k.startswith('CALC_')}
            env.update(self.settings(path))
            process = subprocess.Popen([str(CONSOLE)], stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            output = bytearray()
            try:
                deadline = time.monotonic() + 5
                while b'Allow for this session? [y/N] ' not in output:
                    self.assertLess(time.monotonic(), deadline, output.decode(errors='replace'))
                    if select.select([master], [], [], 0.1)[0]:
                        output.extend(os.read(master, 4096))
                before = bytes(output)
                self.assertNotIn(b'SCRIPT_STARTED', before)
                os.write(master, answer)
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        try:
                            chunk = os.read(master, 4096)
                        except OSError:
                            break
                        if not chunk:
                            break
                        output.extend(chunk)
                    elif process.poll() is not None:
                        break
                code = process.wait(timeout=2)
                return code, output.decode().replace('\r\n', '\n')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                os.close(master)

    def test_prompt_labels_claim_and_does_not_inherit_parent_trust(self):
        code, output = self.interactive(b'n\n')
        self.assertEqual(code, 1)
        self.assertIn('Self-claimed purpose (unverified):', output)
        self.assertIn('Destination hostname: calculator.example.com', output)
        self.assertIn('Port: 443\nPath: /calculate', output)
        self.assertIn('No trust is inherited from a parent domain or sibling subdomains.', output)
        self.assertNotIn('SCRIPT_STARTED', output)

    def test_blank_no_unknown_and_eof_deny_before_execution(self):
        for answer in (b'\n', b'no\n', b'perhaps\n', b'\x04'):
            with self.subTest(answer=answer):
                code, output = self.interactive(answer)
                self.assertEqual(code, 1)
                self.assertNotIn('SCRIPT_STARTED', output)
                self.assertIn('script was not executed', output)

    def test_explicit_yes_mounts_once_then_enters_repl(self):
        for answer in (b'y\n', b'YES\n'):
            with self.subTest(answer=answer):
                code, output = self.interactive(answer + b'SAY CALC("exec", "1", "2")\nSAY "NEXT"\n:quit\n')
                self.assertEqual(code, 0)
                self.assertIn('SCRIPT_STARTED\n', output)
                self.assertIn('unknown operation', output)
                self.assertIn('NEXT\n', output)
                self.assertEqual(output.count('Allow for this session?'), 1)

    def test_claim_cannot_inject_terminal_controls_or_bidi(self):
        code, output = self.interactive(b'n\n', 'trusted\x1b[2J\u202e claim')
        self.assertEqual(code, 1)
        self.assertNotIn('\x1b', output)
        self.assertNotIn('\u202e', output)
        self.assertIn('trusted\\x1b[2J\\xe2\\x80\\xae claim', output)


class HTTPConfigurationTests(unittest.TestCase):
    def config(self, **settings):
        env = {k: v for k, v in os.environ.items() if not k.startswith('CALC_')}
        env.update(CALC_HTTP='1', CALC_CHECK_CONFIG='1', **settings)
        return subprocess.run([str(ROOT / 'build/calculator/server')], env=env,
                              capture_output=True, text=True, timeout=10)

    def test_local_http_without_certificates(self):
        for host in ('localhost', '127.0.0.1'):
            with self.subTest(host=host):
                p = self.config(CALC_HOST=host)
                self.assertEqual((p.returncode, p.stdout, p.stderr),
                                 (0, 'local HTTP configuration valid\n', ''))

    def test_remote_http_bind_refused(self):
        for host in ('0.0.0.0', 'example.com', 'localhost.evil'):
            with self.subTest(host=host):
                p = self.config(CALC_HOST=host)
                self.assertEqual(p.returncode, 1)
                self.assertIn('loopback', p.stderr)

    def test_https_still_requires_certificates_by_default(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('CALC_')}
        p = subprocess.run([str(ROOT / 'build/calculator/server')], env=env,
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 1)
        self.assertIn('CALC_CERT and CALC_KEY', p.stderr)


class TLSConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.path = Path(cls.directory.name)
        for name in ('one', 'two'):
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt',
                            'ec_paramgen_curve:prime256v1', '-nodes', '-days', '1',
                            '-subj', '/CN=localhost', '-keyout', str(cls.path / f'{name}.key'),
                            '-out', str(cls.path / f'{name}.pem')],
                           capture_output=True, check=True, timeout=20)

    def check_config(self, cert, key):
        env = {k: v for k, v in os.environ.items() if not k.startswith('CALC_')}
        env.update(CALC_CERT=str(cert), CALC_KEY=str(key), CALC_CHECK_CONFIG='1')
        return subprocess.run([str(ROOT / 'build/calculator/server')], env=env,
                              capture_output=True, text=True, timeout=10)

    def test_matching_p256_keypair_without_sockets(self):
        p = self.check_config(self.path / 'one.pem', self.path / 'one.key')
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, 'TLS keypair valid\n', ''))

    def test_mismatched_key_rejected_before_bind(self):
        p = self.check_config(self.path / 'one.pem', self.path / 'two.key')
        self.assertEqual(p.returncode, 1)
        self.assertIn('do not match', p.stderr)

    def test_invalid_certificate_rejected_before_bind(self):
        bad = self.path / 'bad.pem'
        bad.write_text('not a certificate')
        p = self.check_config(bad, self.path / 'one.key')
        self.assertEqual(p.returncode, 1)
        self.assertIn('invalid PEM certificate', p.stderr)


if __name__ == '__main__':
    unittest.main()
