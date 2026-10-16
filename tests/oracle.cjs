// Run the SAME source on RexxJS; no source-to-source translation.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(process.argv[2]);
const { parse } = require(path.join(root, 'core/src/parser.js'));
const { RexxInterpreter } = require(path.join(root, 'core/src/interpreter.js'));

(async () => {
    const sources = JSON.parse(fs.readFileSync(0, 'utf8'));
    const results = [];
    for (const entry of sources) {
        const config = typeof entry === 'string' ? { source: entry } : entry;
        const { source } = config;
        const output = [], commands = [], calls = [];
        const interpreter = new RexxInterpreter({
            send: async (address, method, params) => {
                commands.push([address, params.command]);
                return 'host-result';
            }
        }, { output: text => output.push(String(text)) });
        let replyIndex = 0;
        for (const [name] of config.functions || []) {
            interpreter.externalFunctions[name] = (...args) => {
                calls.push([name, args]);
                if (replyIndex >= config.replies.length) throw new Error('test host ran out of replies');
                return config.replies[replyIndex++];
            };
        }
        let execution;
        try { execution = await interpreter.run(parse(source), source); }
        catch (error) {
            if (process.argv.includes('--capture-errors')) {
                results.push({ error: error.message, output, commands, ...(config.functions ? { calls } : {}) });
                continue;
            }
            error.message = `Source:\n${source}\n${error.message}`; throw error;
        }
        const result = { output, commands, exit: Number(execution?.exitCode ?? 0) };
        if (config.functions) result.calls = calls;
        results.push(result);
    }
    process.stdout.write(JSON.stringify(results));
})().catch(error => { console.error(error); process.exit(1); });
