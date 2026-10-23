#!/bin/sh
set -eu
FILE=/code/camera/run/preview80.pid
[ -f "$FILE" ] || { echo 'Preview is not running'; exit 0; }
PID=$(cat "$FILE")
case "$PID" in ''|*[!0-9]*) echo 'Invalid PID' >&2; exit 1;; esac
tr '\000' ' ' <"/proc/$PID/cmdline" | grep -q 'start-preview80.sh' || { echo 'PID mismatch; refusing to signal' >&2; exit 1; }
kill -TERM "$PID"
echo 'Normal shutdown requested'
