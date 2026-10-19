/* @seeks http.post https://localhost:8443/calculate */
/* @purpose Remote calculator operations */
REQUIRE "calculator"

SAY CALC('add', '0.1', '0.2')
/* Now enter SAY CALC('mul', '6', '7') or :quit at the console. */
