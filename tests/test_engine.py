"""Exercise the native ABI and compare supported programs with RexxJS."""
import argparse
import ctypes
import json
from pathlib import Path
import subprocess
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('library')
parser.add_argument('--oracle')
args = parser.parse_args()
lib = ctypes.CDLL(str(Path(args.library).resolve()))
P = ctypes.c_void_p
I = ctypes.c_int32
S = ctypes.c_char_p
for name, parameters, result in [
    ('create', [S], P), ('destroy', [P], None),
    ('step', [P, I], I), ('reply', [P, I, S, S], I),
    ('text', [P], S), ('address', [P], S), ('error', [P], S),
    ('line', [P], I), ('exit_code', [P], I),
    ('register_function', [P, S, I, I], I), ('function', [P], S),
    ('arguments_json', [P], S), ('reply_value', [P, S, S], I),
    ('get_variable_json', [P, S], S), ('set_variable_json', [P, S, S], I),
    ('argument_text', [P, I], S), ('argument_type', [P, I], I),
]:
    fn = getattr(lib, 'aether_rexxae_' + name)
    fn.argtypes, fn.restype = parameters, result
    globals()[name] = fn


def run(source, budget=2):
    config = source if isinstance(source, dict) else {'source': source}
    source = config['source']
    ctx = create(source.encode())
    assert ctx
    answer = {'output': [], 'commands': [], 'exit': 0}
    replies = iter(config.get('replies', []))
    if 'functions' in config:
        answer['calls'] = []
        for name, minimum, maximum in config['functions']:
            assert register_function(ctx, name.encode(), minimum, maximum) == 0
    try:
        for _ in range(10000):
            status = step(ctx, budget)
            if status == -1:
                raise RuntimeError(f'line {line(ctx)}: {error(ctx).decode()}')
            if status == 0:
                answer['exit'] = exit_code(ctx)
                return answer
            if status == 1:
                answer['output'].append(text(ctx).decode())
            if status == 2:
                answer['commands'].append([address(ctx).decode(), text(ctx).decode()])
                assert reply(ctx, 0, b'host-result', b'') == 0
            if status == 4:
                name = function(ctx).decode()
                arguments = json.loads(arguments_json(ctx))
                answer['calls'].append([name, arguments])
                result = next(replies)
                assert reply_value(ctx, json.dumps(result).encode(), b'') == 0
        raise AssertionError('engine did not finish')
    finally:
        destroy(ctx)


