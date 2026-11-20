// SPDX-License-Identifier: GPL-2.0-only
/* Host test: decode every eeprom/*.hex through sfp_core and print one stable line per module (diffed by `make test`). */

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../src/sfp_core.h"

static const char *ifname[] = { "none", "100base-x", "1000base-x", "sgmii", "2500base-x", "10gbase-r" };
#define ALL_IF (SFP_IFBIT(SFP_IF_100BX) | SFP_IFBIT(SFP_IF_1000BX) | SFP_IFBIT(SFP_IF_SGMII) | \
		SFP_IFBIT(SFP_IF_2500BX) | SFP_IFBIT(SFP_IF_10GR))

static size_t load(const char *path, sfp_u8 *buf)
{
	FILE *f = fopen(path, "r");
	char line[256];
	size_t max = 0;

	if (!f)
		return 0;
	while (fgets(line, sizeof(line), f)) {
		unsigned int off, v;
		char *p = line;
		int n;

		if (line[0] == '#' || strncmp(line, "0x", 2))
			continue;
		off = strtoul(line, &p, 16);
		if (*p == ':')
			p++;
		while (sscanf(p, " %2x%n", &v, &n) == 1 && off < 512) {
			buf[off++] = v;
			p += n;
		}
		if (off > max)
			max = off;
	}
	fclose(f);
	return max;
}

static int cmp(const void *a, const void *b)
{
	return strcmp(*(char *const *)a, *(char *const *)b);
}

int main(int argc, char **argv)
{
	const char *dir = argc > 1 ? argv[1] : "eeprom";
	char *names[256];
	int n = 0, i;
	DIR *d = opendir(dir);
	struct dirent *e;

	if (!d) {
		perror(dir);
		return 2;
	}
	while ((e = readdir(d)) && n < 256)
		if (strstr(e->d_name, ".hex"))
			names[n++] = strdup(e->d_name);
	closedir(d);
	qsort(names, n, sizeof(names[0]), cmp);
	for (i = 0; i < n; i++) {
		char path[512], vendor[17], pn[17], sn[17];
		sfp_u8 buf[512] = { 0 };
		const char *why_q, *why_p;
		size_t len;
		unsigned int mask, qmask;
		int phy, padded, fixed, pick, mw, ccb, cce;

		snprintf(path, sizeof(path), "%s/%s", dir, names[i]);
		len = load(path, buf);
		ccb = sfp_cc_base_ok(buf, len);	/* checksums are over the raw bytes, before any repair */
		cce = sfp_cc_ext_ok(buf, len);
		padded = sfp_unpad(buf, len);
		fixed = sfp_fixup(buf, len);
		sfp_field(buf, len, 20, 16, vendor);
		sfp_field(buf, len, 40, 16, pn);
		sfp_field(buf, len, 68, 16, sn);
		mask = sfp_support_mask(buf, len, &phy);
		qmask = sfp_quirk_mask(buf, len, mask, &why_q);
		pick = sfp_pick_if(qmask, ALL_IF, phy);
		mw = sfp_power_mw(buf, len, &why_p);
		printf("%s: %zuB padded=%d fixup=%d ccb=%d cce=%d media=%s mask=0x%02x phy=%d if=%s(%s) power=%dmW(%s) %s/%s/%s\n",
		       names[i], len, padded, fixed, ccb, cce,
		       sfp_media_name(buf, len) ? sfp_media_name(buf, len) : "-", qmask, phy, ifname[pick], why_q,
		       mw, why_p, vendor, pn, sn);
	}
	return 0;
}
