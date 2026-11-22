"""Generate docs/rexxjs-tracking.md (and .json): RexxJS and RexxAE against each other.

    python3 tools/tracking.py build/librexxae.so ../RexxJS [--check]

Nothing in the table is typed by hand except the feature probes and the notes
that explain a difference (tools/tracking_features.json,
tools/tracking_function_notes.json). Everything else comes from the two trees:

- RexxJS's functions from its live registration (tools/rexxjs_registry.cjs);
  RexxAE's from the builtin lists in src/*.ae.
- A function is "tested equal by parity" when a program in `make parity`'s
  corpus (tests/test_engine.py --list-programs) calls it.
- A language feature is classified by running its probe on both engines now:
  an engine has the feature when the probe runs without an error (and without
  sending an unexpected command to the default environment, which is how
  RexxJS treats an instruction it does not know); it agrees when its output is
  the expected one. The expected output is the classic (ANSI) Rexx answer, or
  RexxJS's where the dialect deliberately differs, so a RexxJS bug shows as a
  difference instead of being copied.

--check regenerates in memory and fails when the checked-in files are stale.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from probe import Native, reference  # noqa: E402

EQ = 'in both, tested equal by parity'
NC = 'in both, not covered by a parity program'
DIFF = 'in both, known to differ'
JS = 'RexxJS only'
AE = 'RexxAE only'
NEITHER = 'in neither (classic Rexx)'
HOST = 'host-specific to RexxJS, not tracked'
EMBED = 'RexxAE-specific (embedding)'
CLASSES = [EQ, NC, DIFF, JS, AE, NEITHER, HOST, EMBED]

# RexxJS core files whose functions need a JavaScript or browser host, or
# reach the file system, network or OS directly. RexxAE reaches such effects
# only through functions a host mounts, so these are not RexxAE gaps.
HOST_FILES = {
    'core/src/shell-functions.js': 'POSIX shell utilities over node fs/os/child_process; in RexxAE, host-mounted functions',
    'core/src/file-functions.js': 'file system through node or the browser; in RexxAE, host-mounted functions behind a grant',
    'core/src/http-functions.js': 'network requests; in RexxAE, host-mounted functions behind a grant',
    'core/src/path-functions.js': 'node path module semantics for host paths',
    'core/src/dom-functions.js': 'browser DOM',
    'core/src/dom-pipeline-functions.js': 'browser DOM',
}
HOST_NAMES = {
    'INTERPRET_JS': 'runs JavaScript; RexxAE has no JavaScript runtime by design',
    'JS_SHOW': 'shows a JavaScript value',
    'SHOW': 'renders to a browser element',
    'CHECKPOINT': 'progress callbacks to a parent browser window',
}
# The ANSI Rexx builtin functions (X3.274-1996), to show which classic
# functions neither engine has.
CLASSIC = ('ABBREV ABS ADDRESS ARG B2X BITAND BITOR BITXOR C2D C2X CENTER CENTRE CHANGESTR CHARIN CHAROUT '
           'CHARS COMPARE CONDITION COPIES COUNTSTR D2C D2X DATATYPE DATE DELSTR DELWORD DIGITS ERRORTEXT '
           'FORM FORMAT FUZZ INSERT LASTPOS LEFT LENGTH LINEIN LINEOUT LINES MAX MIN OVERLAY POS QUALIFY '
           'QUEUED RANDOM REVERSE RIGHT SIGN SOURCELINE SPACE STREAM STRIP SUBSTR SUBWORD SYMBOL TIME TRACE '
           'TRANSLATE TRUNC VALUE VERIFY WORD WORDINDEX WORDLENGTH WORDPOS WORDS X2B X2C X2D XRANGE').split()


def git_revision(repo):
    try:
        return subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def rexxae_functions():
    source = '\n'.join(p.read_text() for p in sorted((ROOT / 'src').glob('*.ae')))
    lists = {}
    for kind, names in re.findall(r'const (TEXT|MATH|VALUE|LIBRARY|EXTENSION)_FUNCTIONS = "([^"]+)"', source):
        lists.setdefault(kind, set()).update(names.split())
    native = lists.get('TEXT', set()) | lists.get('MATH', set()) | lists.get('VALUE', set()) | lists.get('LIBRARY', set())
    return native, lists.get('EXTENSION', set())


def table(rows, columns):
    out = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    for row in rows:
        out.append('| ' + ' | '.join(str(c).replace('|', '\\|').replace('\n', ' / ') for c in row) + ' |')
    return '\n'.join(out) + '\n'


def engine_status(answer, feature):
    """absent, ok or differs, and a short account of what it did."""
    expect = feature['expect']
    if 'error' in answer:
        return ('ok' if expect is None else 'absent'), 'error: ' + answer['error'].split('\n')[-1][:120]
    sent = answer.get('commands', [])
    if sent and 'ADDRESS' not in feature['probe'].upper():
        return 'absent', 'sent the clause to the default ADDRESS environment'
    said = answer.get('output', [])
    if expect is None:
        return 'differs', 'no error; said ' + json.dumps(said)
    if said == expect and answer.get('exit', 0) == feature.get('exit', 0):
        return 'ok', ''
    return 'differs', 'said ' + json.dumps(said) + ('' if answer.get('exit', 0) == feature.get('exit', 0) else f" exit {answer.get('exit')}")


def build(library, rexxjs):
    features = json.loads((HERE / 'tracking_features.json').read_text())
    notes = json.loads((HERE / 'tracking_function_notes.json').read_text())
    registry = json.loads(subprocess.run(['node', str(HERE / 'rexxjs_registry.cjs'), rexxjs], capture_output=True,
                                         text=True, check=True).stdout)['functions']
    corpus = json.loads(subprocess.run([sys.executable, str(ROOT / 'tests/test_engine.py'), library, '--list-programs'],
                                       capture_output=True, text=True, check=True).stdout)
    sources = [s if isinstance(s, str) else s['source'] for _, s in corpus]
    native, extensions = rexxae_functions()
    known = json.loads((ROOT / 'tests/known_differences.json').read_text())

    def called(name):
        pattern = re.compile(r'\b' + re.escape(name) + r'\s*\(', re.I)
        return any(pattern.search(s) for s in sources)

    functions, host_groups = [], {}
    rexxjs_names = set()
    for fn in registry:
        name, source = fn['name'], fn['source']
        rexxjs_names.add(name)
        if source in HOST_FILES or name in HOST_NAMES:
            host_groups.setdefault(HOST_NAMES.get(name) and name or source, []).append(name)
            continue
        note = notes.get(name, '')
        if name in native:
            cls = DIFF if note else (EQ if called(name) else NC)
        else:
            cls = JS
        functions.append({'name': name, 'library': source.replace('core/src/', ''), 'class': cls, 'note': note})
    for name in sorted(extensions | {'EXPORT'}):
        functions.append({'name': name, 'library': 'RexxAE' if name != 'EXPORT' else 'RexxAE worker', 'class': EMBED,
                          'note': 'the worker\'s own function: names a label the host may call' if name == 'EXPORT'
                          else 'RexxAE extension (docs/cron-and-logging.md)'})
    for name in sorted(native - rexxjs_names):
        functions.append({'name': name, 'library': 'RexxAE', 'class': AE, 'note': notes.get(name, '')})

    classic = []
    for name in CLASSIC:
        in_js, in_ae = name in rexxjs_names, name in native
        classic.append({'name': name, 'rexxjs': 'yes' if in_js else 'no', 'rexxae': 'yes' if in_ae else 'no',
                        'class': EQ if in_js and in_ae else JS if in_js else AE if in_ae else NEITHER})

    probed = [f for f in features if 'probe' in f]
    reference_answers = reference(rexxjs, [f['probe'] for f in probed])
    engine = Native(library)
    rows = []
    for f in features:
        row = {'area': f['area'], 'feature': f['feature'], 'note': f.get('note', '')}
        if f.get('scope') == 'rexxjs-host':
            row.update({'class': HOST, 'note': f['reason']})
        elif f.get('scope') == 'rexxae-embedding':
            row.update({'class': EMBED, 'note': f['reason']})
        elif 'probe' not in f:
            row['class'] = EQ if f.get('corpus') else NC
        else:
            js_status, js_said = engine_status(reference_answers[probed.index(f)], f)
            ae_status, ae_said = engine_status(engine.run(f['probe']), f)
            same_wrong = js_status == ae_status == 'differs' and js_said == ae_said
            if same_wrong and f.get('both_wrong_means') == 'neither':
                row['class'] = NEITHER
            elif js_status != 'absent' and ae_status != 'absent':
                if js_status == ae_status == 'ok' or same_wrong:
                    covered = f.get('corpus') and any(re.search(f['corpus'], s) for s in sources)
                    row['class'] = EQ if covered else NC
                else:
                    row['class'] = DIFF
            elif js_status != 'absent':
                row['class'] = JS
            elif ae_status != 'absent':
                row['class'] = AE
            else:
                row['class'] = NEITHER
            said = []
            if same_wrong:
                said.append('both ' + js_said)
            elif js_status != 'ok':
                said.append('RexxJS ' + js_said)
            if ae_status != 'ok' and not same_wrong:
                said.append('RexxAE ' + ae_said)
            if row['class'] == DIFF and not row['note']:
                row['note'] = 'UNEXPLAINED: add a note to tools/tracking_features.json.'
            row['probe'] = f['probe']
            row['observed'] = '; '.join(said)
        rows.append(row)

    counts = {}
    for item in functions + rows:
        counts[item['class']] = counts.get(item['class'], 0) + 1
    host_count = sum(len(v) for v in host_groups.values())
    counts[HOST] = counts.get(HOST, 0) + host_count
    revision = git_revision(rexxjs)
    report = {'rexxjsRevision': revision, 'parityPrograms': len(sources), 'counts': counts,
              'functions': functions, 'classicFunctions': classic, 'language': rows,
              'hostSpecificFunctions': host_groups}

    md = ['# RexxJS and RexxAE, tracked against each other\n',
          'Generated by `make tracking` (`tools/tracking.py`); do not edit by hand. The feature probes and the notes that '
          'explain a difference are in `tools/tracking_features.json` and `tools/tracking_function_notes.json`; '
          'everything else is read from the two source trees, and every probe is run on both engines when the '
          'table is generated.\n',
          f'RexxJS `{revision}`; parity corpus of {len(sources)} programs (`make parity`).\n',
          'An expected answer is the classic (ANSI) Rexx one, or RexxJS\'s where the dialect deliberately differs '
          '(`%` is a remainder, `//` starts a comment, numbers are IEEE doubles). Where RexxJS disagrees with classic '
          'Rexx in a way that looks like a bug, RexxAE does not copy it: the row says so, and '
          '[rexxjs-suggestions.md](rexxjs-suggestions.md) proposes the RexxJS fix.\n',
          '## Counts\n',
          table([[c, counts.get(c, 0)] for c in CLASSES], ['Class', 'Rows']),
          f'\nFunctions: {len(functions)} rows, plus {host_count} host-specific RexxJS functions grouped below. '
          f'Language features: {len(rows)} rows. Where both engines give the same answer and it is not the '
          f'classic one, the row counts as equal and its note says how classic Rexx differs.\n',
          '## Builtin functions (RexxJS core library and RexxAE)\n',
          table([[f['name'], f['library'], f['class'], f['note']] for f in
                 sorted(functions, key=lambda f: (CLASSES.index(f['class']), f['library'], f['name']))],
                ['Function', 'Library', 'Class', 'Note']),
          '\n## Classic Rexx builtin functions\n',
          'The ANSI builtins, and which engine has each. Most are not in RexxJS\'s registry at all; those are not '
          'RexxAE gaps against RexxJS, and are listed so both can grow toward them together.\n',
          table([[c['name'], c['rexxjs'], c['rexxae'], c['class']] for c in classic], ['Function', 'RexxJS', 'RexxAE', 'Class']),
          '\n## Language\n']
    for area in dict.fromkeys(r['area'] for r in rows):
        md.append(f'### {area}\n')
        md.append(table([[r['feature'], r['class'], r.get('observed', ''), r['note']] for r in rows if r['area'] == area],
                        ['Feature', 'Class', 'Observed (where an engine missed the expected answer)', 'Note']))
        md.append('')
    md.append('## Host-specific to RexxJS, not tracked\n')
    md.append(table([[k.replace('core/src/', ''), len(v), ', '.join(sorted(v)), HOST_FILES.get(k) or HOST_NAMES.get(k, '')]
                     for k, v in sorted(host_groups.items())], ['Source', 'Functions', 'Names', 'Why not tracked']))
    return report, '\n'.join(md)


def main():
    library, rexxjs = sys.argv[1], sys.argv[2]
    report, md = build(library, rexxjs)
    outputs = [(ROOT / 'docs/rexxjs-tracking.json', json.dumps(report, indent=1, ensure_ascii=False) + '\n'),
               (ROOT / 'docs/rexxjs-tracking.md', md)]
    if '--check' in sys.argv:
        for path, text in outputs:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f'{path.relative_to(ROOT)} is stale; run make tracking')
        print('Tracking table is current')
        return
    for path, text in outputs:
        path.write_text(text)
    print('Wrote docs/rexxjs-tracking.md:', ', '.join(f'{k}: {v}' for k, v in report['counts'].items()))


if __name__ == '__main__':
    main()
