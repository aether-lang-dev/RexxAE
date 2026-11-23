# Validated release; README documents requirements and verification status.
# 0.935.0 is a floor move: the worker serves EXPORTed labels through
# std.guest.child's serve_exports and the host's INVOKE, the host-calls-guest
# verb first released in 0.935.0 (aether PR #3802), which stays the floor.
# 0.936.0 is a tracking move, no new primitive needed and no source change.
# 0.939.0 is a tracking move again: nothing here uses the std.http.client
# process-wide pool that 0.939.0 removed (the calculator's one request per call
# keeps a plain request), and no source changed.
AETHER_RELEASE := 0.939.0
AETHER_LOCAL := $(abspath build/toolchains/aether-$(AETHER_RELEASE))
AE ?= $(if $(wildcard $(AETHER_LOCAL)/bin/ae),$(AETHER_LOCAL)/bin/ae,ae)
# A local extracted release must resolve its own compiler and stdlib.
ifeq ($(abspath $(AE)),$(AETHER_LOCAL)/bin/ae)
ifeq ($(strip $(AETHER_HOME)),)
export AETHER_HOME := $(AETHER_LOCAL)
endif
endif
# Otherwise the toolchain AE comes from (<prefix>/bin/ae, or a source tree's
# build/ae). The worker tests' sandboxed spawn finds libaether_sandbox.so
# under AETHER_HOME, which `ae run` sets but a program run from here would not.
# The link is followed first: an ae reached through ~/.local/bin/ae would
# otherwise name ~/.local, whose share/aether can be an older install's stdlib
# (ae-x64 had one from 2026-11-08, and every build failed on it).
ifeq ($(strip $(AETHER_HOME)),)
export AETHER_HOME := $(abspath $(dir $(realpath $(shell command -v $(AE))))/..)
endif
# AETHER_HOME is not enough where ae is reached through a symlink or the
# install keeps its libraries elsewhere (~/.aether/current/lib): spawn_socket
# then finds no preload and every worker test is refused. It honours
# AETHER_SANDBOX_PRELOAD first, so name the library beside the libaether
# that `ae cflags --libs` points at, when there is one.
ifeq ($(strip $(AETHER_SANDBOX_PRELOAD)),)
AE_LIBDIR := $(patsubst -L%,%,$(firstword $(filter -L%,$(shell $(AE) cflags --libs 2>/dev/null))))
ifneq ($(wildcard $(AE_LIBDIR)/libaether_sandbox.so),)
export AETHER_SANDBOX_PRELOAD := $(AE_LIBDIR)/libaether_sandbox.so
endif
endif
CALC_AE ?= $(AE)
CC ?= cc
REXXJS ?= ../RexxJS
# The RexxJS commit `make parity` was last green against (RexxJS's main is the
# reference: track its current head). To move it: `git -C ../RexxJS pull
# --ff-only`, `make parity`, then record the commit parity prints here and in
# README.md "Verification and references".
REXXJS_GREEN := 30fce5c60b9d6000e4a1b0892bc9bb1d25517f69
export REXXJS_GREEN
AETHER_CACHE_DIR ?= $(abspath build/cache)
export AETHER_CACHE_DIR
UNAME_S := $(shell uname -s)
LIBEXT := so
RPATH := $$ORIGIN
ifeq ($(UNAME_S),Darwin)
LIBEXT := dylib
RPATH := @loader_path
endif
LIB := build/librexxae.$(LIBEXT)

.PHONY: repl reference-audit containment all aether-lib binary-test test spec parity inventory check-inventory tracking check-tracking memcheck clean
all: $(LIB) build/counter build/logging

repl: $(LIB)
	python3 examples/repl.py $(LIB)

aether-lib: build/aether/librexxae.$(LIBEXT)

binary-test: build/test_binary_import build/test_binary_shared
	./build/test_binary_import
	./build/test_binary_shared

build:
	mkdir -p $@

