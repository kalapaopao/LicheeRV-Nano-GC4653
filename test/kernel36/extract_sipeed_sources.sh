#!/usr/bin/env bash
set -euo pipefail
BASE=/mnt/d/study/LicheeRV/test
REPO="$BASE/vendor_sipeed_src"
DST="$BASE/kernel36/sipeed_tree"
mkdir -p "$DST"
# Archive only required camera BSP paths. Never checkout Windows-invalid names.
git -C "$REPO" archive --format=tar HEAD \
 linux_5.10/Makefile linux_5.10/Kbuild linux_5.10/Kconfig \
 linux_5.10/arch/riscv linux_5.10/include linux_5.10/scripts \
 linux_5.10/drivers/clk/cvitek linux_5.10/drivers/pinctrl/cvitek \
 osdrv/interdrv/v2/cif osdrv/interdrv/v2/include osdrv/interdrv/v2/base osdrv/interdrv/v2/Makefile.interdrv.param \
 | tar -xf - --exclude='linux_5.10/include/soc/arc/aux.h' --no-same-owner -C "$DST"
echo 'Git archive extract complete'
test -f "$DST/linux_5.10/Makefile"
test -f "$DST/osdrv/interdrv/v2/cif/chip/mars/cif.c"
wc -c "$DST/linux_5.10/Makefile"
