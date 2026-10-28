#!/bin/sh
# Isolated, bounded color A/B test. Never overwrite the production module.
set -eu
ROOT=/code/camera/diagnostics/darkscene_20261024
MODE=${1-}
WB=${2-native}
case "$MODE:$WB" in 60:native|80:native|60:unity|60:blc256|80:blc256|60:reference|60:reference_blc256|80:reference|80:reference_blc256) :;; *) echo BAD_TEST_MODE; exit 2;; esac
REG=0x030028c4
ORIG=0x00200001
TARGET=0x00210001
LOCK=/code/camera/run/lock
BIN=$ROOT/camera_colorprobe
REPORT=$ROOT/results/${MODE}_${WB}_$(date +%s)_$$
CAM_PID=''; GUARD_PID=''; OWNED=0; STARTED=0
reg() { devmem "$REG" 32 | tr A-F a-f; }
err() { awk '/^[ ]*0[ ]+[0-9]+[ ]+[0-9]+[ ]+[0-9]+/{print $2,$3,$4,$5,$6;exit}' /proc/mipi-rx; }
cleanup() {
  code=$?
  trap - 0 1 2 15
  if [ -n "$CAM_PID" ]; then
    kill -TERM "$CAM_PID" 2>/dev/null || :
    n=0
    while kill -0 "$CAM_PID" 2>/dev/null && [ "$n" -lt 12 ]; do sleep 1; n=$((n+1)); done
    if kill -0 "$CAM_PID" 2>/dev/null; then echo CAMERA_STILL_ALIVE_LOCK_RETAINED; exit 10; fi
    wait "$CAM_PID" 2>/dev/null || :
  fi
  if [ "$STARTED" = 1 ]; then
    current=$(reg)
    case "$current" in
      0x00200001|0x00210001|0x002c0001)
        "$BIN" --restore-clock || { echo CCF_RESTORE_FAILED; code=11; }
        # clk_set_rate can be a no-op when CCF already caches 37.125MHz.
        if [ "$(reg)" = "$TARGET" ]; then devmem "$REG" 32 "$ORIG" || code=11; fi
        if [ "$(reg)" != "$ORIG" ] || [ "$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)" != 37125000 ]; then echo CLOCK_RESTORE_VERIFY_FAILED; code=11; fi
        ;;
      *) echo "UNEXPECTED_CLOCK=$current refuse_to_clobber"; code=12;;
    esac
  fi
  if [ -n "$GUARD_PID" ]; then kill -TERM "$GUARD_PID" 2>/dev/null || :; fi
  echo "FINAL_MMIO=$(reg) FINAL_CCF=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate) FINAL_MIPI=$(err) FINAL_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)"
  if [ "$OWNED" = 1 ]; then rmdir "$LOCK" || code=13; fi
  echo "PROBE_DONE code=$code REPORT=$REPORT"
  exit "$code"
}
[ "$(uname -r)" = 5.10.4-tag- ]
[ ! -e "$LOCK" ] || { echo CAMERA_LOCK_BUSY; exit 2; }
if pidof camera_colorprobe camera_36record camera_http80 camera_normal60 camera_normal60_async camera_preview_hd camera_preview80 camera_preview_factory camera_factory_timing camera_bench camera_stream sensor_test sample_vio >/dev/null 2>&1; then echo CAMERA_PROCESS_BUSY; exit 2; fi
[ "$(reg)" = "$ORIG" ] || { echo BAD_INITIAL_CLOCK; exit 2; }
TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
echo "INIT_TEMP=$TEMP INIT_MMIO=$(reg) INIT_CCF=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate) INIT_MIPI=$(err)"
[ "$TEMP" -lt 70000 ]
[ -x "$BIN" ]
mkdir -p "$REPORT"
cp /code/camera/modules/record80/config/record80.yaml "$REPORT/production_config.yaml"
mkdir "$LOCK"
OWNED=1
trap cleanup 0
trap 'exit 130' 1 2 15
cd /code/camera
export LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd
export PREVIEW_DIAG_LINEAR=1 PREVIEW_DIAG_RAW=1
unset PREVIEW_DIAG_PUBFPS PREVIEW_DIAG_NOTNR PREVIEW_DIAG_NODPC COLORPROBE_WB_UNITY COLORPROBE_BLC_256 DARKCAP_WB_REFERENCE
export RECORD80_JPEG_QUALITY=85 RECORD80_EXPOSURE_MODE=manual
export RECORD80_MANUAL_EXP_US=5000 RECORD80_MANUAL_AGAIN=1024 RECORD80_MANUAL_DGAIN=1024 RECORD80_MANUAL_ISPGAIN=1024
export RECORD80_AUTO_EXP_MAX_US=0 RECORD80_AUTO_AGAIN_MAX=0 RECORD80_AUTO_DGAIN_MAX=0 RECORD80_AUTO_ISPGAIN_MAX=0
[ "$WB" != unity ] || export COLORPROBE_WB_UNITY=1
[ "$WB" != blc256 ] || export COLORPROBE_BLC_256=1
case "$WB" in reference|reference_blc256) export DARKCAP_WB_REFERENCE=1;; esac
[ "$WB" != reference_blc256 ] || export COLORPROBE_BLC_256=1
printf 'mode=%s\nwb=%s\nmanual_exp_us=5000\ngains=1024,1024,1024\ninternal_capture_limit_sec=24\n' "$MODE" "$WB" > "$REPORT/test_parameters.txt"
STARTED=1
"$BIN" 10.133.124.1 "$REPORT" "$MODE" > "$REPORT/capture.log" 2>&1 &
CAM_PID=$!
# Internal 24s limit + independent bounded safety watcher.
(
  sleep 40
  kill -TERM "$CAM_PID" 2>/dev/null || :
  sleep 3
  if ! kill -0 "$CAM_PID" 2>/dev/null; then
    case "$(reg)" in
      0x00200001|0x00210001|0x002c0001)
        "$BIN" --restore-clock > "$REPORT/hardware_guard.log" 2>&1
        if [ "$(reg)" = "$TARGET" ]; then devmem "$REG" 32 "$ORIG"; fi
        ;;
    esac
  fi
) &
GUARD_PID=$!
echo "PROBE_STARTED mode=$MODE wb=$WB pid=$CAM_PID report=$REPORT"
sleep 7
kill -0 "$CAM_PID" 2>/dev/null || { echo EARLY_EXIT; exit 3; }
[ -s "$REPORT/sensor-bayer-before.bin" ] || { echo RAW_MISSING; exit 3; }
CCF=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)
if [ "$MODE" = 60 ]; then
  [ "$CCF" = 27000000 ] && [ "$(reg)" = 0x002c0001 ] || { echo NATIVE60_CLOCK_MISMATCH; exit 4; }
