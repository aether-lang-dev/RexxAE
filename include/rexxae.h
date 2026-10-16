#ifndef REXXAE_H
#define REXXAE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Experimental ABI v0. Each context is confined to one host thread.
 * Inputs are copied. Pass non-NULL NUL-terminated UTF-8 strings.
 * Destroy every context. No Aether runtime types cross this interface. */
typedef void *RexxAE;
enum RexxAEStatus {
    REXXAE_ERROR = -1,
    REXXAE_DONE = 0,
    REXXAE_SAY = 1,
    REXXAE_COMMAND = 2,
    REXXAE_RUNNABLE = 3,
    REXXAE_FUNCTION = 4
};

RexxAE aether_rexxae_create(const char *source);
void aether_rexxae_destroy(RexxAE ctx);
/* Execute at most budget instructions; budget <= 0 executes none.
 * COMMAND/FUNCTION repeat until reply; DONE and ERROR are terminal.
 * Expression results and routine frames survive pending host requests.
 * CALL/RETURN transitions consume budget; routine depth is limited to 128.
 * Plain routines share variables/arguments; PROCEDURE isolates script variables
 * and restores caller arguments. EXPOSE propagates selected names/roots. */
int32_t aether_rexxae_step(RexxAE ctx, int32_t budget);
int32_t aether_rexxae_reply(RexxAE ctx, int32_t rc,
                           const char *result, const char *error_text);
/* Borrowed strings, valid until the next step/reply/destroy. Read text on
 * SAY/COMMAND, address on COMMAND, error on ERROR. Copy to retain them. */
const char *aether_rexxae_text(RexxAE ctx);
const char *aether_rexxae_address(RexxAE ctx);
const char *aether_rexxae_error(RexxAE ctx);
int32_t aether_rexxae_line(RexxAE ctx);
int32_t aether_rexxae_exit_code(RexxAE ctx);

/* Register an application function before or between steps. Names are
 * case-insensitive; builtins cannot be replaced. Arity is checked before
 * dispatch (0 <= min <= max <= 256). Host calls use positional arguments.
 * Functions yield REXXAE_FUNCTION; the host handles the request and replies.
 * All registration/mutation APIs reject calls while a request is pending. */
int32_t aether_rexxae_register_function(RexxAE ctx, const char *name,
                                       int32_t min_args, int32_t max_args);
const char *aether_rexxae_function(RexxAE ctx);
const char *aether_rexxae_arguments_json(RexxAE ctx);
/* Argument convenience getters during FUNCTION. Type codes follow JSON:
 * null=0, boolean=1, number=2, string=3, array=4, object=5; invalid=-1.
 * text returns the Rexx display value, borrowed until the next context call.
 * arguments_json retains the complete structure and escaped string data. */
int32_t aether_rexxae_argument_type(RexxAE ctx, int32_t index);
const char *aether_rexxae_argument_text(RexxAE ctx, int32_t index);
/* Reply with one JSON value (number/string/bool/null/array/object), or a
 * nonempty error_text. Malformed/deep JSON returns -1 and leaves the call
 * pending for correction. An accepted host error terminates the script.
 * Requests and replies copy data. No callback or foreign stack is retained. */
int32_t aether_rexxae_reply_value(RexxAE ctx, const char *json_value,
                                 const char *error_text);
/* Typed variable access. Getter returns NULL for an unset/unrepresentable
 * value, otherwise borrowed JSON until the next context call. Setter copies
 * JSON and rejects malformed values and calls during a pending request.
 * Names with dots address literal object paths; tails are not substituted.
 * Arrays can be read using zero-based numeric paths, but nested writes
 * through arrays are unsupported and return -1 without changing the root.
 * JSON excludes nonfinite numbers; these remain internal numeric values. */
const char *aether_rexxae_get_variable_json(RexxAE ctx, const char *name);
int32_t aether_rexxae_set_variable_json(RexxAE ctx, const char *name,
                                       const char *json_value);

#ifdef __cplusplus
}
#endif
#endif
