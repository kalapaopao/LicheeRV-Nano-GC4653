#!/bin/sh
# LicheeRV SG2002 GC4653 supervised 36MHz divider-33 720p live preview.
# RESEARCH ONLY. Camera clock is temporarily changed via CAM1 MMIO divider.
# Max session length 300s; 74.5C SoC guard; detects capture and MIPI faults.
set -eu
REG=0x030028c4
ROOT=/tmp/clock36_record_20261024
REPORT=$ROOT/record_report
LOCK=/code/camera/run/lock
ORIG=0x00200001
TARGET=0x00210001
CAM_PID=''
GUARD_PID=''
LOCK_OWNED=0
CHANGED=0
STOP_REASON=''
: ${MAX_RUN_SEC:=300}
case $MAX_RUN_SEC in *[!0-9]*|'') echo BAD_MAX_RUN_SEC; exit 2;; esac
test "$MAX_RUN_SEC" -ge 20 && test "$MAX_RUN_SEC" -le 300
now() { date +%s; }
clockreg() { devmem "$REG" 32; }
geterrors() { awk '/^[ ]*0[ ]+[0-9]+[ ]+[0-9]+[ ]+[0-9]+/{print $2,$3,$4,$5,$6;exit}' /proc/mipi-rx; }
on_exit() {
  code=$?
  trap - 0 1 2 15
  echo "CLEANUP_ENTER code=$code reason=${STOP_REASON:-unknown} time=$(now)"
  if [ -n "$CAM_PID" ]; then
    kill -TERM "$CAM_PID" 2>/dev/null || :
    t=0
    while kill -0 "$CAM_PID" 2>/dev/null && [ "$t" -lt 12 ]; do
      sleep 1
      t=$((t+1))
    done
    if kill -0 "$CAM_PID" 2>/dev/null; then
      echo "CAMERA_DID_NOT_EXIT_WITHIN_12S=$CAM_PID"
    else
      wait "$CAM_PID" 2>/dev/null || :
    fi
  fi
  if [ "$CHANGED" = 1 ]; then
    val=$(clockreg || echo ERROR)
    if [ "$val" = "$TARGET" ]; then
      echo "RESTORE_MMIO=$ORIG"
      devmem "$REG" 32 "$ORIG" || echo "RESTORE_FAILED"
    elif [ "$val" != "$ORIG" ]; then
      echo "UNEXPECTED_CAM1_REGISTER=$val refuse_to_clobber"
    fi
  fi
  if [ -n "$GUARD_PID" ]; then kill -TERM "$GUARD_PID" 2>/dev/null || :; fi
  echo "FINAL_MMIO=$(clockreg)"
  echo "FINAL_CCF=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
  echo "FINAL_MIPI=$(geterrors)"
  echo "FINAL_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)"
  if [ "$LOCK_OWNED" = 1 ]; then
    if kill -0 "$CAM_PID" 2>/dev/null; then
      echo "LOCK_RETAINED_CAMERA_STILL_RUNNING"
    else
      rmdir "$LOCK" || echo "LOCK_RELEASE_FAILED"
    fi
  fi
  echo "CLEANUP_DONE"
  exit "$code"
}
trap on_exit 0
trap 'STOP_REASON=signal;exit 130' 1 2 15
test "$(uname -r)" = '5.10.4-tag-'
test -x "$ROOT/camera_36record"
test ! -e "$LOCK" || { echo "CAMERA_LOCK_BUSY"; exit 2; }
if pidof camera_preview_hd camera_preview80 camera_preview_factory camera_factory_timing camera_36record camera_36probe camera_bench camera_http80 camera_normal60 camera_stream minraw36 minraw1080_27or36 sensor_test sample_vio >/dev/null 2>&1; then
  echo "CAMERA_PROCESS_BUSY"
  exit 2
