// Inspect core registration without invoking functions. Extras are read as
// source/manifests only, so no optional npm packages or external tools run.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { builtinModules } = require('node:module');
const here = path.resolve(__dirname, '..');
const root = path.resolve(process.argv[2] || path.join(here, '../RexxJS'));
const check = process.argv.includes('--check');
const { RexxInterpreter } = require(path.join(root, 'core/src/interpreter.js'));
const registry = new RexxInterpreter().builtInFunctions;
const relative = p => path.relative(root, p).split(path.sep).join('/');
const read = p => fs.readFileSync(p, 'utf8');
function revision(repo) {
    let git = path.join(repo, '.git');
    if (fs.statSync(git).isFile()) git = path.resolve(repo, read(git).trim().replace(/^gitdir:\s*/, ''));
    const head = read(path.join(git, 'HEAD')).trim();
    if (!head.startsWith('ref: ')) return head;
    const ref = head.slice(5);
    const commonFile = path.join(git, 'commondir');
    const common = fs.existsSync(commonFile) ? path.resolve(git, read(commonFile).trim()) : git;
    for (const dir of [git, common]) {
        const loose = path.join(dir, ref);
        if (fs.existsSync(loose)) return read(loose).trim();
    }
    const packed = path.join(common, 'packed-refs');
    if (fs.existsSync(packed)) {
        for (const line of read(packed).split('\n')) if (line.endsWith(' ' + ref)) return line.split(' ')[0];
    }
    throw new Error(`Cannot resolve reference ${ref}`);
}
const plumbing = new Set(['webpack', 'webpack-cli', 'buffer', 'process', 'util',
    'crypto-browserify', 'os-browserify', 'path-browserify', 'stream-browserify']);
const nodeBuiltins = new Set(builtinModules.map(n => n.replace(/^node:/, '')));

function walk(dir) {
    if (!fs.existsSync(dir)) return [];
    return fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))
        .flatMap(e => {
            if (['node_modules', '.git', 'dist', 'build', '__tests__', 'tests', 'comparison-tests'].includes(e.name)) return [];
            const p = path.join(dir, e.name);
            return e.isDirectory() ? walk(p) : [p];
        });
}

function imports(source) {
    return [...new Set([...source.matchAll(/\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)/g),
        ...source.matchAll(/^[ \t]*import\s+[^;\n]*?\bfrom\s+['"]([^'"]+)['"]/gm)].map(m => m[1]))].sort();
}

const candidates = new Map(), identities = new Map();
function register(name, fn, file) {
    if (!/^[A-Z][A-Z0-9_]*$/.test(name) || typeof fn !== 'function') return;
    if (!identities.has(fn)) identities.set(fn, file);
    if (!candidates.has(name)) candidates.set(name, []);
    candidates.get(name).push(file);
}
for (const mod of Object.values(require.cache)) {
    if (!mod.filename.startsWith(path.join(root, 'core/src/'))) continue;
    const file = relative(mod.filename);
    for (const [key, value] of Object.entries(mod.exports || {})) {
        register(key, value, file);
        if (value && typeof value === 'object') {
            for (const [name, fn] of Object.entries(value)) register(name, fn, file);
        }
    }
}
const nativeSource = fs.readdirSync(path.join(here, 'src')).filter(p => p.endsWith('.ae')).sort()
    .map(p => read(path.join(here, 'src', p))).join('\n');
const implemented = new Set([...nativeSource.matchAll(/const (?:TEXT|MATH|VALUE)_FUNCTIONS = "([^"]+)"/g)]
    .flatMap(m => m[1].trim().split(/\s+/)));
const scalar = new Set([...nativeSource.matchAll(/const (?:TEXT|MATH)_FUNCTIONS = "([^"]+)"/g)]
    .flatMap(m => m[1].trim().split(/\s+/)));

