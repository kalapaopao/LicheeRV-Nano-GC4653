#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/d/study/LicheeRV
SPEED="$ROOT/speed-fry"
EXP="$ROOT/test/clock36_live_20261023"
SDK="$SPEED/workspace/LicheeRV-Nano-Build"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
INC=(-I"$SDK/middleware/v2/include" -I"$SDK/middleware/v2/include/isp/sg200x"
 -I"$SDK/osdrv/interdrv/v2/include/common/uapi"
 -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi" -I"$SPEED/workspace/camera/src/common")
FLAGS=(-O2 -fPIC -ffunction-sections -fdata-sections
 -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1
 -DSENSOR_GCORE_GC4653
 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT
 -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT)
mkdir -p "$EXP/build"
test -x "$TC-g++"
# Reuse preserved build objects, compile only a new experiment-specific main.
test -f "$SPEED/build-preview-hd/common_vi.o"
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c "$EXP/camera_36probe.cpp" -o "$EXP/build/main.o"
objects=("$EXP/build/main.o")
for f in "$SPEED"/build-preview-hd/*.o; do
  if [[ "${f##*/}" != main.o ]];then objects+=("$f"); fi
done
cd "$SPEED/workspace/camera"
"$TC-g++" -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections \
 -Wl,-rpath,'$ORIGIN/../lib:/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' \
 -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs \
 -o "$EXP/camera_36probe" "${objects[@]}" \
 -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf \
 -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc
file "$EXP/camera_36probe"
