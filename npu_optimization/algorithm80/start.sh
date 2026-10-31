#!/bin/sh
# Pure YOLO26n module: independent from record80_opt.
set -eu
ROOT=/code/camera/modules/algorithm80
exec sh "$ROOT/run_algo80.sh" "$@"