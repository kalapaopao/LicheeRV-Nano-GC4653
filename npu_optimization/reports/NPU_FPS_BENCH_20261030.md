# LicheeRV Nano fly_rm 模型板端 NPU 性能实测（2026-10-30）

## 测试范围

本次通过 AgentDock 登录板端 `root@10.133.125.1`，直接在 SG2002 / RISC-V Linux 上执行 `model_runner`。该记录是 **NPU 纯推理基准**，并非相机→预处理→推理→YOLO 解码/NMS→显示的端到端实时识别帧率。

- 板端内核：`Linux 5.10.4-tag- riscv64`
- 运行时：`Cvitek Runtime 1.4.0`，cvimodel version 1.4，platform cv181x
- 模型位置：`/code/camera/models/fly_rm/`
- 运行库：`/usr/bin/lib`（本次仅通过临时环境变量 `LD_LIBRARY_PATH` 引用，不更改系统设置）
- 基准方法：`model_runner --count 100 --enable-timer`，每个模型使用匹配尺寸的现有 `sample_input_*.npz`，并指定临时 output；测试后删除临时 `.fps_probe_*.npz`。
- 温度：测试前约 64°C，全部测试结束约 67.9°C。
- 内存：板端 MemAvailable 约 82,700 kB。
- 板端 `date` 显示 1970-01-01（时钟未同步），因此本记录日期以操作电脑本地日期为准。

## 实测数据

| cvimodel | 输入 | 精度（文件标识） | 100 次总耗时 | 平均每次 | 推理 FPS |
|---|---|---|---:|---:|---:|
| `fly_rm_192_f16.cvimodel` | 1×3×192×192 | FP16 | 1160.54 ms | 11.605 ms | **86.169754** |
| `fly_rm_224_f16.cvimodel` | 1×3×224×224 | FP16 | 1556.47 ms | 15.564 ms | **64.250835** |
| `fly_rm_320_f16.cvimodel` | 1×3×320×320 | FP16 | 3005.42 ms | 30.054 ms | **33.273441** |
| `fly_rm_320_int8.cvimodel` | 1×3×320×320 | INT8 | 3533.92 ms | 35.339 ms | **28.297349** |

模型输出张量示例：320×320 时为 `output0_Concat_f32 <1,5,2100,1>`，224×224 为 `<1,5,1029,1>`，192×192 为 `<1,5,756,1>`。工具列出的输入也是 fp32；因此模型文件名中的 INT8/FP16 不代表输入和输出张量的数据类型，也不能从文件名直接判断所有算子量化情况。

## 可复现命令

在板端执行，以下以 320×320 FP16 为例：

```sh
LD_LIBRARY_PATH=/usr/bin/lib model_runner \
  --model /code/camera/models/fly_rm/fly_rm_320_f16.cvimodel \
  --input /code/camera/models/fly_rm/sample_input_320.npz \
  --output /code/camera/models/fly_rm/.fps_probe_320f16.npz \
  --count 100 --enable-timer

# 测试确认后移除本次临时输出
rm -f /code/camera/models/fly_rm/.fps_probe_320f16.npz
```

其他规格替换模型名、输入尺寸和临时输出名即可。**一定要带上 `--input` 和 `--output`**：仅指定模型和 `--count` 时此前只显示结构，未打印 Performance result，不能当作有效性能测试。

## 结论及下一步

- 320×320 实测约 **28–33 FPS**；本次 320 FP16（33.27）反而快于 320 INT8（28.30）。要确认原因，应比较模型转换日志、量化与 BF16 层布局、内存搬运和是否发生 CPU fallback；不能简单推断 INT8 无效。
- 224 FP16 约 **64.25 FPS**，192 FP16 约 **86.17 FPS**，但缩小输入可能降低细小目标召回率，需要通过同一验证集比较精度。
- 之前 GC4653 约 80 FPS 的成绩指相机采集/预览，并非 YOLO 实时识别速度。端到端 FPS 还会受到预处理、后处理、线程调度、摄像头吞吐与显示影响，本次未测，不应直接宣称实时 86 FPS。
- 本次开始检查时未发现正在运行的 model_runner 或相机预览/识别进程。测试结束时没有遗留 model_runner 和临时 `.fps_probe_*` 文件。
- 后续若需实测端到端 FPS，建议在已验证相机程序的基础上增加图像前处理 + CVI_NN_Forward + YOLO 后处理的完整计时，分别记录 capture FPS / infer FPS / end-to-end FPS；修改前保留原 80 FPS 方案。

## 本次变更边界

- 没有覆盖板端已有模型文件或摄像头程序。
- 没有变更 SDK/驱动/系统动态库。
- 没有执行 git commit / push。
- 电脑只在 `D:\study\LicheeRV` 项目下新增本报告。
