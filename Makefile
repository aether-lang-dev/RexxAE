AE ?= ae
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

.PHONY: reference-audit containment all aether-lib binary-test test spec parity inventory check-inventory memcheck clean
all: $(LIB) build/counter

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

containment: build/test_containment build/test_containment_shared
	./build/test_containment
	./build/test_containment_shared
	python3 tools/check_containment.py --ae $(AE)

spec: build/test_parse build/test_select build/test_routines build/test_functions build/test_execution build/test_function_fixtures build/test_typed build/test_binary_import build/test_binary_shared
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
	./build/counter
	python3 examples/host.py $(LIB)

parity: all
	python3 tests/test_engine.py $(LIB) --oracle $(REXXJS)

# Characterizes migration gaps; parity above remains a strict equality check.
reference-audit: all
	python3 tools/audit_reference.py $(LIB) --oracle $(REXXJS) --spreadsheet ../spraedsheet

inventory:
	node tools/inventory.cjs $(REXXJS)

check-inventory:
	node tools/inventory.cjs $(REXXJS) --check

memcheck: all spec build/test_containment build/test_containment_shared
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

clean:
	rm -rf build
