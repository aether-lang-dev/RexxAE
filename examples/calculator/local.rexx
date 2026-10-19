/* @seeks http.post http://localhost:8080/calculate */
/* @purpose Local calculator operations */
/* Run with the native calculator console: console.ae registers CALC(op, a, b). */
/* CALC is a host-supplied function, not a Rexx builtin or a definition from @seeks. */
/* Its host adapter posts {op, a, b} to the approved endpoint and returns result. */
SAY CALC('add', '0.1', '0.2')
/* Enter SAY CALC('mul', '6', '7') or :quit at the native console. */
