// Print RexxJS's registered core functions and the source file of each, as
// JSON, for tools/tracking.py. Registration is inspected, nothing is called;
// the source file comes from the identity of the exported function, or else
// the module exporting that name, as in tools/inventory.cjs.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
// The real path: require.cache keys are real paths, and ../RexxJS is often a link.
const root = fs.realpathSync(path.resolve(process.argv[2]));
const { RexxInterpreter } = require(path.join(root, 'core/src/interpreter.js'));
const registry = new RexxInterpreter().builtInFunctions;
const identities = new Map(), byName = new Map();
for (const mod of Object.values(require.cache)) {
    if (!mod.filename.startsWith(path.join(root, 'core/src/'))) continue;
    const file = path.relative(root, mod.filename).split(path.sep).join('/');
    // Only uppercase names, as registration uses: a module's lowercase
    // exports (factories, helpers) would otherwise claim every function.
    const note = (name, fn) => {
        if (!/^[A-Z][A-Z0-9_]*$/.test(name) || typeof fn !== 'function') return;
        if (!identities.has(fn)) identities.set(fn, file);
        if (!byName.has(name)) byName.set(name, file);
    };
    for (const [key, value] of Object.entries(mod.exports || {})) {
        note(key, value);
        if (value && typeof value === 'object') for (const [name, fn] of Object.entries(value)) note(name, fn);
    }
}
const functions = Object.entries(registry)
    .filter(([name, fn]) => typeof fn === 'function' && /^[A-Z][A-Z0-9_]*$/.test(name)
        && !name.endsWith('_positional_args_to_named_param_map'))
    .map(([name, fn]) => ({ name, source: identities.get(fn) || byName.get(name) || 'core/src/interpreter-builtin-functions.js' }))
    .sort((a, b) => a.name.localeCompare(b.name));
process.stdout.write(JSON.stringify({ functions }));