# Source and expected results are intentionally explicit; these also run
# unchanged against the actual JS interpreter when --oracle is supplied.
CASES = [
    ('empty', '', [], [], 0),
    ('say', "SAY 'hello'", ['hello'], [], 0),
    ('empty_literal', "SAY ''", [''], [], 0),
    ('double_quote', 'SAY "hello"', ['hello'], [], 0),
    ('single_doubled_quote', "SAY 'it''s Rexx'", ["it's Rexx"], [], 0),
    ('double_doubled_quote', 'SAY "say ""hi"""', ['say "hi"'], [], 0),
    ('quoted_comments', "SAY '-- /* // ;'", ['-- /* // ;'], [], 0),
    ('comments', "-- hi\n/* comment */\nSAY 'ok' -- tail\n", ['ok'], [], 0),
    ('clauses', "LET X = 4; SAY X; EXIT 0", ['4'], [], 0),
    ('crlf', 'LET X = 7\r\nSAY X\r\n', ['7'], [], 0),
    ('assignment', 'LET X = 4\nSAY X', ['4'], [], 0),
    ('bare_assignment', 'X = 4\nSAY X', ['4'], [], 0),
    ('arithmetic', 'LET X = 2 + 3 * 4\nSAY X', ['14'], [], 0),
    ('parentheses', 'LET X = (2 + 3) * 4\nSAY X', ['20'], [], 0),
    ('left_associative', 'LET X = 12 - 4 - 3\nSAY X', ['5'], [], 0),
    ('division', 'LET X = 7 / 2\nSAY X', ['3.5'], [], 0),
    ('negative', 'LET X = -5\nSAY X', ['-5'], [], 0),
    ('concat', "LET X = 'a' || 'b'\nSAY X", ['ab'], [], 0),
    ('bare_concat', "X = 'a' || 'b'\nSAY X", ['ab'], [], 0),
    ('blank_concat', "SAY 'a' 'b'", ['a b'], [], 0),
    ('mixed_concat', 'LET RC = 0\nSAY "(RC" RC || ")"', ['(RC 0)'], [], 0),
    ('unset', 'SAY UNSET RC RESULT', ['UNSET RC RESULT'], [], 0),
    ('case', "let name = 'Rexx'\nsay name NAME", ['Rexx NAME'], [], 0),
    ('unset_case', 'SAY unset', ['UNSET'], [], 0),
    ('command', "ADDRESS COUNTER\n'VALUE'\nSAY RC RESULT", ['0 host-result'], [['counter', 'VALUE']], 0),
    ('inline_command', "ADDRESS COUNTER 'VALUE'\nSAY RC RESULT", ['0 host-result'], [['counter', 'VALUE']], 0),
    ('default', "ADDRESS DEFAULT\n'hello'", ['hello'], [], 0),
    ('exit', "SAY 'before'\nEXIT 7\nSAY 'after'", ['before'], [], 7),
    ('number_variable_type', 'LET ZERO = 0\nLET X = MATH_PERCENTAGE(25, ZERO)\nSAY X', ['25'], [], 0),
    ('string_variable_type', "LET ZERO = '0'\nLET X = MATH_PERCENTAGE(25, ZERO)\nSAY X", ['0'], [], 0),
    ('function_result_type', 'LET X = MATH_POWER(2, ABS(0))\nSAY X', ['2'], [], 0),
    ('literal_operator', "SAY 'a' '+' 'b'", ['a + b'], [], 0),
    ('array', "LET a = [1, 'two', false]\nSAY LENGTH(a) ARRAY_GET(a, 2)", ['3 two'], [], 0),
    ('object', "LET o = {\"a\": 1, \"b\": true}\nSAY LENGTH(o) JSON_GET(o, 'a')", ['2 1'], [], 0),
    ('typed_bool', "LET a = true\nLET b = 'true'\nSAY TYPEOF(a) TYPEOF(b)", ['boolean string'], [], 0),
    ('null_json', "LET n = JSON_PARSE('null')\nSAY JSON_STRINGIFY(n)", ['{}'], [], 0),
    ('array_clone', "LET a = [1, 2]\nLET b = ARRAY_PUSH(a, 3)\nSAY LENGTH(a) JOIN(b, '-')", ['2 1-2-1,2-3'], [], 0),
    ('comparison', "LET a = '02' = 2\nLET b = '02' == 2\nSAY a b", ['1 0'], [], 0),
    ('if_else', "IF 2 > 1 THEN SAY 'yes'\nELSE SAY 'no'\nIF 0 THEN SAY 'bad'\nELSE SAY 'good'", ['yes', 'good'], [], 0),
    ('nested_if', "IF 1 THEN DO\nIF 0 THEN SAY 'bad'\nELSE SAY 'inner'\nSAY 'outer'\nEND\nELSE SAY 'bad'", ['inner', 'outer'], [], 0),
    ('ranges', "DO i = 1 TO 3\nSAY i\nEND\nDO j = 3 TO 1 BY -2\nSAY j\nEND", ['1', '2', '3', '3', '1'], [], 0),
    ('restore_loop_var', "LET i = 'old'\nDO i = 1 TO 2\nSAY i\nEND\nSAY i", ['1', '2', 'old'], [], 0),
    ('loop_variants', "LET n = 0\nDO 2\nn = n + 1\nEND\nDO WHILE n < 4\nn = n + 1\nEND\nDO UNTIL n = 5\nn = n + 1\nEND\nDO item OVER [n, 6]\nSAY item\nEND", ['5', '6'], [], 0),
    ('inner_loop', "DO i = 1 TO 3\nDO FOREVER\nIF i = 2 THEN LEAVE\nSAY i\nLEAVE\nEND\nIF i = 2 THEN ITERATE\nSAY 'after'\nEND", ['1', 'after', '3', 'after'], [], 0),
    ('quoted_exit', "'EXIT'", ['EXIT'], [], 0),
]

for name, source, output in json.loads(Path(__file__).with_name('routine_cases.json').read_text()):
    CASES.append(('routine_' + name, source, output, [], 0))

for name, source, output in json.loads(Path(__file__).with_name('select_cases.json').read_text()):
    CASES.append(('select_' + name, source, output, [], 0))

for name, source, output in json.loads(Path(__file__).with_name('parse_cases.json').read_text()):
    CASES.append(('parse_' + name, source, output, [], 0))

