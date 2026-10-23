#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
mkdir -p "$ROOT/official-tests/build-factory"
OUT="$ROOT/official-tests/build-factory"
cd workspace/camera
SDK="$(cd ../LicheeRV-Nano-Build && pwd)"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
EXP=experiments/over100/src
INC=(-I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" -I"$SDK/osdrv/interdrv/v2/include/common/uapi" -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -Isrc/common)
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
if [ "${MAIN_ONLY:-0}" != 1 ]; then
"$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$EXP/common_factory1080/sample_common_sensor.c" -o "$OUT/common_sensor.o"
for f in "$EXP/sensor_factory1080/"*.c; do
 "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -I"$EXP/sensor_factory1080" -c "$f" -o "$OUT/$(basename "$f" .c).o"
done
fi
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$ROOT/official-tests/camera_preview_factory.cpp" -o "$OUT/main.o"
OBJ=()
for f in "$ROOT/build-preview-hd/"*.o; do
 case "$(basename "$f")" in main.o|common_sensor.o|gc4653_cmos.o|gc4653_sensor_ctl.o) ;; *) OBJ+=("$f");; esac
done
"$TC-g++" -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections -Wl,-rpath,'$ORIGIN/../lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs -o "$ROOT/official-tests/camera_preview_factory" "${OBJ[@]}" "$OUT/"*.o -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc
file "$ROOT/official-tests/camera_preview_factory"
