#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TMPDIR="$ROOT/cache/tmp"
mkdir -p "$TMPDIR" "$ROOT/models/vpss320"
source /home/admin123/venvs/licheerv-sg2002-tpu-mlir/bin/activate
cd "$ROOT/models/vpss320"
model_transform.py --model_name fly_rm320_v8_vpss --model_def "$ROOT/models/best.onnx" \
  --input_shapes '[[1,3,320,320]]' --pixel_format rgb --channel_format nchw \
  --mean 0,0,0 --scale 0.003921568627,0.003921568627,0.003921568627 \
  --mlir fly_rm320_v8_vpss_fp32.mlir --not_inference
model_deploy.py --mlir fly_rm320_v8_vpss_fp32.mlir --chip cv181x --quantize F16 \
  --fuse_preprocess --customization_format YUV_NV21 --aligned_input \
  --model fly_rm320_v8_vpss_nv21_f16.cvimodel --skip_validation
echo COMPILED
sha256sum fly_rm320_v8_vpss_nv21_f16.cvimodel