for row in json.loads(Path(__file__).with_name('reference_migration.json').read_text()):
    CASES.append(('migration_' + row['name'], row['source'], row['latest_output'], row.get('latest_commands', []), 0))

HOST_CASES = [
    ('parse_command_reply', dict(source="ADDRESS APP 'line'\nPARSE VAR RESULT first '-' rest\nSAY first rest", functions=[], replies=[])),
    ('compound_host_reply', dict(source="LET data.reply = TESTHOST()\nSAY data.reply.ok\nCALL TESTHOST data.reply", functions=[['TESTHOST', 0, 1]], replies=[{'ok': True}, None])),
    ('select_first_host_match', dict(source="SELECT\nWHEN TESTHOST(1) THEN SAY 'bad'\nWHEN TESTHOST(2) THEN CALL TESTHOST 3\nWHEN TESTHOST(4) THEN SAY 'bad'\nOTHERWISE CALL TESTHOST 5\nEND\nSAY RESULT",
                                   functions=[['TESTHOST', 1, 1]], replies=[False, True, {'ok': True}])),
    ('select_condition_expression', dict(source="SELECT\nWHEN TESTHOST(1) < TESTHOST(2) THEN SAY 'match'\nOTHERWISE SAY 'bad'\nEND",
                                        functions=[['TESTHOST', 1, 1]], replies=[2, 3])),
    ('select_default_host', dict(source="SELECT\nWHEN TESTHOST(1) THEN SAY 'bad'\nOTHERWISE\nLET data = TESTHOST(2)\nSAY JSON_STRINGIFY(data)\nEND",
                               functions=[['TESTHOST', 1, 1]], replies=[False, {'data': [True, None]}])),
    ('select_routine_host', dict(source="CALL work\nSAY RESULT\nEXIT\nwork:\nSELECT\nWHEN TESTHOST(1) THEN CALL inner\nOTHERWISE RETURN 0\nEND\nLET answer = RESULT\nRETURN answer\ninner:\nCALL TESTHOST 2\nLET answer = RESULT\nRETURN answer",
                               functions=[['TESTHOST', 1, 1]], replies=[True, 7])),
    ('select_commands', dict(source="SELECT\nWHEN 1 THEN ADDRESS APP 'selected'\nOTHERWISE ADDRESS APP 'bad'\nEND\nSAY RC RESULT",
                           functions=[], replies=[])),
    ('routine_host_arguments', dict(source="CALL outer TESTHOST(1), TESTHOST(2)\nSAY RESULT\nEXIT\nouter:\nARG a,b\nCALL inner a + b\nLET answer = RESULT\nRETURN answer\ninner:\nARG n\nCALL TESTHOST n\nLET answer = RESULT\nRETURN answer",
                                    functions=[['TESTHOST', 1, 1]], replies=[2, 3, 10])),
    ('assigned_host_call', dict(source="LET x = CALL TESTHOST 0 'text'\nSAY JSON_STRINGIFY(x)",
                                functions=[['TESTHOST', 2, 2]], replies=[{'ok': True}])),
    ('recursive_host', dict(source="CALL down 3\nSAY RESULT\nEXIT\ndown:\nARG n\nIF n = 0 THEN RETURN 'done'\nCALL TESTHOST n\nCALL down n - 1\nRETURN 'done'",
                            functions=[['TESTHOST', 1, 1]], replies=[1, 2, 3])),
    ('routine_commands', dict(source="CALL work 2\nSAY RESULT\nEXIT\nwork:\nARG count\nDO i = 1 TO count\nADDRESS APP 'work'\nEND\nRETURN 7",
                              functions=[], replies=[])),
    ('host_nested', dict(source='LET n = ABS(TESTHOST(1)) + TESTHOST(2)\nSAY n',
                         functions=[['TESTHOST', 1, 1]], replies=[-3, 4])),
    ('host_typed', dict(source="LET a = [1, true]\nLET input = {\"key\": \"value\"}\nLET o = TESTHOST(a, input)\nSAY JSON_STRINGIFY(o)",
                        functions=[['TESTHOST', 2, 2]], replies=[{'ok': True, 'empty': None}])),
    ('host_lazy_if', dict(source='LET n = IF(1, 7, TESTHOST())\nSAY n',
                          functions=[['TESTHOST', 0, 0]], replies=[])),
    ('host_loop', dict(source='DO i = 1 TO 3\nLET n = TESTHOST(i)\nSAY n\nEND',
                       functions=[['TESTHOST', 1, 1]], replies=[10, 20, 30])),
    ('host_control', dict(source="LET a = [1, true]\nLET input = {\"ready\": true}\nLET config = TESTHOST(a, input)\nIF JSON_GET(config, 'continue') THEN DO\nDO i = 1 TO 2\nLET n = TESTHOST(i)\nSAY n\nEND\nEND",
                         functions=[['TESTHOST', 1, 2]], replies=[{'continue': True}, 10, 20])),
    ('python_host_harness', dict(source=Path(__file__).resolve().parents[1].joinpath('examples/host.rexx').read_text(),
                                functions=[['TESTHOST', 2, 2], ['TESTADD', 2, 2], ['TESTREPORT', 0, 0]],
                                replies=[{'continue': True, 'echo': [[1, True], {'message': 'hello'}]}, 3, 4, 5,
                                         {'calls': 5, 'ready': True, 'empty': None}])),
]


