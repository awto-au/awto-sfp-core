# Host tests for sfp_core: decode every eeprom/*.hex (diff against test/expected.txt) and run the PHY sequencer on a mock
CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Wno-unused-parameter
SRC = src/sfp_core.c src/sfp_ddm.c src/sfp_phy.c

build/sfp_test: test/sfp_test.c $(SRC) src/sfp_core.h
	@mkdir -p build
	$(CC) $(CFLAGS) -o $@ test/sfp_test.c $(SRC)

build/phy_test: test/phy_test.c $(SRC) src/sfp_core.h
	@mkdir -p build
	$(CC) $(CFLAGS) -o $@ test/phy_test.c $(SRC)

test: build/sfp_test build/phy_test
	build/sfp_test eeprom > build/actual.txt
	diff -u test/expected.txt build/actual.txt && echo "sfp_core: $$(grep -vc '^  ddm' build/actual.txt) modules match test/expected.txt"
	build/phy_test

# regenerate the golden file after a deliberate change (review the diff before committing)
golden: build/sfp_test
	build/sfp_test eeprom > test/expected.txt

clean:
	rm -rf build

.PHONY: test golden clean
