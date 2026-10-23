#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "$ROOT/../../speed-fry/workspace/camera" && pwd)"
SDK="$(cd "$BASE/../LicheeRV-Nano-Build" && pwd)"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
mkdir -p "$ROOT/build"
INC=(-I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" -I"$SDK/osdrv/interdrv/v2/include/common/uapi" -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -I"$BASE/src/common" -I"$ROOT/sensor")
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
for n in sys vi isp sensor bin platform vpss; do
  "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$BASE/src/common/sample_common_$n.c" -o "$ROOT/build/common_$n.o"
done
"$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$SDK/middleware/v2/3rdparty/inih/ini.c" -o "$ROOT/build/ini.o"
"$TC-gcc" "${FLAGS[@]}" -c "$ROOT/atomic_compat.c" -o "$ROOT/build/atomic.o"
for f in "$ROOT/sensor/"*.c; do
  "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -Werror=implicit-function-declaration -c "$f" -o "$ROOT/build/$(basename "$f" .c).o"
done
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$ROOT/main.cpp" -o "$ROOT/build/main.o"
(cd "$BASE" && "$TC-g++" -Wl,--dynamic-list="$ROOT/exports.list" -Wl,--gc-sections -Wl,-rpath,'$ORIGIN/../lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs -o "$ROOT/minraw" "$ROOT"/build/*.o -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc)
file "$ROOT/minraw"
