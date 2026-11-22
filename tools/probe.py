"""Run Rexx programs on RexxAE (through the C ABI) and on RexxJS (tests/oracle.cjs).

Used by tools/tracking.py and by hand:
    python3 tools/probe.py build/librexxae.so ../RexxJS 'SAY 1+1' 'SAY DATATYPE(5)'
prints, per program, what each engine said: its SAY lines, the ADDRESS
commands it sent, and an error if it failed.
"""
import ctypes
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
P, I, S = ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p


class Native:
    def __init__(self, library):
        lib = ctypes.CDLL(str(Path(library).resolve()))
        for name, parameters, result in [
            ('create', [S], P), ('destroy', [P], None), ('step', [P, I], I),
            ('reply', [P, I, S, S], I), ('text', [P], S), ('address', [P], S),
            ('error', [P], S), ('exit_code', [P], I),
        ]:
            fn = getattr(lib, 'aether_rexxae_' + name)
            fn.argtypes, fn.restype = parameters, result
            setattr(self, name, fn)

    def run(self, source):
        """What the program does with no functions mounted: every command answered RC 0."""
        ctx = self.create(source.encode())
        answer = {'output': [], 'commands': []}
        try:
            for _ in range(100000):
                status = self.step(ctx, 1000)
                if status == -1:
                    answer['error'] = self.error(ctx).decode(errors='replace')
                    return answer
                if status == 0:
                    answer['exit'] = self.exit_code(ctx)
                    return answer
                if status == 1:
                    answer['output'].append(self.text(ctx).decode(errors='replace'))
                elif status == 2:
                    answer['commands'].append([self.address(ctx).decode(), self.text(ctx).decode(errors='replace')])
                    self.reply(ctx, 0, b'host-result', b'')
                elif status == 4:
                    answer['error'] = 'called an unmounted host function'
                    return answer
            answer['error'] = 'did not finish within the probe budget'
            return answer
        finally:
            self.destroy(ctx)


def reference(rexxjs, sources):
    """RexxJS's answers for many programs in one node process."""
    result = subprocess.run(['node', str(HERE.parent / 'tests/oracle.cjs'), rexxjs, '--capture-errors'],
                            input=json.dumps(sources), text=True, capture_output=True, timeout=600)
    if result.returncode != 0:
        raise SystemExit(f'RexxJS oracle failed: {result.stderr[-2000:]}')
    return json.loads(result.stdout)


if __name__ == '__main__':
    native = Native(sys.argv[1])
    programs = [p.replace('\\n', '\n') for p in sys.argv[3:]]
    for source, js in zip(programs, reference(sys.argv[2], programs)):
        print('====', source.replace('\n', ' | '))
        print('  RexxAE:', json.dumps(native.run(source)))
        print('  RexxJS:', json.dumps(js))