fi
INIT_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
echo "INIT_TEMP_MC=$INIT_TEMP"
test "$INIT_TEMP" -lt 70000
test "$(clockreg)" = "$ORIG"
PARENT=$(cat /sys/kernel/debug/clk/clk_cam0pll/clk_rate)
test "$PARENT" -gt 1187000000 && test "$PARENT" -lt 1189000000
echo "PARENT_HZ=$PARENT"
mkdir -p "$REPORT"
mkdir -p /code/camera/recordings
mkdir "$LOCK"
LOCK_OWNED=1
cd /code/camera
export LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd
export PREVIEW_DIAG_LINEAR=1
export PREVIEW_DIAG_RAW=1
"$ROOT/camera_36record" 10.133.124.1 "$REPORT" 80 >"$REPORT/capture.log" 2>&1 &
CAM_PID=$!
echo "$CAM_PID" >"$ROOT/record_cam.pid"
echo "CAMERA_PID=$CAM_PID"
sleep 7
kill -0 "$CAM_PID" 2>/dev/null || { echo "CAMERA_EARLY_EXIT"; exit 3; }
test -s "$REPORT/sensor-bayer-before.bin" || { echo "BASELINE_RAW_MISSING"; exit 3; }
ERR_BASE=$(geterrors)
echo "MIPI_BEFORE_SWITCH=$ERR_BASE"
# Hardware watch guard survives a lost supervisor, for bounded test.
(
  sleep 335
  current=$(clockreg || echo ERROR)
  if [ "$current" = "$TARGET" ]; then
    devmem "$REG" 32 "$ORIG" >"$ROOT/record_hardware_guard.log" 2>&1
  fi
  kill -TERM "$CAM_PID" 2>/dev/null || :
) &
GUARD_PID=$!
echo "MMIO_WRITE_TARGET=$TARGET"
CHANGED=1
devmem "$REG" 32 "$TARGET"
test "$(clockreg)" = "$TARGET" || { echo "MMIO_TARGET_MISMATCH"; exit 5; }
echo "LIVE_READY http://10.133.124.1:8081/ approx36MHz; time=$(now)"
echo "CLOCK_CCF_STALE=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
echo "LIFETIME_MAX=${MAX_RUN_SEC}s"
if [ "${RECORD_TEST_AUTOSTART:-0}" = 1 ]; then
  echo RECORD_START_REQUEST
  curl -fsS --max-time 5 -X POST http://10.133.124.1:8082/start || echo RECORD_START_HTTP_FAILED
fi
START=$(now)
CYCLES=0
while [ $(( $(now) - START )) -lt "$MAX_RUN_SEC" ]; do
  sleep 3
  CYCLES=$((CYCLES+1))
  if ! kill -0 "$CAM_PID" 2>/dev/null; then STOP_REASON=process_exited;echo "FATAL_PROCESS_EXIT";exit 6;fi
  TMP=$(cat /sys/class/thermal/thermal_zone0/temp)
  REGNOW=$(clockreg)
  ERRNOW=$(geterrors)
  echo "HEALTH t=$(( $(now) - START ))s temp_mc=$TMP reg=$REGNOW mipi=$ERRNOW"
  if [ "$TMP" -ge 74500 ]; then STOP_REASON=overtemperature;echo "FATAL_TEMP_LIMIT=$TMP";exit 7;fi
  if [ "$REGNOW" != "$TARGET" ]; then STOP_REASON=register_changed;echo "FATAL_CLOCK_CHANGED=$REGNOW";exit 8;fi
  if [ "$ERRNOW" != "$ERR_BASE" ]; then STOP_REASON=mipi_error_change;echo "FATAL_NEW_MIPI_ERROR before=$ERR_BASE after=$ERRNOW";exit 9;fi
  if [ "$CYCLES" -ge 10 ]; then
    CYCLES=0
    tail -7 "$REPORT/capture.log" | grep -E 'capture_frames=|CLOCK36_WINDOW' || :
  fi
done
STOP_REASON=timer_300s
echo "MAX_TIME_REACHED"
