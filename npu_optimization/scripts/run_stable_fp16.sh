#!/bin/sh
# Stable camera/recording implementation + selectable existing FP16-labelled cvimodel.
# Does not modify the original run_board_yolo320.sh or existing binaries.
# sh run_stable_fp16.sh 320|224|192 [--check-config]
set -eu
SIZE=${1:-320}
case "$SIZE" in
  320|224|192) ;;
  *) echo "Usage: sh $0 [320|224|192] [--check-config]" >&2; exit 2 ;;
esac
shift || :
MODEL="/code/camera/models/fly_rm/fly_rm_${SIZE}_f16.cvimodel"
test -r "$MODEL" || { echo "MODEL_NOT_FOUND $MODEL" >&2; exit 3; }
echo "SELECTED_MODEL=$MODEL"
echo "NOTE: forward FPS only; YOLO preprocessing and bounding-box output are not validated"
export FLY_RM_MODEL="$MODEL"
export RECORD_TEST_AUTOSTART=0
: "${MAX_RUN_SEC:=60}"
export MAX_RUN_SEC
exec sh /code/camera/modules/record80/run_board_yolo320.sh "$@"
