"""A small Python host harness exercising the public C API and typed replies.

Run `make`, then `python3 examples/host.py build/librexxae.so`.
The engine and all script evaluation are native Aether; Python supplies only
the three explicitly registered application functions.
"""
import ctypes
import json
from pathlib import Path
import sys


SOURCE = Path(__file__).with_suffix('.rexx').read_text()


def main(library):
    lib = ctypes.CDLL(str(Path(library).resolve()))
    pointer, integer, text = ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p
    signatures = {
        'create': ([text], pointer), 'destroy': ([pointer], None),
        'step': ([pointer, integer], integer),
        'register_function': ([pointer, text, integer, integer], integer),
        'function': ([pointer], text), 'arguments_json': ([pointer], text),
        'reply_value': ([pointer, text, text], integer),
        'text': ([pointer], text), 'error': ([pointer], text),
        'exit_code': ([pointer], integer),
    }
    api = {}
    for name, (parameters, result) in signatures.items():
        function = getattr(lib, 'aether_rexxae_' + name)
        function.argtypes, function.restype = parameters, result
        api[name] = function
    calls = []
    handlers = {
        'TESTHOST': (2, 2, lambda array, obj: {'continue': True, 'echo': [array, obj]}),
        'TESTADD': (2, 2, lambda a, b: a + b),
        'TESTREPORT': (0, 0, lambda: {'calls': len(calls), 'ready': True, 'empty': None}),
    }
    ctx = api['create'](SOURCE.encode())
    if not ctx:
        raise RuntimeError('cannot create Rexx context')
    output = []
    try:
        for name, (minimum, maximum, _) in handlers.items():
            if api['register_function'](ctx, name.encode(), minimum, maximum) != 0:
                raise RuntimeError('cannot register ' + name)
        for _ in range(1000):
            status = api['step'](ctx, 4)
            if status == -1:
                raise RuntimeError(api['error'](ctx).decode())
            if status == 0:
                assert api['exit_code'](ctx) == 0
                assert output[:3] == ['3', '4', '5']
                assert json.loads(output[3]) == {'calls': 5, 'ready': True, 'empty': None}
                assert [name for name, _ in calls] == ['TESTHOST', 'TESTADD', 'TESTADD', 'TESTADD', 'TESTREPORT']
                print(f'Python host harness passed: {len(calls)} typed calls, nested CALL/RETURN, SELECT/DO, JSON replies')
                return
            if status == 1:
                output.append(api['text'](ctx).decode())
            if status == 4:
                name = api['function'](ctx).decode()
                arguments = json.loads(api['arguments_json'](ctx))
                calls.append((name, arguments))
                result = handlers[name][2](*arguments)
                if api['reply_value'](ctx, json.dumps(result).encode(), b'') != 0:
                    raise RuntimeError('host reply rejected')
            if status == 2:
                raise RuntimeError('unexpected ADDRESS request')
        raise RuntimeError('execution did not complete within the harness limit')
    finally:
        api['destroy'](ctx)


if __name__ == '__main__':
    main(sys.argv[1])
