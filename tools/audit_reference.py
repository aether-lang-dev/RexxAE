"""Audit upstream changes without recategorizing failures as passing parity."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('library')
parser.add_argument('--oracle', default='../RexxJS')
parser.add_argument('--spreadsheet', default='../spraedsheet')
parser.add_argument('--output', default='docs/reference-audit.json')
options = parser.parse_args()
helper = Path('tests/test_engine.py')
saved_argv = sys.argv
try:
    sys.argv = [str(helper), options.library]
    spec = importlib.util.spec_from_file_location('native_test_driver', helper)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
finally:
    sys.argv = saved_argv


def reference(root, sources):
    result = subprocess.run(['node', 'tests/oracle.cjs', str(root), '--capture-errors'],
                            input=json.dumps(sources), text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise SystemExit(result.stderr)
    return json.loads(result.stdout)


def current(source):
    try:
        return native.run(source)
    except (RuntimeError, AssertionError) as error:
        return {'error': str(error)}


def revision(path):
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


programs = native.parity_programs()
changes = json.loads(Path('tests/reference_migration.json').read_text())
known = json.loads(Path('tests/known_differences.json').read_text())
entries = programs + [(c['name'], c['source']) for c in changes]
observed = [current(source) for _, source in entries]
spreadsheet = Path(options.spreadsheet)
pin = (spreadsheet / 'vendor/rexxjs/UPSTREAM').read_text().splitlines()[0].split()[-1]
report = {
    'previous_reference_revision': '57b97c7d8b3079f65c53d0ac6a179fe3760fe27b',
    'native_source_sha256': hashlib.sha256(b''.join(p.name.encode() + p.read_bytes() for p in sorted(Path('src').glob('*.ae')))).hexdigest(),
    'spreadsheet_revision': revision(spreadsheet),
    'spreadsheet_vendored_revision': pin,
    'references': [],
}
for label, root, commit in [('standalone', Path(options.oracle), revision(options.oracle)),
                            ('spreadsheet_vendor', spreadsheet / 'vendor/rexxjs', pin)]:
    results = reference(root, [source for _, source in entries])
    if len(results) != len(entries):
        raise SystemExit('Oracle returned the wrong number of results')
    differences = []
    for (name, source), actual, expected in zip(programs, observed, results):
        if actual != expected:
            differences.append(dict(name=name, source=source, native=actual, reference=expected))
    probes = []
    for row, actual, expected in zip(changes, observed[len(programs):], results[len(programs):]):
        if label == 'standalone' and ('error' in expected or expected['output'] != row['latest_output'] or expected['commands'] != row.get('latest_commands', []) or expected['exit'] != 0):
            raise SystemExit(f"Migration expectation changed for {row['name']}: {expected}")
        probes.append(dict(name=row['name'], source=row['source'], matches=actual == expected, native=actual, reference=expected))
    pinned = reference(root, [c['source'] for c in known])
    pinned_matches = sum('error' not in result and result['output'] == case['reference_output'] and
                         result['commands'] == case.get('reference_commands', []) for case, result in zip(known, pinned))
    result = dict(name=label, revision=commit, existing_total=len(programs), existing_matching=len(programs) - len(differences),
                  existing_differences=differences, migration_total=len(probes), migration_matching=sum(p['matches'] for p in probes),
                  migration_probes=probes, known_reference_snapshots_unchanged=pinned_matches, known_total=len(known))
    report['references'].append(result)
    print(f"{label} {commit[:7]}: {result['existing_matching']}/{len(programs)} existing programs match; "
          f"{result['migration_matching']}/{len(probes)} migration probes match; {pinned_matches}/{len(known)} known reference snapshots unchanged")
Path(options.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
print(f'Wrote {options.output}; audit completion does not imply compatibility. make parity remains the strict check.')
