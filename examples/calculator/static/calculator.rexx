/* @exports CALC */
/* @seeks http.post /calculate */
/* @purpose Remote calculator operations */

CALC: PROCEDURE
ARG operation, left, right
LET request = {op:operation, a:left, b:right}
LET response = HTTP_POST('/calculate', request)
RETURN JSON_GET(response, 'result')