function policy(name, file) {
    if (implemented.has(name)) return scalar.has(name)
        ? ['native-scalar', 'std.string/std.map/std.math', 'implemented-profile']
        : ['native-values', 'std.json; typed evaluator and lazy IF', 'implemented-profile'];
    if (['INTERPRET_JS', 'JS_SHOW'].includes(name)) return ['omit-js-runtime', '', 'proposed-omission'];
    if (/dom/.test(file) || name === 'SHOW') return ['host-ui', 'host API; optional rendering module', 'planned'];
    if (/file-functions|path-functions|http-functions/.test(file)) return ['host-effects', 'std.fs/std.path/std.http behind host grants', 'planned'];
    if (/shell-functions/.test(file)) {
        if (/^(BASENAME|DIRNAME|PATH_|HEAD$|TAIL$|WC$|SORT$|UNIQ$|CUT$|PASTE$|SEQ$|NL$|REV$|TAC$|FOLD$|EXPAND$|DOS2UNIX$|UNIX2DOS$|FMT$|STRINGS$|CMP$|COMM$|CRC32$|CKSUM$|SUM_BSD$|UUENCODE$|UUDECODE$|BASE32$|XXD$|HEXDUMP$|OD$|FACTOR$|ASCII$|TRUE$|FALSE$|GETOPT$)/.test(name))
            return ['native-utility-review', 'std.string/std.path/std.encoding/std.hash', 'planned'];
        return ['host-effects', 'host services; std.fs/std.os where authorized', 'planned'];
    }
    if (/json-functions|array-functions|data-functions/.test(file)) return ['native-typed-values', 'std.json/std.list/std.map; contrib.parsers.xml_expat', 'planned'];
    if (/date-time/.test(file)) return ['native-time', 'std.time; host clock for NOW/default dates', 'planned'];
    if (/cryptography|random-functions/.test(file)) return ['native-crypto-review', 'std.cryptography/std.encoding/std.uuid/std.nanoid; host entropy', 'planned'];
    if (/regex|validation/.test(file)) return ['native-patterns', 'std.regex/std.schema; JS RegExp compatibility fixtures', 'planned'];
    if (/statistics|probability/.test(file)) return ['optional-numerics', 'std.math/std.floatarr; algorithms and RNG profile required', 'planned'];
    if (/logic/.test(file)) return ['native-language', 'typed values and lazy expression evaluation', 'planned'];
    if (/url-functions/.test(file)) return ['native-url', 'std.url/std.encoding', 'planned'];
    if (/string-functions/.test(file)) return ['native-text-review', 'std.string/std.unicode; typed returns for text analysis', 'planned'];
    if (name === 'GETENV') return ['host-effects', 'host environment provider', 'planned'];
    return ['native-language-review', 'execution frames, modules, stack and diagnostics', 'planned'];
}

const core = Object.entries(registry).filter(([name, fn]) =>
    typeof fn === 'function' && !name.endsWith('_positional_args_to_named_param_map'))
    .sort(([a], [b]) => a.localeCompare(b)).map(([name, fn]) => {
        const file = identities.get(fn) || (candidates.get(name) || [])[0] || 'core/src/interpreter-builtin-functions.js';
        const [disposition, aether, status] = policy(name, file);
        return { name, source: file, disposition, aether, status };
    });
const helpers = Object.keys(registry).filter(n => n.endsWith('_positional_args_to_named_param_map')).sort();
const coreSources = [...new Set(core.map(f => f.source))].sort().map(source => ({ source,
    externalImports: imports(read(path.join(root, source))).filter(n => !n.startsWith('.')).map(name => ({
        name, kind: nodeBuiltins.has(name.replace(/^node:/, '')) ? 'node-builtin' : 'npm-or-external'
    }))
}));

