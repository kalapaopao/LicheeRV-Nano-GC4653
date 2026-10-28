#!/bin/sh
# Pure configuration validation: never start the camera.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
CASES="$ROOT/test/blc_config_20261024/cases"
RUNNER="$ROOT/modules/record80/scripts/run_board.sh"
check() {
  name=$1 expected=$2 text=$3
  set +e
  output=$(RECORD80_CONFIG="$CASES/$name.yaml" sh "$RUNNER" --check-config 2>&1)
  code=$?
  set -e
  printf '%s: rc=%s expected=%s %s\n' "$name" "$code" "$expected" "$output"
  [ "$code" -eq "$expected" ] || exit 1
  case "$output" in *"$text"*) :;; *) echo BAD_OUTPUT; exit 1;; esac
}
check manual 0 'black_level_mode=manual blc=256,256,256,256'
check legacy 0 'black_level_mode=default'
check default 0 'black_level_mode=default'
check crlf 0 'black_level_mode=manual'
check boundary_zero 0 'blc=0,256,256,256'
check boundary_max 0 'blc=4095,256,256,256'
check bad_mode 2 'black_level_mode must be default or manual'
check out_of_range 2 'black_level_r out of range'
check negative 2 'black_level_gb must be an integer'
check missing 2 'black_level_r must be an integer'
check duplicate 2 'duplicate key black_level_r'
check fractional 2 'black_level_r must be an integer'
echo CONFIG_TESTS_PASS=12
