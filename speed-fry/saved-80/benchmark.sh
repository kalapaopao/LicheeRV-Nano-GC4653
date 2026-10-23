#!/bin/sh
set -eu
BASE=/code/camera
MODE=${1:-30}
DURATION=${2:-20}
EXTRA=""
case "$MODE" in
  30) BIN="$BASE/bin/camera_bench_baseline"; FPS=30 ;;
  60|80) BIN="$BASE/bin/camera_bench"; FPS="$MODE" ;;
  60-manual) BIN="$BASE/bin/camera_bench"; FPS=60; EXTRA=manual ;;
  60-ae-fix) BIN="$BASE/bin/camera_bench_ae_fix"; FPS=60 ;;
  60-refresh) BIN="$BASE/bin/camera_bench_ae_fix"; FPS=60; EXTRA=refresh ;;
  30-maix) BIN="$BASE/bin/camera_bench"; FPS=30 ;;
  *) echo "Usage: $0 {30|60|80|60-manual|60-ae-fix|60-refresh|30-maix} [3..300 seconds]" >&2; exit 2 ;;
esac
case "$DURATION" in ''|*[!0-9]*) echo "Invalid duration" >&2; exit 2 ;; esac
[ "$DURATION" -ge 3 ] && [ "$DURATION" -le 300 ] || exit 2
mkdir -p "$BASE/run" "$BASE/reports"
if ! mkdir "$BASE/run/lock" 2>/dev/null; then
  echo "Camera test lock exists. Use stop.sh or inspect /code/camera/run." >&2; exit 1
fi
PID=""
cleanup() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then kill -TERM "$PID"; wait "$PID" || true; fi
  rm -f "$BASE/run/camera.pid"
  rmdir "$BASE/run/lock" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
UPTIME=$(cut -d. -f1 /proc/uptime)
REPORT="$BASE/reports/user-$MODE-$UPTIME-$$"
mkdir "$REPORT"
grep MemAvailable /proc/meminfo > "$REPORT/memory-before.txt"
printf 'mode=%s\nduration=%s\nextra=%s\n' "$MODE" "$DURATION" "$EXTRA" > "$REPORT/command.txt"
echo "Report: $REPORT"
export LD_LIBRARY_PATH="$BASE/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd"
if [ -n "$EXTRA" ]; then
  "$BIN" "$FPS" "$DURATION" "$REPORT" "$EXTRA" > "$REPORT/run.log" 2>&1 &
else
  "$BIN" "$FPS" "$DURATION" "$REPORT" > "$REPORT/run.log" 2>&1 &
fi
PID=$!
echo "$PID" > "$BASE/run/camera.pid"
set +e
wait "$PID"
RC=$?
set -e
PID=""
echo "$RC" > "$REPORT/exit-code.txt"
grep MemAvailable /proc/meminfo > "$REPORT/memory-after.txt"
[ ! -f "$REPORT/result.json" ] || cat "$REPORT/result.json"
echo "Exit code: $RC"
exit "$RC"
