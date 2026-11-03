"""Compile-time escape probes; a denial must be a relevant compiler diagnostic."""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--ae', default='ae')
args = p.parse_args()
engine_source = Path('src/engine.ae').read_text()
public = re.findall(r'^rexxae_[a-z_]+(?=\()', engine_source, re.MULTILINE)
if not public or any(not re.search(r'@pure\s+' + name + r'\(', engine_source) for name in public):
    raise SystemExit('Every public engine entry point must retain its @pure effect guard')
print(f'{len(public)} public engine entry points retain @pure guards')
# This is a reviewed guest API snapshot, like sae/tests/spec_globals.ae.
surface = json.loads(Path('tests/guest_functions.json').read_text())
expected_functions = set(surface['rexxjs'])
expected_extensions = set(surface['rexxae_extensions'])
functions = set()
extensions = set()
allowed_std = {'std.string', 'std.map', 'std.json', 'std.math', 'std.strbuilder', 'std.list',
                'std.sync', 'std.mem', 'std.bytes'}  # last three: cancel flag only, no authority
for path in Path('src').glob('*.ae'):
    source = path.read_text()
    for names in re.findall(r'const (?:TEXT|MATH|VALUE)_FUNCTIONS = "([^"]+)"', source):
        functions.update(names.split())
    for names in re.findall(r'const EXTENSION_FUNCTIONS = "([^"]+)"', source):
        extensions.update(names.split())
    for module in re.findall(r'^import\s+(\S+)', source, re.MULTILINE):
        if not module.startswith('src.') and module not in allowed_std:
            raise SystemExit(f'{path}: unreviewed engine import {module}')
if functions != expected_functions:
    raise SystemExit(f'Guest function surface changed: added={functions - expected_functions}, removed={expected_functions - functions}')
service_imports = set(re.findall(r'^import\s+(\S+)', Path('examples/services/config.ae').read_text(), re.MULTILINE))
if service_imports != {'std.file', 'std.sandbox', 'std.map', 'std.string'}:
    raise SystemExit('Configuration service imports widened or changed; review its effect boundary')
if extensions != expected_extensions:
    raise SystemExit(f'RexxAE extension surface changed: added={extensions - expected_extensions}, removed={expected_extensions - extensions}')
if functions & extensions:
    raise SystemExit(f'Names listed both as RexxJS functions and as extensions: {functions & extensions}')
print(f'{len(functions)} guest functions, {len(extensions)} RexxAE extensions and engine/service import boundaries match the reviewed surface')
# The worker process (worker/) is a separate component with its own reviewed
# allowance; it never widens the engine's list above. The protocol, the
# lockdown and the PROBE self-check (which touches fs and tcp, inside the
# no-grant enforce) are Aether's std.guest.child; the worker is the engine
# glue, and child.run, which enters sandbox.enforce with no grants, is the
# only place it steps the engine.
worker_source = Path('worker/worker.ae').read_text()
worker_imports = set(re.findall(r'^import\s+(\S+)', worker_source, re.MULTILINE))
if worker_imports != {'std.guest.child', 'std.string', 'src.engine'}:
    raise SystemExit(f'Worker imports changed: {sorted(worker_imports)}; review its effect boundary')
locked = worker_source.find('child.run(h) callback {')
first_step = worker_source.find('run_script(ctx, h)')
if locked < 0 or not (locked < first_step):
    raise SystemExit('The worker must run its script inside child.run (no-grant sandbox.enforce)')
if worker_source.count('run_script(ctx, h)') != 1 or worker_source.count('engine.rexxae_step(') != 1:
    raise SystemExit('The worker steps the engine from one place, inside child.run')
host_source = Path('worker/rexxworker/module.ae').read_text()
host_imports = set(re.findall(r'^import\s+(\S+)', host_source, re.MULTILINE))
if host_imports != {'std.guest', 'std.sandbox'}:
    raise SystemExit(f'Worker host alias imports changed: {sorted(host_imports)}')
if 'spawn_socket' in host_source:
    raise SystemExit('The deprecated host alias forwards to std.guest; it spawns nothing itself')
print('worker and its host alias match their reviewed imports; the worker runs its script inside child.run')
cases = [
    ('filesystem', 'import std.fs\nexports(probe)\nprobe() { fs.read("/etc/passwd") }', ['--emit=lib'], ('--emit=lib rejects',)),
    # Since Aether 0.859.0 --emit=lib refuses std.file (and std.dir) itself;
    # this probe holds that gate. The two @pure probes grant fs with
    # --with=fs so that @pure, not the import gate, is what refuses them.
    ('file_module', 'import std.file\nexports(probe)\nprobe() { file.read("/etc/passwd") }', ['--emit=lib'], ('--emit=lib rejects',)),
    ('pure_file_wrapper', 'import std.file\nexports(probe)\n@pure\nprobe() { file.read("/etc/passwd") }', ['--emit=lib', '--with=fs'], ('but reaches a',)),
    ('network', 'import std.tcp\nexports(probe)\nprobe() { tcp.connect("127.0.0.1", 1) }', ['--emit=lib'], ('--emit=lib rejects',)),
    ('process', 'import std.os\nexports(probe)\nprobe() { os.system("true") }', ['--emit=lib'], ('--emit=lib rejects',)),
    ('foreign_symbol', 'exports(probe)\nextern system(cmd: string) -> int\nprobe() -> int { return system("true") }', ['--emit=lib'], ('without --with=extern',)),
    ('sealed_read', 'main() {\n secret = "private"\n if true {\n seal except println\n println(secret)\n }\n}', [], ('is hidden in this scope',)),
    ('sealed_write', 'main() {\n secret = "private"\n if true {\n seal except println\n secret += "new"\n }\n}', [], ('is hidden in this scope',)),
    ('sealed_nested_read', 'main() {\n secret = "private"\n if true {\n seal except println\n if true { println(secret) }\n }\n}', [], ('is hidden in this scope',)),
    ('pure_transitive_file', 'import std.file\nhelper() { file.read("/etc/passwd") }\nexports(probe)\n@pure\nprobe() { helper() }', ['--emit=lib', '--with=fs'], ('but reaches a',)),
    ('trusted_value_escape', 'import std.sandbox\nservice() {}\nmain() {\n w = sandbox.new("none") {}\n sandbox.enforce(w, service) callback {\n escaped = service\n call(escaped)\n }\n sandbox.free(w)\n}', [], ('only be called, not used as a value',)),
    ('trusted_extern', 'import std.sandbox\nextern system(cmd: string) -> int\nmain() {\n w = sandbox.new("none") {}\n sandbox.enforce(w, system) callback { system("true") }\n sandbox.free(w)\n}', [], ('it is a c extern',)),
]
with tempfile.TemporaryDirectory(prefix='rexxae-compile-containment-') as tmp:
    root = Path(tmp)
    env = dict(os.environ, AETHER_CACHE_DIR=str(Path('build/cache').resolve()))
    for name, source, flags, diagnostic in cases:
        path = root / (name + '.ae')
        path.write_text(source + '\n')
        result = subprocess.run([args.ae, 'build', str(path), *flags, '-o', str(root / name)],
                                capture_output=True, text=True, timeout=60, env=env)
        output = result.stdout + result.stderr
        if result.returncode == 0:
            raise SystemExit(f'Containment failure: {name} unexpectedly compiled')
        if not any(word in output.lower() for word in diagnostic):
            raise SystemExit(f'{name} failed for an unrelated reason:\n{output}')
        print(f'Compiler refused {name}')
print(f'{len(cases)} compile-time containment probes passed')
