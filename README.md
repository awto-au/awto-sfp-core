# awto-sfp-core

Chip-independent SFP module core for U-Boot ports. Vendored (copy + drift check) by `awto-tl-st1008f`, `awto-unvr` and `awto-unifi-us48`; decision and discussion: awto-tl-st1008f#181.

## Scope
- In the core (pure C, no hardware access except through an ops table):
  - A0h/A2h decode: ID, connector, compliance, vendor/PN/rev/SN/date, checksums (CC_BASE, CC_EXT), partial buffers (`buf, valid_len` in, per-field validity out).
  - Unpad / quirk table keyed by vendor + PN (space-padded GLC-SX-MM, clone GLC-T-TX, FS SFP-10G-T RollBall, ...).
  - Media classification: 1000BASE-X/SX/T, 10GBASE-SR/LR/T, DAC passive/active; "A2h absent" is a normal result.
  - Power class and budget, DDM scaling and thresholds.
  - Copper-module PHY init (88E1111, AQR113C) as register tables plus one small sequencer.
- Not in the core (stays per chip, in each repo): I2C/GPIO access, SerDes/MAC bring-up, RX calibration.

## Ops table (backend contract)
`read(bus, addr, off, buf, len)`, `write(...)`, `delay_ms`, `log`; optional: `select_bus(cage)`, `gpio_presence(cage)`, `tx_disable(cage, on)` (polarity documented per backend), `clear_soft_tx_disable(cage)` step at init (UNVR #345: Linux leaves A2h byte 110 bit 6 set across a warm reboot).

## Rules
- Decode and classify never do I/O, so every repo can unit-test them on host.
- Linux-derived functions (GPL-2.0-only) come from a pinned kernel `sfp.c` / `sfp-bus.c` / `marvell.c` through a generator script (verbatim) plus a stub header; hardware sequences are hand-written and checked by the same script. Headers keep the origin and the pinned kernel version.
- Consumers vendor a copy and fail their gate on drift (`sync_shared.py check|stage`, pattern of awto-dan#109).
- Test corpus: captured EEPROMs of real modules (FS SFP-10GSR-85, FS SFP-10G-T, Cisco GLC-SX-MM, GLC-T, GLC-T-TX clone, CISCO-JPC DAC, Finisar FTLX8571D3BCL, Avago AFBR-57F5AMZ); each repo adds its own.

## Status
- v0 (2026-11-20): `src/sfp_core.[ch]` = unpad, fixups (FS/OEM SFP-10G-T), CC_BASE/CC_EXT, media name, interface support (Linux `parse_support`), quirk table, interface pick, power. Ported from awto-tl-st1008f `rtk_sfpmode.c` / `rtk_sfppower.c` / `cmd_rtk.c`; no I/O.
- Test: `make test` decodes every `eeprom/*.hex` (15 real modules, dumped with `tools/dump_eeprom.py`) and diffs against `test/expected.txt`; `make golden` regenerates it after a reviewed change.
- v1 (2026-11-21): `src/sfp_ddm.c` (`sfp_ddm_decode`: SFF-8472 scaling incl. external calibration, integer only, origin ethtool sfpdiag.c) and `src/sfp_phy.c` (`sfp_phy_identify`, `sfp_phy_init`: 88E1111 SGMII table + sequencer over `struct sfp_phy_ops`; AQR113C recognised, no table: firmware-managed, clause-45, Linux does the host side). `make test` also runs `test/phy_test.c` (mock 88E1111: end state, ID1 realign, reset timeout, I/O failure) and the golden file carries a `ddm` line for the modules with an A2 page.
- Not yet: the Linux-extraction generator, UNVR/US-48 vendoring.
