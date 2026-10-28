#!/bin/sh
# One-off recovery after inspection: no recursive removal, no process kill.
set -eu
LOCK=/code/camera/run/lock
ROOT=/code/camera/modules/record80
REPORT=/code/camera/diagnostics/lock_recovery_20261025
if pidof camera_preview_hd camera_preview80 camera_preview_factory camera_factory_timing camera_36record camera_36probe camera_bench camera_http80 camera_normal60 camera_stream minraw36 minraw1080_27or36 sensor_test sample_vio >/dev/null 2>&1; then
    echo CAMERA_PROCESS_BUSY; exit 2
fi
[ ! -L "$LOCK" ]
[ -d "$LOCK" ]
# The inspected stale PID must still be unchanged and absent.
[ "$(cat "$ROOT/record_cam.pid")" = 2638 ]
[ ! -e /proc/2638 ]
[ "$(devmem 0x030028c4 32)" = 0x00200001 ]
grep -q 'VI DEV ATTR1' /proc/cvitek/vi
if awk '/VI DEV ATTR1/{p=1;next} p && /^-/{p=0} p && $1 ~ /^[0-9]+$/ && $2 != 0 {active=1} END{exit active?0:1}' /proc/cvitek/vi; then
    echo VI_ACTIVE; exit 2
fi
[ ! -e "$REPORT" ]
mkdir "$REPORT"
ls -lad "$LOCK" > "$REPORT/lock_before.txt"
ls -la "$LOCK" >> "$REPORT/lock_before.txt"
cp -p "$ROOT/record_cam.pid" "$REPORT/record_cam.pid.before"
ps > "$REPORT/processes_before.txt"
cat /proc/cvitek/vi > "$REPORT/vi_before.txt"
cat /proc/mipi-rx > "$REPORT/mipi_before.txt"
cat /proc/uptime > "$REPORT/uptime_before.txt"
sha256sum "$ROOT/camera_36record" "$ROOT/run_board.sh" "$ROOT/config/record80.yaml" > "$REPORT/protected.sha256"
# This can remove only an empty directory. Fail closed if anything was added.
rmdir "$LOCK"
echo STALE_EMPTY_LOCK_REMOVED
sha256sum -c "$REPORT/protected.sha256"
echo RECOVERY_REPORT="$REPORT"
