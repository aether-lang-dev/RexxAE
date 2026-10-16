/* A native application steered by embedded Rexx; no JS or service needed. */
#include "rexxae.h"
#include <stdio.h>
#include <string.h>

int main(void) {
    const char *source =
        "CALL increment_twice\n"
        "SAY 'Counter:' RESULT\n"
        "EXIT RC\n"
        "increment_twice:\n"
        "ADDRESS COUNTER\n"
        "'INCREMENT'\n"
        "'INCREMENT'\n"
        "'VALUE'\n"
        "PARSE VAR RESULT count\n"
        "SELECT\n"
        "WHEN count = 2 THEN RETURN count\n"
        "OTHERWISE RETURN 0\n"
        "END\n";
    RexxAE ctx = aether_rexxae_create(source);
    if (!ctx) return 1;
    int counter = 0, result = 0;
    for (;;) {
        int status = aether_rexxae_step(ctx, 100);
        if (status == REXXAE_DONE) {
            result = aether_rexxae_exit_code(ctx);
            break;
        }
        if (status == REXXAE_ERROR) {
            fprintf(stderr, "Rexx line %d: %s\n", aether_rexxae_line(ctx),
                    aether_rexxae_error(ctx));
            result = 1;
            break;
        }
        if (status == REXXAE_SAY) puts(aether_rexxae_text(ctx));
        if (status == REXXAE_COMMAND) {
            const char *address = aether_rexxae_address(ctx);
            const char *command = aether_rexxae_text(ctx);
            char value[32];
            if (strcmp(address, "counter") != 0) {
                aether_rexxae_reply(ctx, 2, "", "unknown environment");
            } else if (strcmp(command, "INCREMENT") == 0) {
                ++counter;
                aether_rexxae_reply(ctx, 0, "", "");
            } else if (strcmp(command, "VALUE") == 0) {
                snprintf(value, sizeof(value), "%d", counter);
                aether_rexxae_reply(ctx, 0, value, "");
            } else {
                aether_rexxae_reply(ctx, 1, "", "unknown command");
            }
        }
    }
    aether_rexxae_destroy(ctx);
    return result;
}
