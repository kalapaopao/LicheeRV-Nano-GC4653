#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "$ROOT/../../../speed-fry/workspace/camera" && pwd)"
SDK="$(cd "$BASE/../LicheeRV-Nano-Build" && pwd)"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
INC=(-I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" -I"$SDK/osdrv/interdrv/v2/include/common/uapi" -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -I"$ROOT/common")
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$ROOT/camera_bench_empty_1080.cpp" -o "$ROOT/build/camera_bench_empty_1080.o"
(
  cd "$BASE"
  "$TC-g++" -Wl,--dynamic-list="$ROOT/exports.list" -Wl,--gc-sections \
    -Wl,-rpath,'$ORIGIN/../lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' \
    -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs \
    -o "$ROOT/camera_bench_empty_1080" \
    "$ROOT/build/camera_bench_empty_1080.o" \
    "$ROOT/build/common_sys.o" "$ROOT/build/common_vi.o" "$ROOT/build/common_isp.o" \
    "$ROOT/build/common_sensor.o" "$ROOT/build/common_bin.o" "$ROOT/build/common_platform.o" \
    "$ROOT/build/common_vpss.o" "$ROOT/build/gc4653_cmos.o" "$ROOT/build/gc4653_sensor_ctl.o" \
    "$ROOT/build/ini.o" "$ROOT/build/atomic.o" \
    -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo \
    -lae -lawb -laf -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc
)
file "$ROOT/camera_bench_empty_1080"
