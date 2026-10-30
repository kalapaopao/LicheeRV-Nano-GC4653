#!/usr/bin/env bash
# Isolated NPU experiment: never overwrite camera_36record or the stable 80 FPS binary.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Public Git excludes SDK and vendor binaries, kept in the external local lab.
LAB="${LICHEERV_LAB_ROOT:-$ROOT/../gc4653_36mhz_80fps_20261019}"
OPT="$ROOT/npu_optimization"
CAM="$LAB/workspace/camera"
SDK="$LAB/workspace/LicheeRV-Nano-Build"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
mkdir -p "$OPT/build" "$OPT/bin"
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
INC=(-I"$OPT/include" -I"$ROOT/modules/record80/include" -I"$LAB/npu_optimization/include" -I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" -I"$SDK/osdrv/interdrv/v2/include/common/uapi" -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -I"$CAM/src/common")
LIBS="$LAB/npu_optimization/sdk_libs"
test -f "$LIBS/libcviruntime.so" && test -f "$LIBS/libcvikernel.so" || { echo "NPU_LIBRARY_MISSING"; exit 3; }
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$OPT/capture_pipeline_opt/camera_capture_first_320.cpp" -o "$OPT/build/capture_first_320.o"
cd "$CAM"
"$TC-g++" -pthread -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections -Wl,-rpath,'$ORIGIN/../../lib:/usr/bin/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' -Wl,-rpath-link,"$LIBS" -Wl,-rpath-link,"$CAM/sdk/board-libs" -L"$CAM/sdk/board-libs" -L"$LIBS" -o "$OPT/bin/camera_capture_first_baked70_webfix" "$OPT/build/capture_first_320.o" "$CAM/build/atomic_compat.o" "$CAM"/build/common_*.o "$CAM/build/ini.o" "$CAM/build/sensor_gc4653_cmos.o" "$CAM/build/sensor_gc4653_sensor_ctl.o" -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf -lcviruntime -lcvikernel -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc
file "$OPT/bin/camera_capture_first_baked70_webfix"
sha256sum "$OPT/bin/camera_capture_first_baked70_webfix"
echo BUILD_CAPTURE_FIRST_DONE
