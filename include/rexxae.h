#ifndef REXXAE_H
#define REXXAE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Experimental ABI v0. Each context is confined to one host thread, except
 * aether_rexxae_cancel, which any thread may call (see below).
 * Inputs are copied. Pass non-NULL NUL-terminated UTF-8 strings.
 * Destroy every context. No Aether runtime types cross this interface. */
typedef void *RexxAE;
enum RexxAEStatus {
    REXXAE_ERROR = -1,
    REXXAE_DONE = 0,
    REXXAE_SAY = 1,
    REXXAE_COMMAND = 2,
    REXXAE_RUNNABLE = 3,
    REXXAE_FUNCTION = 4,
    REXXAE_LOG = 5
};

/* REQUIRE "module" [AS alias] requests the explicitly registered REQUIRE
 * function with one or two string arguments. The application resolves modules
 * under its own policy. After replying, register approved exports before the
 * next step. The engine performs no filesystem/network/native module loading. */
RexxAE aether_rexxae_create(const char *source);
/* Start a new program from a DONE or ERROR context. Copies script variables,
 * mounted function registrations and selected ADDRESS environment. The prior
 * context remains valid; destroy both independently. Returns NULL for an active
 * or pending context. Parse errors return a new ERROR context with copied state.
 * Instructions, routine definitions, argv and execution caches are not copied.
 * This is a host operation; scripts cannot use it to acquire services. */
RexxAE aether_rexxae_create_next(RexxAE previous, const char *source);
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
/* Cancel a running or suspended context from ANY thread, including while
 * another thread is inside aether_rexxae_step or the context awaits a
 * COMMAND/FUNCTION reply. The reason (copied, truncated to 1024 bytes, may be
 * empty, non-NULL) is recorded. Returns 0 when recorded, 1 if the context was
 * already cancelled (the first reason is kept), -1 for a NULL context.
 * The engine polls an atomic flag before every instruction and before
 * honouring a pending request, so the next (or current) step returns
 * REXXAE_ERROR within one instruction; a long builtin is not interrupted
 * mid-call. aether_rexxae_error then reads "cancelled by host: <reason>".
 * A pending request is discarded (a later reply returns -1), routine and loop
 * frames are unwound, and every later step keeps returning REXXAE_ERROR.
 * A context already DONE or in ERROR is unchanged. Rexx code cannot catch
 * cancellation: RexxJS has no SIGNAL ON HALT equivalent, so none is offered.
 * The caller must not race aether_rexxae_destroy against cancel; destroy
 * still frees everything after a cancel. */
int32_t aether_rexxae_cancel(RexxAE ctx, const char *reason);
/* Borrowed strings, valid until the next step/reply/destroy. Read text on
 * SAY/COMMAND/LOG, address on COMMAND, error on ERROR. Copy to retain them. */
const char *aether_rexxae_text(RexxAE ctx);
const char *aether_rexxae_address(RexxAE ctx);
const char *aether_rexxae_error(RexxAE ctx);
int32_t aether_rexxae_line(RexxAE ctx);
int32_t aether_rexxae_exit_code(RexxAE ctx);

/* Static logging (RexxAE extension; RexxJS has no equivalent). Scripts call
 * LOG_TRACE, LOG_DEBUG, LOG_INFO, LOG_WARN, LOG_ERROR or LOG_FATAL
 * (message [, tags]); each returns "". The host sets this context's
 * threshold: -1 = off (the default, so no LOG event ever occurs), or
 * 0 trace, 1 debug, 2 info, 3 warn, 4 error, 5 fatal; a message below it
 * produces no event. Returns 0, or -1 for NULL or a level outside -1..5.
 * It may be set at any time, also while an event is pending; scripts cannot
 * read or change it. aether_rexxae_create_next copies it and the name.
 *
 * A message at or above the threshold makes step return REXXAE_LOG. Read
 * aether_rexxae_text (the message), aether_rexxae_log_level and
 * aether_rexxae_log_tags_json (a JSON object of string/number/boolean
 * values, "{}" when the script gave none), then step again; no reply is
 * wanted. As with FUNCTION, registry and variable mutation is rejected while
 * the event is pending, and the instruction resumes without repeating host
 * calls already answered. Cancelling while it is pending ends the script. */
int32_t aether_rexxae_set_log_level(RexxAE ctx, int32_t level);
/* The pending LOG event's level (0..5), or -1 when none is pending. */
int32_t aether_rexxae_log_level(RexxAE ctx);
/* The pending LOG event's tags (borrowed JSON), or NULL when none is pending. */
const char *aether_rexxae_log_tags_json(RexxAE ctx);
/* A label (at most 256 bytes; copied) the host keeps with this context and
 * attaches to its own log output. Scripts cannot see or set it. Returns 0,
 * or -1 for NULL or a longer name. The getter returns "" until it is set. */
int32_t aether_rexxae_set_log_name(RexxAE ctx, const char *name);
const char *aether_rexxae_log_name(RexxAE ctx);

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
