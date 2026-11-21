// SPDX-License-Identifier: GPL-2.0-only
/* Host test: sfp_phy sequencer against a mock 88E1111 (power-on state = a GLC-T module, st1008f #178). */

#include <stdio.h>
#include <string.h>
#include "../src/sfp_core.h"

struct mock {
	unsigned short reg[32];
	int reset_polls;	/* BMCR reset clears after this many reads; < 0: never */
	int fail_reg;		/* register whose access fails, -1 none */
	int ms;			/* total delay requested */
	int id_off;		/* first ID1 read returns 0x4101 (byte pointer off by one) */
};

static int m_rd(void *c, int r, unsigned short *v)
{
	struct mock *m = c;

	if (r == m->fail_reg)
		return -1;
	if (r == 2 && m->id_off) {
		m->id_off = 0;
		*v = 0x4101;
		return 0;
	}
	if (r == 0 && (m->reg[0] & 0x8000) && m->reset_polls >= 0 && m->reset_polls-- == 0)
		m->reg[0] &= ~0x8000;
	*v = m->reg[r];
	return 0;
}

static int m_wr(void *c, int r, unsigned short v)
{
	struct mock *m = c;

	if (r == m->fail_reg)
		return -1;
	m->reg[r] = v;
	return 0;
}

static void m_delay(void *c, unsigned int ms)
{
	((struct mock *)c)->ms += ms;
}

static void power_on(struct mock *m, unsigned short id1, unsigned short id2)
{
	memset(m, 0, sizeof(*m));
	m->fail_reg = -1;
	m->reg[0] = 0x0140;	/* AN off, 1000 full */
	m->reg[2] = id1;
	m->reg[3] = id2;
	m->reg[0x1b] = 0x9088;
}

static int fails;

static void check(int ok, const char *what)
{
	printf("%s: %s\n", ok ? "PASS" : "FAIL", what);
	fails += !ok;
}

int main(void)
{
	struct mock m;
	struct sfp_phy_ops o = { m_rd, m_wr, m_delay, &m };
	int r;

	power_on(&m, 0x0141, 0x0cc2);
	check(sfp_phy_identify(&o) == SFP_PHY_88E1111, "identify 88E1111");
	r = sfp_phy_init(&o, SFP_PHY_88E1111);
	check(r == 1, "init returns 1");
	check((m.reg[0x1b] & 0xf) == 4 && (m.reg[0x1b] & 0x8000) && !(m.reg[0x1b] & 0x2000), "ext_sr: SGMII w/o clock, auto media");
	check(m.reg[4] == 0x0c01 && m.reg[9] == 0x0200 && m.reg[0] == 0x1200, "ANAR/1000CTRL/BMCR end state");
	check(m.reg[0x16] == 0, "page 0");

	power_on(&m, 0x0141, 0x0cc2);
	m.id_off = 1;
	check(sfp_phy_identify(&o) == SFP_PHY_88E1111, "identify with ID1 byte pointer off by one");

	power_on(&m, 0x0141, 0x0cc2);
	m.reset_polls = -1;
	check(sfp_phy_init(&o, SFP_PHY_88E1111) == -SFP_E_TIMEOUT, "reset never clears: timeout");
	check(m.ms >= 600 && m.ms <= 605 && m.reg[0] == 0x8000, "timeout after 600 ms, no AN restart");

	power_on(&m, 0x0141, 0x0cc2);
	m.fail_reg = 4;
	check(sfp_phy_init(&o, SFP_PHY_88E1111) == -SFP_E_IO, "register access failure: -EIO");

	power_on(&m, 0x31c3, 0x1c12);
	check(sfp_phy_identify(&o) == SFP_PHY_AQR113C && sfp_phy_init(&o, SFP_PHY_AQR113C) == 0 && m.reg[0] == 0x0140,
	      "AQR113C identified, left alone");

	power_on(&m, 0x1234, 0x5678);
	check(sfp_phy_identify(&o) == SFP_PHY_OTHER && sfp_phy_init(&o, SFP_PHY_OTHER) == 0, "unknown PHY: nothing done");

	power_on(&m, 0, 0);
	m.fail_reg = 2;
	check(sfp_phy_identify(&o) == SFP_PHY_NONE && sfp_phy_init(&o, SFP_PHY_NONE) == 0, "no answer: none");
	return fails ? 1 : 0;
}
