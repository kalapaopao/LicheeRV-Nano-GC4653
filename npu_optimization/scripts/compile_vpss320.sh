#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/models/vpss320" "$ROOT/cache/tmp"
export TMPDIR="$ROOT/cache/tmp"
source /home/admin123/venvs/licheerv-sg2002-tpu-mlir/bin/activate
cd "$ROOT/models/vpss320"
# best.onnx must be RAW [1,5,2100], not YOLO26 [1,300,6] NMS-free model.
model_transform.py \
  --model_name fly_rm_320_vpss \
  --model_def "$ROOT/models/best.onnx" \
  --input_shapes '[[1,3,320,320]]' \
  --pixel_format rgb --channel_format nchw \
  --mean 0,0,0 --scale 0.003921568627,0.003921568627,0.003921568627 \
  --mlir fly_rm_320_vpss_fp32.mlir --not_inference
model_deploy.py \
  --mlir fly_rm_320_vpss_fp32.mlir \
  --chip cv181x --quantize F16 \
  --fuse_preprocess --customization_format YUV_NV21 --aligned_input \
  --model fly_rm_320_vpss_nv21_f16.cvimodel \
  --skip_validation
sha256sum fly_rm_320_vpss_nv21_f16.cvimodel
echo FUSED_MODEL_READY
