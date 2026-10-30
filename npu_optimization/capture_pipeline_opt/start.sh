#!/bin/sh
# One command entry point; all runtime settings come from config/record80_opt.yaml.
set -eu
ROOT=/code/camera/modules/record80_opt
exec sh "$ROOT/run_capture_first.sh" "$@"