else
  [ "$CCF" = 37125000 ] && [ "$(reg)" = "$ORIG" ] || { echo MODE80_CLOCK_MISMATCH; exit 4; }
  devmem "$REG" 32 "$TARGET"
fi
BASE=$(err)
echo "READY mode=$MODE reg=$(reg) ccf=$CCF mipi=$BASE"
n=0
while kill -0 "$CAM_PID" 2>/dev/null && [ "$n" -lt 16 ]; do
  sleep 2; n=$((n+1))
  TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
  echo "HEALTH n=$n temp=$TEMP reg=$(reg) mipi=$(err)"
  [ "$TEMP" -lt 74500 ] || { echo TEMP_LIMIT; exit 5; }
  [ "$(err)" = "$BASE" ] || { echo NEW_MIPI_ERROR; exit 6; }
  if [ "$MODE" = 60 ]; then EXPECTED=0x002c0001; else EXPECTED=$TARGET; fi
  [ "$(reg)" = "$EXPECTED" ] || { echo UNEXPECTED_CLOCK_CHANGE; exit 7; }
done
if kill -0 "$CAM_PID" 2>/dev/null; then echo CHILD_EXCEEDED_LIMIT; exit 8; fi
if wait "$CAM_PID"; then echo CAMERA_EXIT=0; else echo CAMERA_EXIT_NONZERO; exit 9; fi
CAM_PID=''
test -s "$REPORT/after-hw.jpg"
echo "TEST_COMPLETE mode=$MODE wb=$WB"
