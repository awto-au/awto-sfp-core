# Host test for sfp_core: decode every eeprom/*.hex and diff against test/expected.txt
CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Wno-unused-parameter

build/sfp_test: test/sfp_test.c src/sfp_core.c src/sfp_core.h
	@mkdir -p build
	$(CC) $(CFLAGS) -o $@ test/sfp_test.c src/sfp_core.c

test: build/sfp_test
	build/sfp_test eeprom > build/actual.txt
	diff -u test/expected.txt build/actual.txt && echo "sfp_core: $$(wc -l < build/actual.txt) modules match test/expected.txt"

# regenerate the golden file after a deliberate change (review the diff before committing)
golden: build/sfp_test
	build/sfp_test eeprom > test/expected.txt

clean:
	rm -rf build

.PHONY: test golden clean
