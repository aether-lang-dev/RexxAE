"""Console host for the native RexxAE library; run `make repl`.

Rexx parsing, values and evaluation live in Aether. This host supplies input,
output and explicitly mounted functions. The console mounts no effect services.
"""
import argparse
import ctypes
import json
from pathlib import Path
import sys


class RexxError(Exception):
    pass


class SubmissionCancelled(Exception):
    pass


class Session:
    def __init__(self, library, functions=(), instruction_limit=100_000):
        if instruction_limit <= 0:
            raise ValueError('instruction limit must be positive')
        self.library = ctypes.CDLL(str(Path(library).resolve()))
        self.api = {}
        pointer, integer, text = ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p
        signatures = {
            'create': ([text], pointer), 'create_next': ([pointer, text], pointer),
            'destroy': ([pointer], None), 'step': ([pointer, integer], integer),
            'register_function': ([pointer, text, integer, integer], integer),
            'reply': ([pointer, integer, text, text], integer),
            'reply_value': ([pointer, text, text], integer),
            'get_variable_json': ([pointer, text], text),
            **{name: ([pointer], text) for name in
               ('text', 'error', 'function', 'arguments_json')},
            'line': ([pointer], integer), 'exit_code': ([pointer], integer),
        }
        for name, (parameters, result) in signatures.items():
            fn = getattr(self.library, 'aether_rexxae_' + name)
            fn.argtypes, fn.restype = parameters, result
            self.api[name] = fn
        self.limit = instruction_limit
        self.functions = tuple(functions)
        self.handlers = {name.upper(): handler for name, _, _, handler in self.functions}
        self.ctx = None
        self.reset()

    @staticmethod
    def _source(source):
        if '\0' in source:
            raise ValueError('source must not contain NUL')
        return source.encode('utf-8')

    def reset(self):
        new = self.api['create'](b'')
        if not new:
            raise MemoryError('cannot create RexxAE context')
        try:
            for name, minimum, maximum, _ in self.functions:
                if '\0' in name or self.api['register_function'](
                        new, name.encode(), minimum, maximum) != 0:
                    raise ValueError('cannot register service ' + name)
            if self.api['step'](new, 1) != 0:
                raise RexxError('cannot initialize empty session')
        except BaseException:
            self.api['destroy'](new)
            raise
        self.close()
        self.ctx = new

    def close(self):
        if self.ctx:
            self.api['destroy'](self.ctx)
            self.ctx = None

    def inspect(self, name):
        if '\0' in name:
            raise ValueError('variable name must not contain NUL')
        encoded = self.api['get_variable_json'](self.ctx, name.encode())
        return None if encoded is None else encoded.decode('utf-8')

    def submit(self, source, output=print):
        if not self.ctx:
            raise RuntimeError('session is closed')
        candidate = self.api['create_next'](self.ctx, self._source(source))
        if not candidate:
            raise RexxError('cannot create next session program')
        adopted = False
        try:
            # Syntax failure never replaces the previous terminal context.
            if self.api['step'](candidate, 0) == -1:
                raise RexxError(self._error(candidate))
            for _ in range(self.limit):
                status = self.api['step'](candidate, 1)
                if status in (0, -1):
                    previous, self.ctx = self.ctx, candidate
                    adopted = True
                    self.api['destroy'](previous)
                    if status == -1:
                        raise RexxError(self._error(candidate))
                    return self.api['exit_code'](candidate)
                if status == 1:
                    output(self.api['text'](candidate).decode('utf-8'))
                elif status == 2:
                    # ADDRESS is data. The console has no mounted environments.
                    self.api['reply'](candidate, 13, b'', b'environment not mounted')
                elif status == 4:
                    name = self.api['function'](candidate).decode('utf-8')
                    arguments = json.loads(self.api['arguments_json'](candidate))
                    try:
                        handler = self.handlers[name]
                        result = json.dumps(handler(*arguments), allow_nan=False).encode()
                        if self.api['reply_value'](candidate, result, b'') != 0:
                            raise ValueError('host reply is outside the supported JSON profile')
                    except Exception as error:
                        detail = str(error).replace('\0', '\\0').encode('utf-8')
                        self.api['reply_value'](candidate, b'null', detail or b'host service refused')
            raise SubmissionCancelled('instruction limit reached; submission discarded')
        finally:
            if not adopted:
                self.api['destroy'](candidate)

    def _error(self, ctx):
        return f"line {self.api['line'](ctx)}: {self.api['error'](ctx).decode('utf-8')}"


HELP = '''RexxAE console: SAY 2 + 3, LET total = 10, or = total * 2
:begin   collect a multiline Rexx program
:run     submit the collected program
:cancel  discard collected input
:show NAME  inspect a variable as JSON (literal property paths)
:reset   clear variables and the selected environment
:quit    exit the console
Ctrl-C cancels input or the active submission. No effect services are mounted.'''


def repl(session, input_stream=sys.stdin, output_stream=sys.stdout, error_stream=sys.stderr):
    interactive = input_stream.isatty()
    block = None
    if interactive:
        print(HELP, file=output_stream)
    while True:
        try:
            if interactive:
                print('... ' if block is not None else 'rexx> ', end='',
                      file=output_stream, flush=True)
            line = input_stream.readline()
            if not line:
                if block is not None:
                    print('error: unfinished block discarded; use :run to submit', file=error_stream)
                return
            line = line.rstrip('\r\n')
            command = line.strip()
            if command in (':quit', ':q'):
                return
            if command == ':cancel':
                block = None
                continue
            if block is not None and command != ':run':
                block.append(line)
                continue
            if command == ':begin':
                block = []
                continue
            if command == ':run':
                if block is None:
                    raise ValueError('no block; use :begin first')
                source, block = '\n'.join(block), None
            elif command == ':help':
                print(HELP, file=output_stream)
                continue
            elif command == ':reset':
                session.reset()
                continue
            elif command.startswith(':show '):
                value = session.inspect(command[6:].strip())
                print('(unset)' if value is None else value, file=output_stream)
                continue
            elif command.startswith(':'):
                raise ValueError('unknown console command; use :help')
            elif command.startswith('='):
                source = 'SAY ' + command[1:].lstrip()
            else:
                source = line
            code = session.submit(source, lambda text: print(text, file=output_stream))
            if code:
                print(f'EXIT {code}', file=output_stream)
        except KeyboardInterrupt:
            block = None
            print('cancelled', file=error_stream)
        except (RexxError, SubmissionCancelled, ValueError) as error:
            print(f'error: {error}', file=error_stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    extension = 'dylib' if sys.platform == 'darwin' else 'so'
    parser.add_argument('library', nargs='?', default=str(
        Path(__file__).resolve().parents[1] / 'build' / ('librexxae.' + extension)))
    parser.add_argument('--instruction-limit', type=int, default=100_000)
    args = parser.parse_args()
    session = Session(args.library, instruction_limit=args.instruction_limit)
    try:
        repl(session)
    finally:
        session.close()


if __name__ == '__main__':
    main()
