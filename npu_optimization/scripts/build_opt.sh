#!/usr/bin/env bash
# Isolated NPU experiment: never overwrite camera_36record or the stable 80 FPS binary.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPT="$ROOT/npu_optimization"
CAM="$ROOT/workspace/camera"
SDK="$ROOT/workspace/LicheeRV-Nano-Build"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
mkdir -p "$OPT/build" "$OPT/bin"
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
INC=(-I"$OPT/include" -I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" -I"$SDK/osdrv/interdrv/v2/include/common/uapi" -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -I"$CAM/src/common")
test -f "$OPT/sdk_libs/libcviruntime.so" && test -f "$OPT/sdk_libs/libcvikernel.so" || { echo "NPU_LIBRARY_MISSING"; exit 3; }
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$OPT/src/camera_36record_opt.cpp" -o "$OPT/build/main.o"
cd "$CAM"
"$TC-g++" -pthread -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections -Wl,-rpath,'$ORIGIN/../../lib:/usr/bin/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' -Wl,-rpath-link,"$OPT/sdk_libs" -Wl,-rpath-link,"$CAM/sdk/board-libs" -L"$CAM/sdk/board-libs" -L"$OPT/sdk_libs" -o "$OPT/bin/camera_36record_opt" "$OPT/build/main.o" "$CAM/build/atomic_compat.o" "$CAM"/build/common_*.o "$CAM/build/ini.o" "$CAM/build/sensor_gc4653_cmos.o" "$CAM/build/sensor_gc4653_sensor_ctl.o" -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf -lcviruntime -lcvikernel -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc
file "$OPT/bin/camera_36record_opt"
sha256sum "$OPT/bin/camera_36record_opt"
echo BUILD_OPT_DONE
