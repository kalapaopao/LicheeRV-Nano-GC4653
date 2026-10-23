#!/bin/sh
set -eu
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ARCHIVE="$DIR/board-runtime.tar.gz"
[ -f "$ARCHIVE" ] || { echo "board-runtime.tar.gz must be next to this script" >&2; exit 2; }
[ -d /code ] || { echo "Missing /code; verify this is the intended board" >&2; exit 2; }
if [ -e /code/camera ] || [ -L /code/camera ]; then
  echo "/code/camera already exists. Refusing to overwrite; read docs/HANDOVER.md." >&2
  exit 3
fi
# Atomic creation also prevents accidental overwrite if another installer runs.
mkdir /code/camera
tar -xzf "$ARCHIVE" -C /code
echo "Installed /code/camera. No system files replaced; camera not started."
echo "Run: sh /code/camera/scripts/benchmark.sh 80 60"