$(LIB): $(wildcard src/*.ae) | build
	$(AE) build --emit=lib src/engine.ae -o $@

# The shared library already carries its Aether runtime dependencies.
build/counter: examples/counter.c include/rexxae.h $(LIB)
	$(CC) -std=c11 -Wall -Wextra -Werror -Iinclude $< -Lbuild -lrexxae -Wl,-rpath,'$(RPATH)' -o $@

# Static logging and a host-supplied clock for CRON_NEXT, from C.
build/logging: examples/logging.c include/rexxae.h $(LIB)
	$(CC) -std=c11 -Wall -Wextra -Werror -Iinclude $< -Lbuild -lrexxae -Wl,-rpath,'$(RPATH)' -o $@

build/test_%: tests/test_%.ae $(wildcard src/*.ae) | build
	$(AE) build $< -o $@

build/test_function_fixtures: tests/function_cases.json

build/test_routines: tests/routine_cases.json tests/reference_migration.json

build/test_select: tests/select_cases.json

build/test_parse: tests/parse_cases.json

build/test_trusted_service: examples/services/config.ae

build/aether:
	mkdir -p $@

# Aether binary consumers can use the same self-contained artifact as C,
# or this variant to share one runtime with other Aether libraries.
build/aether/librexxae.$(LIBEXT): $(wildcard src/*.ae) | build/aether
	$(AE) build --emit=lib --shared-runtime src/engine.ae -o $@

build/test_binary_import: tests/test_binary_import.ae $(LIB)
	$(AE) build $< --lib $(abspath build) -o $@

build/test_binary_shared: tests/test_binary_import.ae build/aether/librexxae.$(LIBEXT)
	$(AE) build $< --lib $(abspath build/aether) -o $@

build/test_containment: tests/test_containment.ae examples/services/config.ae $(LIB)
	$(AE) build $< --lib $(abspath build) -o $@

build/test_containment_shared: tests/test_containment.ae examples/services/config.ae build/aether/librexxae.$(LIBEXT)
	$(AE) build $< --lib $(abspath build/aether) -o $@

containment: build/test_containment build/test_containment_shared build/test_trusted_service
	./build/test_containment
	./build/test_containment_shared
	./build/test_trusted_service
	python3 tools/check_containment.py --ae $(AE)

spec: build/test_library build/test_require build/test_session build/test_call build/test_cron build/test_logging build/test_parse build/test_select build/test_routines build/test_functions build/test_execution build/test_function_fixtures build/test_typed build/test_binary_import build/test_binary_shared
	./build/test_library
	./build/test_require
	./build/test_session
	./build/test_call
	./build/test_cron
	./build/test_logging
	./build/test_functions
	./build/test_execution
	./build/test_function_fixtures
	./build/test_typed
	./build/test_routines
	./build/test_select
	./build/test_parse
	./build/test_binary_import
	./build/test_binary_shared

test: all spec containment
	python3 tests/test_engine.py $(LIB)
	python3 tests/test_resource_cleanup.py $(LIB)
	python3 tests/test_repl.py $(LIB)
	./build/counter
	./build/logging
	python3 examples/host.py $(LIB)

parity: all build/test_require
	python3 tests/test_require_reference.py $(LIB) $(REXXJS)
	python3 tests/test_engine.py $(LIB) --oracle $(REXXJS)
	python3 tools/tracking.py $(LIB) $(REXXJS) --check

# docs/rexxjs-tracking.md: RexxJS and RexxAE against each other, every
# feature probe run on both engines (tools/tracking.py says how it is read).
tracking: all
	python3 tools/tracking.py $(LIB) $(REXXJS)

check-tracking: all
	python3 tools/tracking.py $(LIB) $(REXXJS) --check

# Characterizes migration gaps; parity above remains a strict equality check.
reference-audit: all
	python3 tools/audit_reference.py $(LIB) --oracle $(REXXJS) --spreadsheet ../spraedsheet --probes tests/reference_update_20261019.json

inventory:
	node tools/inventory.cjs $(REXXJS)

check-inventory:
	node tools/inventory.cjs $(REXXJS) --check

memcheck: all spec build/test_containment build/test_containment_shared build/test_trusted_service
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_library
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_require
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_session
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_call
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/counter
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/logging
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_cron
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_logging
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_functions
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_execution
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_function_fixtures
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_typed
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_routines
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_select
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_parse
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_binary_import
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_binary_shared
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_containment
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_containment_shared
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_trusted_service

clean:
	rm -rf build

.PHONY: calculator calculator-test calculator-integration
calculator: build/calculator/calculator-service build/calculator/calculator-console build/calculator/test_protocol build/calculator/test_service build/calculator/test_downloaded

build/calculator:
	mkdir -p $@

build/calculator/librexxae.$(LIBEXT): $(wildcard src/*.ae) | build/calculator
	$(CALC_AE) build --emit=lib src/engine.ae -o $@

build/calculator/calculator-service: examples/calculator/calculator-service.ae examples/calculator/protocol.ae examples/calculator/policy.ae examples/calculator/tls_config.ae | build/calculator
	$(CALC_AE) build $< -o $@

build/calculator/calculator-console: examples/calculator/calculator-console.ae examples/calculator/consent.ae examples/calculator/downloaded.ae examples/calculator/modules.ae examples/calculator/service.ae examples/calculator/policy.ae examples/calculator/protocol.ae build/calculator/librexxae.$(LIBEXT)
	$(CALC_AE) build $< --lib $(abspath build/calculator) -o $@

build/calculator/test_protocol: tests/test_calculator.ae examples/calculator/protocol.ae examples/calculator/policy.ae | build/calculator
	$(CALC_AE) build $< -o $@

build/calculator/test_service: tests/test_calculator_service.ae examples/calculator/service.ae examples/calculator/protocol.ae examples/calculator/policy.ae | build/calculator
	$(CALC_AE) build $< -o $@

calculator-test: calculator
	./build/calculator/test_protocol
	./build/calculator/test_service
	./build/calculator/test_downloaded
	python3 tests/test_calculator_console.py

calculator-integration:
	python3 tools/test_calculator_tls.py --ae $(CALC_AE)

build/test_require: examples/calculator/modules.ae

build/calculator/test_downloaded: tests/test_downloaded_calculator.ae examples/calculator/downloaded.ae examples/calculator/policy.ae examples/calculator/service.ae examples/calculator/protocol.ae build/calculator/librexxae.$(LIBEXT)
	$(CALC_AE) build $< --lib $(abspath build/calculator) -o $@

# The worker process (worker/, README "Worker process"): a separate
# component with its own build directory. It is built on Aether's std.guest
# (the host's side) and std.guest.child (the worker's); serving exported
# labels (READY and INVOKE) needs the AETHER_RELEASE here, 0.935.0.
# It is not part of `make test`; run it with `make worker-test`.
.PHONY: worker worker-test
worker: build/worker/rexxae-worker

build/worker:
	mkdir -p $@

build/worker/rexxae-worker: worker/worker.ae $(wildcard src/*.ae) | build/worker
	$(AE) build $< -o $@

build/worker/silent: tests/worker_silent.ae | build/worker
	$(AE) build $< -o $@

build/worker/test_worker: tests/test_worker.ae worker/rexxworker/module.ae | build/worker
	$(AE) build $< --lib worker -o $@

worker-test: build/worker/rexxae-worker build/worker/silent build/worker/test_worker
	./build/worker/test_worker
