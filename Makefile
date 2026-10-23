# Validated release; README documents requirements and verification status.
AETHER_RELEASE := 0.841.0
AETHER_LOCAL := $(abspath build/toolchains/aether-$(AETHER_RELEASE))
AE ?= $(if $(wildcard $(AETHER_LOCAL)/bin/ae),$(AETHER_LOCAL)/bin/ae,ae)
# A local extracted release must resolve its own compiler and stdlib.
ifeq ($(abspath $(AE)),$(AETHER_LOCAL)/bin/ae)
ifeq ($(strip $(AETHER_HOME)),)
export AETHER_HOME := $(AETHER_LOCAL)
endif
endif
CALC_AE ?= $(AE)
CC ?= cc
REXXJS ?= ../RexxJS
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

.PHONY: repl reference-audit containment all aether-lib binary-test test spec parity inventory check-inventory memcheck clean
all: $(LIB) build/counter

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

spec: build/test_require build/test_session build/test_parse build/test_select build/test_routines build/test_functions build/test_execution build/test_function_fixtures build/test_typed build/test_binary_import build/test_binary_shared
	./build/test_require
	./build/test_session
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
	python3 tests/test_repl.py $(LIB)
	./build/counter
	python3 examples/host.py $(LIB)

parity: all build/test_require
	python3 tests/test_require_reference.py $(LIB) $(REXXJS)
	python3 tests/test_engine.py $(LIB) --oracle $(REXXJS)

# Characterizes migration gaps; parity above remains a strict equality check.
reference-audit: all
	python3 tools/audit_reference.py $(LIB) --oracle $(REXXJS) --spreadsheet ../spraedsheet --probes tests/reference_update_20261019.json

inventory:
	node tools/inventory.cjs $(REXXJS)

check-inventory:
	node tools/inventory.cjs $(REXXJS) --check

memcheck: all spec build/test_containment build/test_containment_shared build/test_trusted_service
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_require
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/test_session
	valgrind --leak-check=full --errors-for-leak-kinds=definite --error-exitcode=99 ./build/counter
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
