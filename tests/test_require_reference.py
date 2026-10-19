"""Use real RexxJS parsing and AS helpers with a controlled module resolver."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from repl import Session

library, reference = sys.argv[1:3]
cases = [('REQUIRE "calculator"', ['calculator']),
         ('REQUIRE "calculator" AS Remote', ['calculator', 'Remote']),
         ('REQUIRE "calculator" AS remote_', ['calculator', 'remote_']),
         ('REQUIRE "calculator" AS remote_(.*)', ['calculator', 'remote_(.*)']),
         ('REQUIRE "calculator" AS (.*)', ['calculator', '(.*)']),
         ('REQUIRE "calculator" AS "Remote"', ['calculator', 'Remote'])]
session = Session(library)
api = session.api
observed = []
try:
    for source, expected in cases:
        ctx = api['create'](source.encode())
        try:
            assert api['register_function'](ctx, b'REQUIRE', 1, 2) == 0
            assert api['step'](ctx, 100) == 4
            request = json.loads(api['arguments_json'](ctx))
            assert request == expected, (source, request)
            assert api['reply_value'](ctx, b'true', b'') == 0
            assert api['step'](ctx, 100) == 0
            observed.append(request)
        finally:
            api['destroy'](ctx)
finally:
    session.close()
javascript = r'''
const fs = require('node:fs'), path = require('node:path');
const root = path.resolve(process.argv[1]);
const {parse} = require(path.join(root, 'core/src/parser.js'));
const {RexxInterpreter} = require(path.join(root, 'core/src/interpreter.js'));
const registration = require(path.join(root, 'core/src/interpreter-library-registration.js'));
(async () => {
  const requests = [];
  for (const source of JSON.parse(fs.readFileSync(0, 'utf8'))) {
    const interpreter = new RexxInterpreter({send: async () => {throw Error('unexpected ADDRESS')}}, {output: () => {}});
    interpreter.requireWithDependencies = async (name, alias) => {
      requests.push(alias === null ? [name] : [name, alias]); return true;
    };
    await interpreter.run(parse(source), source);
  }
  const names = ['', 'Remote', 'remote_', 'remote_(.*)', '(.*)'].map(alias => registration.applyAsClauseToFunction(null, 'CALC', alias));
  const address = registration.applyAsClauseToAddressTarget(null, 'original', 'Remote', {});
  let refused = false;
  try { registration.applyAsClauseToAddressTarget(null, 'original', 'remote_(.*)', {}); } catch (_) { refused = true; }
  process.stdout.write(JSON.stringify({requests, names, address, refused}));
})().catch(error => { console.error(error); process.exit(1) });
'''
p = subprocess.run(['node', '-e', javascript, reference], input=json.dumps([s for s, _ in cases]),
                   text=True, capture_output=True, check=True, timeout=30)
actual = json.loads(p.stdout)
assert actual == {'requests': observed, 'names': ['CALC', 'Remote_CALC', 'remote_CALC', 'remote_CALC', 'CALC'],
                  'address': 'remote', 'refused': True}, actual
print(f'{len(cases)} REQUIRE/AS requests and naming rules match actual RexxJS code')