for name, expression, expected in json.loads(Path(__file__).with_name('function_cases.json').read_text()):
    CASES.append(('function_' + name, 'LET ANSWER = ' + expression + '\nSAY ANSWER', [expected], [], 0))


def parity_programs():
    programs = [(c[0], c[1]) for c in CASES] + HOST_CASES
    # A deterministic boundary matrix supplements the named golden cases.
    # Expected answers come from executing the reference engine, not from
    # reproducing the native implementation in the test.
    for fn in ['SUBSTR', 'SUBSTRING']:
        for start in [-3, 0, 1, 3, 9]:
            for length in [-3, 0, 1, 3, 9]:
                expression = f"{fn}('abcd', {start}, {length})"
                programs.append((expression, 'LET X = ' + expression + '\nSAY X'))
    for fn in ['POS', 'INDEX', 'INDEXOF']:
        for needle in ['', 'a', 'bc', 'z']:
            for start in [-2, 0, 1, 3, 9]:
                expression = f"{fn}('abcabc', '{needle}', {start})"
                programs.append((expression, 'LET X = ' + expression + '\nSAY X'))
    for fn in ['LEFT', 'RIGHT', 'CENTER', 'PAD_START', 'PAD_END']:
        for size in [-2, 0, 1, 3, 7]:
            for pad in [' ', 'xy']:
                expression = f"{fn}('abc', {size}, '{pad}')"
                programs.append((expression, 'LET X = ' + expression + '\nSAY X'))
    for fn in ['INT', 'MATH_FLOOR', 'MATH_CEIL', 'MATH_ROUND']:
        for value in [-3.5, -2.5, -1.1, -0.5, 0, 0.5, 1.1, 2.5, 3.5]:
            expression = f'{fn}({value})'
            programs.append((expression, 'LET X = ' + expression + '\nSAY X'))
    return programs


