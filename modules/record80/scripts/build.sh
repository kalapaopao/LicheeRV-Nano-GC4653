#!/usr/bin/env bash
# Independent GC4653 80FPS capture / 40FPS AVI recording module build.
# All generated files remain under D:/study/LicheeRV (or this cloned checkout).
# Requires Sipeed SDK/toolchain in speed-fry/workspace (not shipped to GitHub).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SPEED="$ROOT/speed-fry"
EXP="$ROOT/modules/record80"
CAMERA="${CAMERA_ROOT:-$SPEED/workspace/camera}"
SDK="${SDK_ROOT:-$SPEED/workspace/LicheeRV-Nano-Build}"
TC="$SDK/host-tools/gcc/riscv64-linux-musl-x86_64/bin/riscv64-unknown-linux-musl"
OBJ="$EXP/build"
OUTPUT="${1:-$EXP/bin/camera_36record}"

die(){ printf 'BUILD_ERROR: %s\n' "$*" >&2; exit 1; }
[[ -x "$TC-gcc" && -x "$TC-g++" ]] || die "RISC-V musl compiler not installed: $TC-{gcc,g++}"
[[ -d "$CAMERA/src/common" && -d "$CAMERA/src/sensor" ]] || die "camera sources are missing: $CAMERA"
[[ -d "$CAMERA/sdk/board-libs" ]] || die "board linkage libraries missing: $CAMERA/sdk/board-libs"
[[ -f "$CAMERA/src/exports.list" ]] || die "exports list missing"
[[ -f "$SDK/middleware/v2/3rdparty/inih/ini.c" ]] || die "inih sources missing from SDK"
[[ "$OUTPUT" = "$EXP/"* ]] || die "Output must stay within modules/record80"
mkdir -p "$OBJ" "$(dirname "$OUTPUT")"

INC=(
 -I"$EXP/include"
 -I"$SDK/middleware/v2/include"
 -I"$SDK/middleware/v2/include/isp/sg200x"
 -I"$SDK/osdrv/interdrv/v2/include/common/uapi"
 -I"$SDK/osdrv/interdrv/v2/include/chip/mars/uapi"
 -I"$CAMERA/src/common"
 -I"$CAMERA/src/sensor"
)
FLAGS=(
 -O2 -fPIC -ffunction-sections -fdata-sections
 -DARCH_CV181X -DARCH_SG200X -DUSE_USER_SEN_DRIVER=1
 -DSENSOR_GCORE_GC4653
 -DSENSOR0_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT
 -DSENSOR1_TYPE=GCORE_GC4653_MIPI_4M_30FPS_10BIT
)

echo "BUILD_TARGET=GC4653 CAM1 divider-33 80FPS"
echo "BUILD_ROOT=$ROOT"
echo "BUILD_OUTPUT=$OUTPUT"
echo "BUILD_TOOLCHAIN=$TC"

# Build the common CVITEK and sensor objects from the SDK/reference source,
# rather than relying on stale speed-fry/build-preview-hd/*.o.
objects=()
for n in sys vi isp sensor bin platform vpss; do
  src="$CAMERA/src/common/sample_common_$n.c"
  [[ -f "$src" ]] || die "Missing common source: $src"
  dest="$OBJ/common_$n.o"
  "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$src" -o "$dest"
  objects+=("$dest")
done
"$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$SDK/middleware/v2/3rdparty/inih/ini.c" -o "$OBJ/ini.o"
objects+=("$OBJ/ini.o")
"$TC-gcc" "${FLAGS[@]}" -c "$CAMERA/src/atomic_compat.c" -o "$OBJ/atomic.o"
objects+=("$OBJ/atomic.o")
for src in "$CAMERA"/src/sensor/*.c; do
  [[ -f "$src" ]] || die "No GC4653 sensor sources in $CAMERA/src/sensor"
  dest="$OBJ/$(basename "$src" .c).o"
  "$TC-gcc" "${FLAGS[@]}" "${INC[@]}" -c "$src" -o "$dest"
  objects+=("$dest")
done
"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" \
  -c "$EXP/src/camera_36record.cpp" -o "$OBJ/main.o"
objects=("$OBJ/main.o" "${objects[@]}")

cd "$CAMERA"
"$TC-g++" \
 -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections \
 -Wl,-rpath,'$ORIGIN/../lib:/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd' \
 -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs -L"$EXP/sdk/board-libs" \
 -o "$OUTPUT" "${objects[@]}" \
 -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp \
 -lisp -lisp_algo -lae -lawb -laf -lcviruntime -lcvikernel -lm -lpthread -ldl -latomic \
 -static-libstdc++ -static-libgcc
file "$OUTPUT"
sha256sum "$OUTPUT"
echo "BUILD_RESULT=SUCCESS"
