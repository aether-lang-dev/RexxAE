/* @seeks http.post http://localhost:8080/calculate */
/* @purpose Local calculator operations */
/* @seeks http.get /static/calculator.rexx */
REQUIRE "/static/calculator.rexx"

SAY CALC('add', '0.1', '0.2')
/* Enter SAY CALC('mul', '6', '7') or :quit at the native console. */
