#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
cd workspace/camera
SDK="$(cd ../LicheeRV-Nano-Build && pwd)"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
INC=(-I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" -I"$SDK/osdrv/interdrv/v2/include/common/uapi" -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -Isrc/common)
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
mkdir -p "$ROOT/build-preview80"
for n in sys vi isp sensor bin platform vpss; do
 "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c src/common/sample_common_$n.c -o "$ROOT/build-preview80/common_$n.o"
done
"$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$SDK/middleware/v2/3rdparty/inih/ini.c" -o "$ROOT/build-preview80/ini.o"
"$TC-gcc" "${FLAGS[@]}" -c src/atomic_compat.c -o "$ROOT/build-preview80/atomic.o"
for f in src/sensor/*.c; do
 "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -Isrc/sensor -c "$f" -o "$ROOT/build-preview80/$(basename "$f" .c).o"
done
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$ROOT/camera_preview80.cpp" -o "$ROOT/build-preview80/main.o"
"$TC-g++" -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections -Wl,-rpath,'$ORIGIN/../lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs -o "$ROOT/camera_preview80" "$ROOT"/build-preview80/*.o -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc
file "$ROOT/camera_preview80"
