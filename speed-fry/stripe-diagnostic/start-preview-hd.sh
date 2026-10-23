#!/bin/sh
set -eu
BASE=/code/camera
MODE=${1:-80}
IP=${2:-10.133.125.1}
case "$IP" in 10.133.125.1|10.133.124.1) ;; *) echo 'Unsupported USB bind IP' >&2; exit 2;; esac
case "$MODE" in 60|80) ;; *) echo 'Usage: start-preview-hd.sh [60|80] [USB_BIND_IP]' >&2; exit 2;; esac
if [ "${PREVIEW_HD_CHILD:-0}" != 1 ]; then
  test -x "$BASE/bin/camera_preview_hd"
  mkdir -p "$BASE/run" "$BASE/reports"
  mkdir "$BASE/run/lock" 2>/dev/null || { echo 'Camera is busy'; exit 1; }
  PREVIEW_HD_CHILD=1 nohup sh "$0" "$MODE" "$IP" </dev/null >"$BASE/run/preview-hd-launch.log" 2>&1 &
  exit 0
fi
PID=''
cleanup(){
  trap - EXIT INT TERM HUP
  if [ -n "$PID" ]; then kill -TERM "$PID" 2>/dev/null || true; wait "$PID" || true; fi
  rm -f "$BASE/run/camera.pid" "$BASE/run/preview-hd.pid"
  rmdir "$BASE/run/lock"
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP
REPORT="$BASE/reports/preview-hd-$(cut -d. -f1 /proc/uptime)-$$"
mkdir "$REPORT"
echo "$REPORT" >"$BASE/run/preview-hd.report"
echo $$ >"$BASE/run/preview-hd.pid"
export LD_LIBRARY_PATH="$BASE/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
"$BASE/bin/camera_preview_hd" "$IP" "$REPORT" "$MODE" >"$REPORT/run.log" 2>&1 &
PID=$!
echo "$PID" >"$BASE/run/camera.pid"
set +e
wait "$PID"
RC=$?
set -e
PID=''
echo "$RC" >"$REPORT/exit-code.txt"
exit "$RC"