class EngineTests(unittest.TestCase):
    def test_documented_parser_differences(self):
        differences = json.loads(Path(__file__).with_name('known_differences.json').read_text())
        for case in differences:
            with self.subTest(name=case['name']):
                native = run(case['source'])
                self.assertEqual(native['output'], case['native_output'])
                self.assertEqual(native['commands'], case.get('native_commands', []))
        if args.oracle:
            result = subprocess.run(
                ['node', str(Path(__file__).with_name('oracle.cjs')), args.oracle],
                input=json.dumps([c['source'] for c in differences]), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for case, reference in zip(differences, json.loads(result.stdout)):
                with self.subTest(reference=case['name']):
                    self.assertEqual(reference['output'], case['reference_output'])
                    self.assertEqual(reference['commands'], case.get('reference_commands', []))

    def test_programs(self):
        for name, source, output, commands, code in CASES:
            with self.subTest(name=name):
                self.assertEqual(run(source), dict(output=output, commands=commands, exit=code))

    def test_reply_and_pending_command(self):
        ctx = create(b"ADDRESS APP\n'work'\nSAY RC RESULT ERRORTEXT")
        try:
            self.assertEqual(reply(ctx, 0, b'', b''), -1)
            self.assertEqual(step(ctx, 0), 3)
            self.assertEqual(step(ctx, 10), 2)
            self.assertEqual(text(ctx), b'work')
            self.assertEqual(step(ctx, 10), 2)
            self.assertEqual(reply(ctx, 2, b'failed', b'missing app'), 0)
            self.assertEqual(step(ctx, 10), 1)
            self.assertEqual(text(ctx), b'2 failed missing app')
            self.assertEqual(step(ctx, 10), 0)
            self.assertEqual(step(ctx, 10), 0)
        finally:
            destroy(ctx)

    def test_error_is_terminal_and_located(self):
        for source in [b'\nLET X = (1 + 2', b"\nSAY 'oops", b'\nDO I = 1 TO 2',
                       b'\nLET X = 1 / 0', b'\nREQUIRE "file.js"', b'\nLET X = MISSING(1,2)',
                       b'\nSAY "hello {NAME}"', b'\n/* unfinished', b'\nPARSE SOURCE input',
                       b'\nSAY', b"\nADDRESS APP\n'hello {NAME}'"]:
            with self.subTest(source=source):
                ctx = create(source)
                try:
                    self.assertEqual(step(ctx, 100), -1)
                    self.assertTrue(error(ctx))
                    self.assertEqual(line(ctx), 3 if source.startswith(b'\nADDRESS') else 2)
                    self.assertEqual(step(ctx, 100), -1)
                finally:
                    destroy(ctx)

    def test_independent_contexts(self):
        a = create(b"LET X = 'first'\nSAY X")
        b = create(b"LET X = 'second'\nSAY X")
        try:
            self.assertEqual(step(a, 1), 3)
            self.assertEqual(step(b, 1), 3)
            self.assertEqual(step(b, 1), 1)
            self.assertEqual(step(a, 1), 1)
            self.assertEqual(text(a), b'first')
            self.assertEqual(text(b), b'second')
        finally:
            destroy(a)
            destroy(b)

    def test_typed_variable_boundary(self):
        ctx = create(b'LET result = input')
        try:
            self.assertEqual(set_variable_json(ctx, b'input', b'{"a":[1,true,null,"a\\u0000b"]}'), 0)
            self.assertEqual(step(ctx, 100), 0)
            self.assertEqual(json.loads(get_variable_json(ctx, b'result')), {'a': [1, True, None, 'a\0b']})
            self.assertIsNone(get_variable_json(ctx, b'unset'))
            self.assertEqual(set_variable_json(ctx, b'input', b'{}'), -1)  # done is terminal
        finally:
            destroy(ctx)

    def test_host_reply_protocol_and_arguments(self):
        ctx = create(b'LET result = TESTHOST("cell", 42, true, JSON_PARSE("null"))')
        try:
            self.assertEqual(register_function(ctx, b'testhost', 4, 4), 0)
            self.assertEqual(step(ctx, 100), 4)
            self.assertEqual([argument_type(ctx, i) for i in range(5)], [3, 2, 1, 0, -1])
            self.assertEqual(argument_text(ctx, 0), b'cell')
            self.assertEqual(argument_text(ctx, 1), b'42')
            self.assertIsNone(argument_text(ctx, -1))
            self.assertEqual(reply_value(ctx, b'not-json', b''), -1)
            self.assertEqual(step(ctx, 100), 4)
            self.assertEqual(reply_value(ctx, b'{"ok":true}', b''), 0)
            self.assertEqual(step(ctx, 100), 0)
            self.assertEqual(json.loads(get_variable_json(ctx, b'result')), {'ok': True})
        finally:
            destroy(ctx)

    def test_host_error_is_terminal(self):
        ctx = create(b'\nLET n = TESTHOST()')
        try:
            self.assertEqual(register_function(ctx, b'TESTHOST', 0, 0), 0)
            self.assertEqual(step(ctx, 100), 4)
            self.assertEqual(reply_value(ctx, b'null', b'application refused'), 0)
            self.assertEqual(step(ctx, 100), -1)
            self.assertEqual(error(ctx), b'application refused')
            self.assertEqual(line(ctx), 2)
        finally:
            destroy(ctx)

    @unittest.skipUnless(args.oracle, 'pass --oracle /path/to/RexxJS for differential tests')
    def test_rexxjs_parity(self):
        programs = parity_programs()
        result = subprocess.run(
            ['node', str(Path(__file__).with_name('oracle.cjs')), args.oracle],
            input=json.dumps([source for _, source in programs]), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        reference = json.loads(result.stdout)
        self.assertEqual(len(reference), len(programs))
        for (name, source), expected in zip(programs, reference):
            with self.subTest(name=name):
                self.assertEqual(run(source), expected)
        print(f'Compared {len(programs)} programs against RexxJS')


if __name__ == '__main__':
    unittest.main(argv=['test_engine.py'], verbosity=2)
