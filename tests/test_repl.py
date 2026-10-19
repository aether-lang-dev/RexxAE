"""Public C ABI and console tests; all Rexx evaluation uses the native library."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = str(Path(sys.argv[1]).resolve())
spec = importlib.util.spec_from_file_location('rexxae_repl', ROOT / 'examples/repl.py')
repl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repl)


class ReplTests(unittest.TestCase):
    def session(self, **kwargs):
        session = repl.Session(LIBRARY, **kwargs)
        self.addCleanup(session.close)
        return session

    def test_persistent_typed_values_and_reset(self):
        session = self.session()
        session.submit("LET total = 10\nLET data = [1,true]")
        out = []
        session.submit('total = total + 2\nSAY total\nSAY JSON_STRINGIFY(data)', out.append)
        self.assertEqual(out, ['12', '[1,true]'])
        self.assertEqual(session.inspect('total'), '12')
        session.reset()
        self.assertIsNone(session.inspect('total'))

    def test_previous_host_effects_are_not_replayed(self):
        calls = []

        def echo(value):
            calls.append(value)
            return value * 10

        session = self.session(functions=[('TESTECHO', 1, 1, echo)])
        session.submit('LET answer = TESTECHO(2)')
        out = []
        session.submit('SAY answer', out.append)
        session.submit('LET answer = TESTECHO(answer)')
        self.assertEqual(out, ['20'])
        self.assertEqual(calls, [2, 20])
        self.assertEqual(session.inspect('answer'), '200')

    def test_syntax_and_runtime_errors_allow_following_entries(self):
        session = self.session()
        session.submit('LET x = 7')
        with self.assertRaisesRegex(repl.RexxError, 'line 1'):
            session.submit('LET x =')
        self.assertEqual(session.inspect('x'), '7')
        with self.assertRaisesRegex(repl.RexxError, 'division by zero'):
            session.submit('LET x = 8\nLET bad = 1 / 0')
        out = []
        session.submit('SAY x', out.append)
        self.assertEqual(out, ['8'])

    def test_cancellation_discards_partial_bindings(self):
        session = self.session(instruction_limit=20)
        session.submit('LET x = 7')
        with self.assertRaises(repl.SubmissionCancelled):
            session.submit('LET x = 99\nDO FOREVER\nEND')
        self.assertEqual(session.inspect('x'), '7')
        out = []
        session.submit('SAY x', out.append)
        self.assertEqual(out, ['7'])

    def test_interrupted_host_request_is_discarded_without_replay(self):
        calls = []

        def interrupted():
            calls.append(1)
            raise KeyboardInterrupt

        session = self.session(functions=[('TESTWAIT', 0, 0, interrupted)])
        session.submit('LET x = 7')
        with self.assertRaises(KeyboardInterrupt):
            session.submit('LET x = 99\nCALL TESTWAIT')
        out = []
        session.submit('SAY x', out.append)
        self.assertEqual(out, ['7'])
        self.assertEqual(calls, [1])

    def test_default_console_vetoes_commands_and_cannot_mount_services(self):
        session = self.session()
        out = []
        session.submit("ADDRESS APP 'operation'\nSAY RC ERRORTEXT", out.append)
        self.assertEqual(out, ['13 environment not mounted'])
        session.submit("LET h.NETWORK = {min:0,max:1}")
        with self.assertRaisesRegex(repl.RexxError, 'unknown or unavailable'):
            session.submit("CALL NETWORK 'https://example.invalid'")
        self.assertEqual(session.inspect('RC'), '13')

    def test_two_sessions_do_not_share_variables_or_mounts(self):
        first = self.session(functions=[('TESTECHO', 0, 0, lambda: 42)])
        second = self.session()
        first.submit('LET x = TESTECHO()')
        self.assertIsNone(second.inspect('x'))
        with self.assertRaises(repl.RexxError):
            second.submit('CALL TESTECHO')
        first.submit('SAY x', lambda text: self.assertEqual(text, '42'))

    def test_host_refusal_is_terminal_for_entry_but_not_session(self):
        def refused():
            raise ValueError('resource refused')

        session = self.session(functions=[('TESTREFUSE', 0, 0, refused)])
        session.submit('LET x = 7')
        with self.assertRaisesRegex(repl.RexxError, 'resource refused'):
            session.submit('CALL TESTREFUSE')
        self.assertEqual(session.inspect('x'), '7')
        session.submit('LET x = 8')
        self.assertEqual(session.inspect('x'), '8')

    def test_console_multiline_shorthand_inspection_and_recovery(self):
        program = """LET total = 10
= total * 2
:begin
DO i = 1 TO 3
total = total + i
END
SAY total
:run
:show total
:begin
LET total = 999
:cancel
SAY total
LET bad =
SAY total
:reset
:show total
:quit
SAY 'never'
"""
        run = subprocess.run([sys.executable, str(ROOT / 'examples/repl.py'), LIBRARY],
                             input=program, text=True, capture_output=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.splitlines(), ['20', '16', '16', '16', '16', '(unset)'])
        self.assertIn('error: line 1', run.stderr)

    def test_complete_block_parses_before_any_host_effect(self):
        calls = []
        session = self.session(functions=[('TESTECHO', 0, 0, lambda: calls.append(1))])
        with self.assertRaises(repl.RexxError):
            session.submit('CALL TESTECHO\nLET bad =')
        self.assertEqual(calls, [])
        self.assertIsNone(session.inspect('bad'))

    def test_unsubmitted_block_has_no_effect(self):
        session = self.session()
        out, err = io.StringIO(), io.StringIO()
        repl.repl(session, io.StringIO(':begin\nLET x = 7\n'), out, err)
        self.assertIsNone(session.inspect('x'))
        self.assertIn('unfinished block discarded', err.getvalue())

    def test_nul_input_is_not_silently_truncated(self):
        session = self.session()
        with self.assertRaises(ValueError):
            session.submit("LET x = 7\0\nLET x = 8")
        self.assertIsNone(session.inspect('x'))


if __name__ == '__main__':
    unittest.main(argv=['test_repl.py'], verbosity=2)
