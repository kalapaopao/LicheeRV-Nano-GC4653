# fly_rm 部署记录（LicheeRV Nano / SG2002）

## 模型来源

- 训练权重：`E:\study\X-AnyLabeling-main\xanylabeling_data\trainer\ultralytics\runs\detect\fly_rm\weights\best.pt`
- 类别：`target`（单类）
- 网络输入：`1x3x640x640`
- 本目录中的 `best.onnx` 是原始导出的端到端输出版本，保留作对照，不覆盖训练目录文件。
- `raw_export/best.onnx` 是重新导出的原始检测头版本，输出 `1x5x8400`，用于 SG2002 编译。

## 主机隔离环境

TPU-MLIR 使用 WSL Ubuntu-22.04 中的独立虚拟环境：

```bash
source /home/admin123/venvs/licheerv-sg2002-tpu-mlir/bin/activate
```

当前版本：`TPU-MLIR v1.30.2-20260831`。原 Windows 训练环境和系统 Python 未修改。

## 编译结果

`cv181x` 的 F32 降级在当前模型上触发 TPU-MLIR 的 `Not Implemented`，F16 编译成功：

```bash
model_transform.py \
  --model_name fly_rm_raw_nopp \
  --model_def raw_export/best.onnx \
  --input_shapes '[[1,3,640,640]]' \
  --mlir fly_rm_raw_nopp_fp32.mlir \
  --not_inference

model_deploy.py \
  --mlir fly_rm_raw_nopp_fp32.mlir \
  --chip cv181x \
  --quantize F16 \
  --model fly_rm_raw_nopp_f16.cvimodel \
  --skip_validation
```

不要把 `fly_rm_raw_nopp_f16.cvimodel` 配成现有 `yolov5s_224_int8.mud` 的 `yolov5` 模型。该模型输出原始 YOLO26 检测头，板端还需要按 YOLO26 规则做候选框解码和 NMS。

## 板端位置和实测命令

模型已上传到独立目录，不覆盖现有录像模块和系统模型：

```text
/code/camera/models/fly_rm/fly_rm_raw_nopp_f16.cvimodel
```

板端运行时需要先设置动态库路径：

```sh
export LD_LIBRARY_PATH=/usr/bin/lib
/usr/bin/model_runner \
  --model /code/camera/models/fly_rm/fly_rm_raw_nopp_f16.cvimodel \
  --input /code/camera/models/fly_rm/sample_input.npz \
  --output /code/camera/models/fly_rm/sample_output.npz \
  --enable-timer --count 1
```

已验证结果：

- 输入：`images <1,3,640,640>, fp32`
- 输出：`output0_Concat_f32 <1,5,8400,1>, fp32`
- 板端 NPU 单次耗时：`122.499 ms`，约 `8.16 FPS`
- 输出文件：`sample_output.npz`

## 尚未接入项

当前完成的是独立 NPU 模型部署和推理冒烟测试。`modules/record80` 仍是录像程序，尚未把摄像头帧采集、640x640 预处理、YOLO26 解码/NMS、目标框绘制或 HTTP 输出接入该程序。接入时应复用本目录的输入约定和模型文件，并单独验证整链路帧率与检测准确性。
