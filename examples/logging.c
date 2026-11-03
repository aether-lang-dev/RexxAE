/* Static logging and a host-owned clock from C (RexxAE extensions).
 *
 * The script logs through LOG_INFO / LOG_WARN / LOG_DEBUG and works out a
 * schedule with CRON_NEXT. The engine has no clock: the host mounts NOW,
 * which here returns a fixed instant so the run is deterministic. The host
 * sets the threshold (info), names the context, and prints each LOG event
 * with that name. It checks every line it saw and exits non-zero on any
 * difference, so `make test` runs it as a test. */
#include "rexxae.h"
#include <stdio.h>
#include <string.h>

static const char *expected[] = {
    "[nightly] INFO starting {\"job\":\"backup\",\"attempt\":1}",
    "SAY next run 2026-11-04T02:30:00.000Z",
    "[nightly] WARN late by 0 runs {}",
    "SAY after 2026-11-05T02:30:00.000Z",
};

int main(void) {
    const char *source =
        "LET now = NOW()\n"
        "LET tags.job = 'backup'\n"
        "LET tags.attempt = 1\n"
        "CALL LOG_INFO 'starting', tags\n"
        "CALL LOG_DEBUG 'below the threshold: no event'\n"
        "LET at = CRON_NEXT('30 2 * * *', now)\n"
        "SAY 'next run' at\n"
        "LET w = LOG_WARN('late by 0 runs')\n"
        "SAY 'after' CRON_NEXT('30 2 * * *', at)\n";
    RexxAE ctx = aether_rexxae_create(source);
    if (!ctx) return 1;
    int failed = 0, seen = 0, result = 0;
    char line[512];
    if (aether_rexxae_set_log_level(ctx, 7) != -1) failed = 1;  /* out of range */
    if (aether_rexxae_set_log_level(ctx, 2) != 0) failed = 1;   /* info */
    if (aether_rexxae_set_log_name(ctx, "nightly") != 0) failed = 1;
    if (aether_rexxae_register_function(ctx, "NOW", 0, 0) != 0) failed = 1;
    static const char *names[] = {"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"};
    for (;;) {
        int status = aether_rexxae_step(ctx, 100);
        line[0] = '\0';
        if (status == REXXAE_DONE) break;
        if (status == REXXAE_ERROR) {
            fprintf(stderr, "Rexx line %d: %s\n", aether_rexxae_line(ctx), aether_rexxae_error(ctx));
            result = 1;
            break;
        }
        if (status == REXXAE_FUNCTION) {
            /* The host's clock, answered as RexxJS's NOW would format it. */
            if (strcmp(aether_rexxae_function(ctx), "NOW") != 0) failed = 1;
            aether_rexxae_reply_value(ctx, "\"2026-11-03T16:49:32.123Z\"", "");
            continue;
        }
        if (status == REXXAE_LOG) {
            int level = aether_rexxae_log_level(ctx);
            if (level < 0 || level > 5) { failed = 1; continue; }
            snprintf(line, sizeof line, "[%s] %s %s %s", aether_rexxae_log_name(ctx),
                     names[level], aether_rexxae_text(ctx), aether_rexxae_log_tags_json(ctx));
        } else if (status == REXXAE_SAY) {
            snprintf(line, sizeof line, "SAY %s", aether_rexxae_text(ctx));
        } else {
            continue;
        }
        puts(line);
        if (seen >= (int)(sizeof expected / sizeof *expected) || strcmp(line, expected[seen]) != 0) {
            fprintf(stderr, "unexpected line %d: %s\n", seen + 1, line);
            failed = 1;
        }
        ++seen;
    }
    if (seen != (int)(sizeof expected / sizeof *expected)) failed = 1;
    aether_rexxae_destroy(ctx);
    if (failed) fprintf(stderr, "logging example: FAILED\n");
    else printf("C logging host passed: %d events\n", seen);
    return result || failed;
}
