"""Offline checks of the Aether binary host, including the new EOF API."""
import os
from pathlib import Path
import subprocess
import tempfile
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
