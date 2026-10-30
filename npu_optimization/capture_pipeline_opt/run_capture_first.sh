#!/bin/sh
# LicheeRV SG2002 GC4653 supervised 36MHz divider-33 720p live preview.
# RESEARCH ONLY. Camera clock is temporarily changed via CAM1 MMIO divider.
# Max session length 300s; 74.5C SoC guard; detects capture and MIPI faults.
set -eu
REG=0x030028c4
ROOT=/code/camera/modules/record80_opt
REPORT=$ROOT/record_report/session_$(date +%s)_$$
LOCK=/code/camera/run/lock
ORIG=0x00200001
TARGET=0x00210001
CAM_PID=''
GUARD_PID=''
LOCK_OWNED=0
CHANGED=0
STOP_REASON=''
CONFIG=${RECORD80_CONFIG:-$ROOT/config/record80_opt.yaml}
config_error() { echo "BAD_RECORD80_CONFIG: $*" >&2; exit 2; }
[ -r "$CONFIG" ] || config_error "cannot read $CONFIG"
SEEN=' '
CR=$(printf '\r')
while IFS= read -r line || [ -n "$line" ]; do
  line=${line%"$CR"}
  case "$line" in ''|\#*) continue;; *:*) :;; *) config_error "expected key: value";; esac
  key=${line%%:*}
  value=$(printf '%s' "${line#*:}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  case "$key" in ''|*[!a-z0-9_]*) config_error "invalid key $key";; esac
  if [ "$key" = npu_model_path ]; then
    case "$value" in
      /code/camera/modules/record80_opt/*.cvimodel) :;;
      *) config_error "model must be an absolute .cvimodel under record80_opt";;
    esac
    case "$value" in *..*|*[!a-zA-Z0-9_./-]*) config_error "unsafe model path";; esac
  else
    case "$value" in ''|*[!a-zA-Z0-9_.-]*) config_error "invalid value for $key";; esac
  fi
  case "$SEEN" in *" $key "*) config_error "duplicate key $key";; esac
  SEEN="$SEEN$key "
  case "$key" in
    schema_version) CFG_SCHEMA=$value;;
    camera_mode) CFG_MODE=$value;;
    max_run_sec) CFG_MAX_RUN=$value;;
    npu_model_path) CFG_MODEL=$value;;
    vpss_min_gap_ms) CFG_VPSS_GAP=$value;;
    auto_record) CFG_AUTO_RECORD=$value;;
    jpeg_quality) CFG_JPEG=$value;;
    exposure_mode) CFG_EXPOSURE_MODE=$value;;
    auto_exposure_max_us) CFG_AUTO_EXP_MAX=$value;;
    auto_analog_gain_max_x1024) CFG_AUTO_AGAIN_MAX=$value;;
    auto_digital_gain_max_x1024) CFG_AUTO_DGAIN_MAX=$value;;
    auto_isp_gain_max_x1024) CFG_AUTO_ISPGAIN_MAX=$value;;
    manual_exposure_us) CFG_MANUAL_EXP=$value;;
    manual_analog_gain_x1024) CFG_MANUAL_AGAIN=$value;;
    manual_digital_gain_x1024) CFG_MANUAL_DGAIN=$value;;
    manual_isp_gain_x1024) CFG_MANUAL_ISPGAIN=$value;;
    black_level_mode) CFG_BLC_MODE=$value;;
    black_level_r) CFG_BLC_R=$value;;
    black_level_gr) CFG_BLC_GR=$value;;
    black_level_gb) CFG_BLC_GB=$value;;
    black_level_b) CFG_BLC_B=$value;;
    *) config_error "unknown key $key";;
  esac
done < "$CONFIG"
[ "${CFG_SCHEMA-}" = 1 ] || config_error 'schema_version must be 1'
[ "${CFG_MODE-}" = 80 ] || config_error 'camera_mode must be 80'
num_range() {
  case "$2" in ''|*[!0-9]*) config_error "$1 must be an integer";; esac
  [ "$2" -ge "$3" ] && [ "$2" -le "$4" ] || config_error "$1 out of range [$3,$4]"
}
num_range max_run_sec "${CFG_MAX_RUN-}" 20 300
num_range vpss_min_gap_ms "${CFG_VPSS_GAP-}" 0 50
[ -n "${CFG_MODEL-}" ] || config_error 'npu_model_path is required'
[ -r "$CFG_MODEL" ] || config_error "NPU model missing/unreadable: $CFG_MODEL"
num_range jpeg_quality "${CFG_JPEG-}" 75 90
case "${CFG_AUTO_RECORD-}" in true|false) :;; *) config_error 'auto_record must be true or false';; esac
case "${CFG_EXPOSURE_MODE-}" in auto|manual) :;; *) config_error 'exposure_mode must be auto or manual';; esac
num_range auto_exposure_max_us "${CFG_AUTO_EXP_MAX-}" 0 10000
num_range auto_analog_gain_max_x1024 "${CFG_AUTO_AGAIN_MAX-}" 0 16384
num_range auto_digital_gain_max_x1024 "${CFG_AUTO_DGAIN_MAX-}" 0 4096
num_range auto_isp_gain_max_x1024 "${CFG_AUTO_ISPGAIN_MAX-}" 0 4096
for value in "${CFG_AUTO_AGAIN_MAX-}" "${CFG_AUTO_DGAIN_MAX-}" "${CFG_AUTO_ISPGAIN_MAX-}"; do
  [ "$value" -eq 0 ] || [ "$value" -ge 1024 ] || config_error 'auto gain max must be 0 or at least 1024'
done
num_range manual_exposure_us "${CFG_MANUAL_EXP-}" 100 10000
num_range manual_analog_gain_x1024 "${CFG_MANUAL_AGAIN-}" 1024 16384
num_range manual_digital_gain_x1024 "${CFG_MANUAL_DGAIN-}" 1024 4096
num_range manual_isp_gain_x1024 "${CFG_MANUAL_ISPGAIN-}" 1024 4096
# Optional in schema 1: old YAML files keep the original ISP/PQ settings.
CFG_BLC_MODE=${CFG_BLC_MODE:-default}
case "$CFG_BLC_MODE" in default|manual) :;; *) config_error 'black_level_mode must be default or manual';; esac
if [ "$CFG_BLC_MODE" = manual ]; then
  num_range black_level_r "${CFG_BLC_R-}" 0 4095
  num_range black_level_gr "${CFG_BLC_GR-}" 0 4095
  num_range black_level_gb "${CFG_BLC_GB-}" 0 4095
  num_range black_level_b "${CFG_BLC_B-}" 0 4095
fi
CFG_BLC_R=${CFG_BLC_R:-256}
CFG_BLC_GR=${CFG_BLC_GR:-256}
CFG_BLC_GB=${CFG_BLC_GB:-256}
CFG_BLC_B=${CFG_BLC_B:-256}
num_range black_level_r "$CFG_BLC_R" 0 4095
num_range black_level_gr "$CFG_BLC_GR" 0 4095
num_range black_level_gb "$CFG_BLC_GB" 0 4095
num_range black_level_b "$CFG_BLC_B" 0 4095
# All runtime settings come from experiment YAML.
MAX_RUN_SEC=$CFG_MAX_RUN
if [ "$CFG_AUTO_RECORD" = true ]; then RECORD_TEST_AUTOSTART=1; else RECORD_TEST_AUTOSTART=0; fi
CAPTURE_VPSS_MIN_GAP_MS=$CFG_VPSS_GAP
export FLY_RM_MODEL=$CFG_MODEL
export CAPTURE_VPSS_MIN_GAP_MS
num_range MAX_RUN_SEC "$MAX_RUN_SEC" 20 300
case "$RECORD_TEST_AUTOSTART" in 0|1) :;; *) config_error 'RECORD_TEST_AUTOSTART must be 0 or 1';; esac
export RECORD80_JPEG_QUALITY=$CFG_JPEG RECORD80_EXPOSURE_MODE=$CFG_EXPOSURE_MODE
export RECORD80_AUTO_EXP_MAX_US=$CFG_AUTO_EXP_MAX RECORD80_AUTO_AGAIN_MAX=$CFG_AUTO_AGAIN_MAX
export RECORD80_AUTO_DGAIN_MAX=$CFG_AUTO_DGAIN_MAX RECORD80_AUTO_ISPGAIN_MAX=$CFG_AUTO_ISPGAIN_MAX
export RECORD80_MANUAL_EXP_US=$CFG_MANUAL_EXP RECORD80_MANUAL_AGAIN=$CFG_MANUAL_AGAIN
export RECORD80_MANUAL_DGAIN=$CFG_MANUAL_DGAIN RECORD80_MANUAL_ISPGAIN=$CFG_MANUAL_ISPGAIN
export RECORD80_BLC_MODE=$CFG_BLC_MODE RECORD80_BLC_R=$CFG_BLC_R RECORD80_BLC_GR=$CFG_BLC_GR
export RECORD80_BLC_GB=$CFG_BLC_GB RECORD80_BLC_B=$CFG_BLC_B
if [ "$CFG_EXPOSURE_MODE" = manual ]; then
  AE_SUMMARY="manual_exp_us=$CFG_MANUAL_EXP gains=$CFG_MANUAL_AGAIN,$CFG_MANUAL_DGAIN,$CFG_MANUAL_ISPGAIN"
else
  AE_SUMMARY="auto_exp_max_us=$CFG_AUTO_EXP_MAX"
fi
CONFIG_SUMMARY="path=$CONFIG mode=$CFG_MODE run_sec=$MAX_RUN_SEC auto_record=$RECORD_TEST_AUTOSTART npu_model=$FLY_RM_MODEL vpss_gap_ms=$CAPTURE_VPSS_MIN_GAP_MS jpeg_quality=$CFG_JPEG exposure_mode=$CFG_EXPOSURE_MODE $AE_SUMMARY black_level_mode=$CFG_BLC_MODE blc=$CFG_BLC_R,$CFG_BLC_GR,$CFG_BLC_GB,$CFG_BLC_B"
if [ "${1-}" = --check-config ]; then
  echo "CONFIG_OK $CONFIG_SUMMARY"
  exit 0
fi
echo "RUN_CONFIG $CONFIG_SUMMARY"
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
test -x "$ROOT/camera_capture_first_baked70"
test ! -e "$LOCK" || { echo "CAMERA_LOCK_BUSY"; exit 2; }
if pidof camera_capture_first_baked camera_capture_first_baked70 camera_capture_first_yolo26 camera_preview_hd camera_preview80 camera_preview_factory camera_factory_timing camera_36record camera_capture_first_320 camera_vpss_320 camera_36probe camera_bench camera_http80 camera_normal60 camera_stream minraw36 minraw1080_27or36 sensor_test sample_vio >/dev/null 2>&1; then
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
cp "$CONFIG" "$REPORT/record80_opt.yaml"
mkdir -p /code/camera/recordings
mkdir "$LOCK"
LOCK_OWNED=1
cd /code/camera
export LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd:/usr/bin/lib
echo "NPU_CONFIG model=$FLY_RM_MODEL vpss_gap_ms=$CAPTURE_VPSS_MIN_GAP_MS"
export PREVIEW_DIAG_LINEAR=1
export PREVIEW_DIAG_RAW=1
# Prefer the actual Wi-Fi address; keep the legacy USB bind if wlan0 is down.
WEB_BIND_IP=$(ifconfig wlan0 2>/dev/null | awk '/inet addr:/ {sub(/^addr:/, "", $2); print $2; exit}')
if [ -z "$WEB_BIND_IP" ]; then WEB_BIND_IP=10.133.124.1; fi
echo "PREVIEW_BIND_IP=$WEB_BIND_IP"
"$ROOT/camera_capture_first_baked70" "$WEB_BIND_IP" "$REPORT" 80 >"$REPORT/capture.log" 2>&1 &
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
  sleep $((MAX_RUN_SEC + 20))
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
echo "LIVE_READY http://$WEB_BIND_IP:8081/ approx36MHz; time=$(now)"
echo "CLOCK_CCF_STALE=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
echo "LIFETIME_MAX=${MAX_RUN_SEC}s"
if [ "${RECORD_TEST_AUTOSTART:-0}" = 1 ]; then
  echo RECORD_START_REQUEST
  curl -fsS --max-time 5 -X POST "http://$WEB_BIND_IP:8082/start" || echo RECORD_START_HTTP_FAILED
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
STOP_REASON=timer_limit
echo "MAX_TIME_REACHED limit=${MAX_RUN_SEC}s"
