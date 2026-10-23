#!/bin/sh
# GC4653 80-mode, controlled 37.125 -> 36 MHz CAM1 divider experiment.
# TEMPORARY register write only: original state is restored, old ko/binaries untouched.
set -eu
BASE=/tmp/clock36_live_20261023
REPORT="$BASE/report_long"
REG=0x030028c4
LOCK=/code/camera/run/lock
ORIGINAL=''
LOCK_OWNED=0
CHANGED=0
CAMERA_PID=''
GUARD_PID=''
cleanup() {
  rc=$?
  trap - 0 1 2 15
  if [ "$CHANGED" = 1 ]; then
    echo "EMERGENCY_RESTORE_DIVIDER=$ORIGINAL"
    devmem "$REG" 32 "$ORIGINAL" || echo RESTORE_WRITE_FAILED
  fi
  if [ -n "$GUARD_PID" ]; then kill -TERM "$GUARD_PID" 2>/dev/null || :; fi
  if [ -n "$CAMERA_PID" ]; then
    kill -TERM "$CAMERA_PID" 2>/dev/null || :
    wait "$CAMERA_PID" 2>/dev/null || :
  fi
  if [ "$LOCK_OWNED" = 1 ]; then
    rmdir "$LOCK" || echo LOCK_RELEASE_FAILED
  fi
  echo "FINISH_EXIT=$rc"
  echo "FINISH_CAM1_REGISTER=$(devmem "$REG" 32)"
  echo "FINISH_CAM1_CLOCK=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
  echo "FINISH_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)"
  exit "$rc"
}
trap cleanup 0 1 2 15
test "$(uname -r)" = '5.10.4-tag-'
test -x "$BASE/camera_36long"
test ! -e "$LOCK"
if pidof camera_preview_hd camera_preview80 camera_preview_factory camera_factory_timing camera_36probe camera_36long camera_bench camera_http80 camera_normal60 sensor_test sample_vio >/dev/null 2>&1; then
  echo BUSY_REFUSING
  exit 4
fi
TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
echo "INITIAL_TEMP=$TEMP"
test "$TEMP" -lt 75000
ORIGINAL=$(devmem "$REG" 32)
echo "INITIAL_DIV_REG=$ORIGINAL"
test "$ORIGINAL" = '0x00200001'
PARENT=$(cat /sys/kernel/debug/clk/clk_cam0pll/clk_rate)
test "$PARENT" -gt 1187000000
test "$PARENT" -lt 1189000000
echo "PARENT_HZ=$PARENT"
mkdir -p "$REPORT"
mkdir "$LOCK"
LOCK_OWNED=1
echo "MIPI_BEFORE=$(awk '/^[ ]*0[ ]+[0-9]+[ ]+[0-9]+/{print;exit}' /proc/mipi-rx)"
cd /code/camera
export LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd
export PREVIEW_DIAG_RAW=1
export PREVIEW_DIAG_LINEAR=1
"$BASE/camera_36long" 10.133.124.1 "$REPORT" 80 > "$REPORT/run.log" 2>&1 &
CAMERA_PID=$!
echo "CAMERA_PID=$CAMERA_PID"
sleep 7
kill -0 "$CAMERA_PID"
test -s "$REPORT/sensor-bayer-before.bin"
echo "BASELINE_RAW_BYTES=$(wc -c < "$REPORT/sensor-bayer-before.bin")"
test -s "$REPORT/first-hw.jpg"
cp "$REPORT/first-hw.jpg" "$REPORT/before.jpg"
test -s "$REPORT/before.jpg"
echo "BASELINE_JPEG_BYTES=$(wc -c < "$REPORT/before.jpg")"
echo "BASELINE_MIPI=$(awk '/^[ ]*0[ ]+[0-9]+[ ]+[0-9]+/{print;exit}' /proc/mipi-rx)"
test "$(devmem "$REG" 32)" = "$ORIGINAL"
# This guard rolls the hardware divider back even if the caller disconnects.
( sleep 90; devmem "$REG" 32 "$ORIGINAL" > "$BASE/rollback_guard.log" 2>&1 ) &
GUARD_PID=$!
echo "CAM1_CHANGE_TO_DIV33"
CHANGED=1
devmem "$REG" 32 0x00210001
echo "CAM1_TEST_REG=$(devmem "$REG" 32)"
n=0
while [ "$n" -lt 28 ]; do
  sleep 2
  TEMP_NOW=$(cat /sys/class/thermal/thermal_zone0/temp)
  if [ "$TEMP_NOW" -ge 75000 ]; then echo "OVERTEMP_ABORT=$TEMP_NOW"; exit 7; fi
  n=$((n+1))
done
echo "CAM1_TEST_REG_END=$(devmem "$REG" 32)"
echo "CAM1_SOFTWARE_CLOCK=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
echo "TEST_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)"
echo "TEST_MIPI=$(awk '/^[ ]*0[ ]+[0-9]+[ ]+[0-9]+/{print;exit}' /proc/mipi-rx)"
test -s "$REPORT/sensor-bayer-after.bin"
echo "TEST_RAW_BYTES=$(wc -c < "$REPORT/sensor-bayer-after.bin")"
test -s "$REPORT/after-hw.jpg"
cp "$REPORT/after-hw.jpg" "$REPORT/after.jpg"
test -s "$REPORT/after.jpg"
echo "TEST_JPEG_BYTES=$(wc -c < "$REPORT/after.jpg")"
test -s "$REPORT/sensor-bayer-late.bin"
test -s "$REPORT/late-hw.jpg"
echo "LATE_RAW_BYTES=$(wc -c < "$REPORT/sensor-bayer-late.bin")"
echo "LATE_JPEG_BYTES=$(wc -c < "$REPORT/late-hw.jpg")"
echo "NORMAL_RESTORE=$ORIGINAL"
devmem "$REG" 32 "$ORIGINAL"
test "$(devmem "$REG" 32)" = "$ORIGINAL"
CHANGED=0
sleep 1
echo "MIPI_AFTER_RESTORE=$(awk '/^[ ]*0[ ]+[0-9]+[ ]+[0-9]+/{print;exit}' /proc/mipi-rx)"
echo "WINDOW_FPS_LOG:"
grep 'CLOCK36_WINDOW' "$REPORT/run.log" || :
echo "EXPERIMENT_DONE"
