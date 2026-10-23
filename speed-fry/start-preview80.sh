#!/bin/sh
set -eu
BASE=/code/camera
IP=${1:-10.133.125.1}
case "$IP" in *[!0-9.]*|'') echo 'Invalid IPv4 address' >&2; exit 2;; esac
test -x "$BASE/bin/camera_preview80"
command -v ffmpeg >/dev/null
mkdir -p "$BASE/run" "$BASE/reports"
if [ "${PREVIEW80_CHILD:-0}" != 1 ]; then
  if ! mkdir "$BASE/run/lock" 2>/dev/null; then echo 'Camera busy. Do not delete the lock.' >&2; exit 1; fi
  PREVIEW80_CHILD=1 nohup sh "$0" "$IP" </dev/null >"$BASE/run/preview80-launch.log" 2>&1 &
  # Child owns the lock created above.
  exit 0
fi
PID=''
cleanup() {
  trap - EXIT INT TERM HUP
  if [ -n "$PID" ]; then kill -TERM "$PID" 2>/dev/null || true; wait "$PID" || true; fi
  rm -f "$BASE/run/camera.pid" "$BASE/run/preview80.pid"
  rmdir "$BASE/run/lock"
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP
REPORT="$BASE/reports/preview80-$(cut -d. -f1 /proc/uptime)-$$"
mkdir "$REPORT"
echo "$REPORT" >"$BASE/run/preview80.report"
echo $$ >"$BASE/run/preview80.pid"
export LD_LIBRARY_PATH="$BASE/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
"$BASE/bin/camera_preview80" "$IP" >"$REPORT/run.log" 2>&1 &
PID=$!
echo "$PID" >"$BASE/run/camera.pid"
set +e
wait "$PID"
RC=$?
set -e
PID=''
echo "$RC" >"$REPORT/exit-code.txt"
exit "$RC"
