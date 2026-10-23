#!/usr/bin/env bash
set -euo pipefail
# All generated outputs and temporary compiler files MUST remain beneath test/.
TEST="/mnt/d/study/LicheeRV/test"
SRC="/mnt/d/study/LicheeRV/speed-fry"
CAMERA="$SRC/workspace/camera"
SDK="$SRC/workspace/LicheeRV-Nano-Build"
OUT="$TEST/build"
mkdir -p "$OUT/tmp"
export TMPDIR="$OUT/tmp"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
test -x "$TC-gcc" || { echo "RISC-V toolchain unavailable"; exit 1; }
cd "$CAMERA"
INC=(-I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" -I"$SDK/osdrv/interdrv/v2/include/common/uapi" -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -Isrc/common -I"$TEST/sensor_experiment")
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
if [ "${FAST:-0}" != 1 ]; then
  "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c experiments/over100/src/common_factory1080/sample_common_sensor.c -o "$OUT/common_sensor.o"
  "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$TEST/sensor_experiment/gc4653_cmos.c" -o "$OUT/gc4653_cmos.o"
  "$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$TEST/camera_preview_hts.cpp" -o "$OUT/main.o"
fi
if [ "${REBUILD_CMOS:-0}" = 1 ]; then
  "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$TEST/sensor_experiment/gc4653_cmos.c" -o "$OUT/gc4653_cmos.o"
fi
"$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$TEST/sensor_experiment/gc4653_sensor_ctl.c" -o "$OUT/gc4653_sensor_ctl.o"
OBJ=()
for f in "$SRC/build-preview-hd/"*.o; do
  case "$(basename "$f")" in main.o|common_sensor.o|gc4653_cmos.o|gc4653_sensor_ctl.o) ;; *) OBJ+=("$f");; esac
done
"$TC-g++" -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections -Wl,-rpath,'$ORIGIN/../lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs -o "$TEST/camera_preview_hts" "${OBJ[@]}" "$OUT/"*.o -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc
file "$TEST/camera_preview_hts"
sha256sum "$TEST/camera_preview_hts"
