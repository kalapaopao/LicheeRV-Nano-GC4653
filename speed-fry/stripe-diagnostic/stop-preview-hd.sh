#!/bin/sh
set -eu
FILE=/code/camera/run/preview-hd.pid
[ -f "$FILE" ] || { echo 'HD preview is not running'; exit 0; }
PID=$(cat "$FILE")
case "$PID" in ''|*[!0-9]*) echo 'Invalid PID' >&2; exit 1;; esac
tr '\000' ' ' <"/proc/$PID/cmdline" | grep -q 'start-preview-hd.sh' || { echo 'PID mismatch' >&2; exit 1; }
kill -TERM "$PID"
echo 'Normal shutdown requested'