function extraPolicy(source) {
    if (/jq/.test(source)) return ['optional-native', 'contrib.jq already implements jq; test dialect/API differences'];
    if (/sqlite|duckdb/.test(source)) return ['optional-database', 'contrib.sqlite available; DuckDB needs its own native dependency'];
    if (/minimatch/.test(source)) return ['optional-native', 'std.string.glob_match is a starting point, not minimatch parity'];
    if (/graphviz/.test(source)) return ['optional-host-rendering', 'native Graphviz dependency and output adapter; exclude WASM loader'];
    if (/numpy-via-pyoide|pyodide/.test(source)) return ['omit-browser-runtime', 'proposed omission of browser Python/WASM delivery; native numerical API may remain'];
    if (/numpy|scipy|matlab|sympy|r-inspired/.test(source)) return ['optional-numerics', 'std.math/std.floatarr cover primitives; dedicated algorithms/backends need evaluation'];
    if (/excel/.test(source)) return ['optional-formula-library', 'spreadsheet formulas are useful; browser polyfills are replaceable infrastructure'];
    if (/diff|sed/.test(source)) return ['optional-native-port', 'port required algorithms with fixtures; no complete stdlib substitute claimed'];
    if (/extras\/addresses/.test(source)) return ['host-adapter', 'application/remote-service adapter supplied explicitly by host'];
    return ['review', 'inspect implementation and demand before selecting a native replacement'];
}
const files = walk(path.join(root, 'extras'));
const packages = files.filter(p => p.endsWith('/package.json')).map(p => {
    const data = JSON.parse(read(p)), source = relative(p);
    const [disposition, rationale] = extraPolicy(source);
    return { source, package: data.name || '', disposition, rationale,
        dependencies: Object.entries(data.dependencies || {}).sort(([a], [b]) => a.localeCompare(b))
            .map(([name, version]) => ({ name, version, kind: plumbing.has(name) ? 'browser-build-plumbing' : 'feature-dependency' })),
        developmentDependencies: Object.keys(data.devDependencies || {}).sort() };
});
// Static candidates are explicitly not an exhaustive or loaded function list.
const extraSources = files.filter(p => /\.js$/.test(p) && !/test|spec|webpack|bundle|render/i.test(path.basename(p)))
    .map(p => {
        const text = read(p), source = relative(p);
        const names = [...new Set([...text.matchAll(/['"]([A-Z][A-Z0-9_]*)['"]\s*:\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>)/g)].map(m => m[1]))].sort();
        const externalImports = imports(text).filter(n => !n.startsWith('.'));
        const [disposition, rationale] = extraPolicy(source);
        return { source, disposition, rationale, staticFunctionCandidates: names, externalImports };
    }).filter(entry => entry.staticFunctionCandidates.length || entry.externalImports.length);
const registered = new Set(core.map(f => f.name));
for (const name of implemented) if (!registered.has(name)) throw new Error(`Native builtin absent from reference registry: ${name}`);
const goldenCases = JSON.parse(read(path.join(here, 'tests/function_cases.json')));
const covered = new Set(goldenCases.map(([, expression]) => (expression.match(/^([A-Z][A-Z0-9_]*)/) || [])[1]));
for (const name of implemented) if (!covered.has(name)) throw new Error(`Native builtin needs a golden function fixture: ${name}`);
if (new Set(goldenCases.map(([name]) => name)).size !== goldenCases.length) throw new Error('Duplicate golden function fixture names');
const report = {
    schema: 1, referenceRevision: revision(root),
    methodology: 'Live core registration, loaded source export identity, literal imports and extras manifests/static candidates. No extra modules loaded or functions invoked. Dispositions are provisional.',
    counts: { registeredNames: Object.keys(registry).length, languageFunctions: core.length, converterHelpers: helpers.length,
        nativeFunctions: implemented.size, nativeScalarFunctions: scalar.size,
        nativeValueFunctions: implemented.size - scalar.size, extraPackageManifests: packages.length },
    core, converterHelpers: helpers, coreSources, packages, extraSources
};
const groups = {};
for (const fn of core) (groups[fn.disposition] ||= []).push(fn);
let md = '# Function inventory\n\nGenerated by `make inventory`; do not edit this file manually.\n\n';
md += `Reference: RexxJS \`${report.referenceRevision}\`. ${report.counts.registeredNames} registered names comprise ${core.length} callable language functions and ${helpers.length} argument-converter helpers. ${implemented.size} functions have native implementations (${scalar.size} scalar, ${implemented.size - scalar.size} typed-value functions) with restrictions documented in [function-policy.md](function-policy.md).\n\n`;
md += 'This is an inventory and provisional disposition, not a compatibility claim. See the JSON companion for per-function source, npm manifests, import evidence and conservative static candidates in extras. Core is inspected through registration; extras are never loaded.\n\n';
for (const [group, functions] of Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))) {
    md += `## ${group} (${functions.length})\n\n| Function | Reference source | Aether route | Status |\n|---|---|---|---|\n`;
    for (const fn of functions) md += `| ${fn.name} | ${fn.source.replace('core/src/', '')} | ${fn.aether || '—'} | ${fn.status} |\n`;
    md += '\n';
}
md += '## Optional package manifests\n\nFeature dependencies are separated from browser/build plumbing (Webpack, polyfills). Development dependencies remain in JSON. Manifest declarations alone do not prove a package is called on every path.\n\n| Package path | Proposed route | Feature dependencies | Browser/build plumbing |\n|---|---|---|---|\n';
for (const p of packages) md += `| ${p.source} | ${p.disposition} | ${p.dependencies.filter(d => d.kind === 'feature-dependency').map(d => d.name).join(', ') || '—'} | ${p.dependencies.filter(d => d.kind === 'browser-build-plumbing').map(d => d.name).join(', ') || '—'} |\n`;
const outputs = [['docs/function-inventory.json', JSON.stringify(report, null, 2) + '\n'], ['docs/function-inventory.md', md]];
for (const [file, contents] of outputs) {
    const target = path.join(here, file);
    if (check) {
        if (!fs.existsSync(target) || read(target) !== contents) throw new Error(`${file} is stale; run make inventory`);
    } else fs.writeFileSync(target, contents);
}
console.log(`${check ? 'Checked' : 'Inventoried'} ${core.length} core functions, ${helpers.length} converters, ${packages.length} optional manifests, ${extraSources.length} optional source candidates`);
