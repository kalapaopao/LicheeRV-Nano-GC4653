#!/usr/bin/env bash
# Portable host compiler: all support files confined to D:/study/LicheeRV/test.
set -e
P=/mnt/d/study/LicheeRV/test/kernel36/host_tools/sysroot
export GCC_EXEC_PREFIX="$P/usr/lib/gcc/x86_64-linux-gnu/11/"
export CPATH="$P/usr/lib/gcc/x86_64-linux-gnu/11/include:$P/usr/include:$P/usr/include/x86_64-linux-gnu"
export LIBRARY_PATH="$P/usr/lib/x86_64-linux-gnu:$P/usr/lib/gcc/x86_64-linux-gnu/11"
export LD_LIBRARY_PATH="$P/usr/lib/x86_64-linux-gnu:$P/usr/lib/gcc/x86_64-linux-gnu/11"
exec "$P/usr/bin/gcc-11" -Wl,--sysroot="$P" "$@"
