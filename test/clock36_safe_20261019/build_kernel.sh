#!/usr/bin/env bash
# Experimental O= Linux kernel Kbuild preparation only.
# Refuse any writes to kernel source; output stays inside this project.
set -euo pipefail
T=/mnt/d/study/LicheeRV/test
ROOT="$T/clock36_safe_20261019"
SRC="$ROOT/kernel_src"
OUT="$ROOT/kernel_out"
P="$T/kernel36/host_tools/sysroot"
CROSS=/mnt/d/study/LicheeRV/speed-fry/workspace/LicheeRV-Nano-Build/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl-
test -r "$SRC/Makefile"
test -f "$ROOT/board.config"
test -x "${CROSS}gcc"
mkdir -p "$OUT"
if [ ! -e "$OUT/.config" ]; then
 cp "$ROOT/board.config" "$OUT/.config"
fi
export PATH="$ROOT/host_packages/sysroot/usr/bin:$P/usr/bin:/usr/bin:/bin"
export M4="$ROOT/host_packages/sysroot/usr/bin/m4"
export BISON_PKGDATADIR="$ROOT/host_packages/sysroot/usr/share/bison"
export GCC_EXEC_PREFIX="$P/usr/lib/gcc/x86_64-linux-gnu/11/"
export CPATH="$P/usr/lib/gcc/x86_64-linux-gnu/11/include:$P/usr/include:$P/usr/include/x86_64-linux-gnu"
export LIBRARY_PATH="$P/usr/lib/x86_64-linux-gnu:$P/usr/lib/gcc/x86_64-linux-gnu/11"
export LD_LIBRARY_PATH="$ROOT/host_packages/sysroot/usr/lib/x86_64-linux-gnu:$P/usr/lib/x86_64-linux-gnu:$P/usr/lib/gcc/x86_64-linux-gnu/11"
export HOSTCC="bash $ROOT/hostcc.sh"
export HOSTCXX="bash $ROOT/hostcc.sh"
echo "Host toolchain: $P, source $SRC, O=$OUT"
"$P/usr/bin/make" -C "$SRC" O="$OUT" ARCH=riscv CROSS_COMPILE="$CROSS" HOSTCC="$HOSTCC" HOSTCXX="$HOSTCXX" V=0 modules_prepare
