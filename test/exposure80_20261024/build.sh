#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXP="$ROOT/test/exposure80_20261024"
CAMERA="$ROOT/speed-fry/workspace/camera"
SDK="$ROOT/speed-fry/workspace/LicheeRV-Nano-Build"
MODULE="$ROOT/modules/record80"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
mkdir -p "$EXP/build"
"$TC-g++" -std=c++11 -O2 -fPIC -ffunction-sections -fdata-sections \
  -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1 \
  -DSENSOR_GCORE_GC4653 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT \
  -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT \
  -I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x" \
  -I"$SDK/osdrv/interdrv/v2/include/common/uapi" \
  -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" \
  -I"$CAMERA/src/common" -I"$CAMERA/src/sensor" -I"$MODULE/src" \
  -c "$EXP/camera_36record_exposure.cpp" -o "$EXP/build/main.o"
cd "$CAMERA"
"$TC-g++" -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections \
  -Wl,-rpath,'$ORIGIN/../lib:/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' \
  -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs \
  -o "$EXP/camera_36record" "$EXP/build/main.o" \
  "$MODULE"/build/{atomic,common_*,gc4653_cmos,gc4653_sensor_ctl,ini}.o \
  -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp \
  -lisp -lisp_algo -lae -lawb -laf -lm -lpthread -ldl -latomic \
  -static-libstdc++ -static-libgcc
file "$EXP/camera_36record"
sha256sum "$EXP/camera_36record"
