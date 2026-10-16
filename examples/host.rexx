LET inputArray = [1, true]
LET inputObject.message = 'hello'
CALL run inputArray, inputObject
SAY JSON_STRINGIFY(RESULT)
EXIT 0

run:
ARG items, config
LET parsed_message = config.message
PARSE VAR parsed_message word
LET config.message = word
LET payload = TESTHOST(items, config)
SELECT
WHEN payload.continue THEN DO
    DO i = 1 TO 3
        CALL add i, 2
        SAY RESULT
    END
OTHERWISE RETURN JSON_PARSE('null')
END
CALL TESTREPORT
LET report = RESULT
RETURN report

add:
PARSE ARG left, right
CALL TESTADD left, right
LET sum = RESULT
RETURN sum
