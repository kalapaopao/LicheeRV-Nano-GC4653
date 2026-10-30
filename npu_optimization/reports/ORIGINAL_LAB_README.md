## 新版：320 FP16 VPSS + NPU 实测及准确率对照（2026-10-30）

**优先阅读 [REPORT_320_VPSS_ACCURACY_20261030.md](REPORT_320_VPSS_ACCURACY_20261030.md)**。本轮使用用户原始验证集 31 张图对 640/320/224/192 输入进行公平对照，同时部署了独立 320x320 NV21 VPSS 硬件缩放 + 融合预处理 CVI F16 模型。板端采集约80FPS，NPU Forward约31.6次/秒；没有丢失原有稳定取流方案。请注意本轮尚未完成 CVImodel 与 best.pt 数值对齐、YOLO26 叠框/网页显示与板端 mAP 复测，**不得将 NPU forward 次数描述为真实检测 FPS**。实验数据保存在 `reports/eval_summary.json` 和 `reports/vpss_320_board_capture.log`。

# GC4653 × SG2002 NPU 性能优化实验

本目录为独立的 Linux 线程调度和 NPU 输入预取实验。**没有替换原来的 36 MHz / 80 FPS 稳定相机程序。**

- 真实板端测试、成功/失败、FPS 对照：见 [REPORT_20261030.md](REPORT_20261030.md)。
- `src/camera_36record_opt.cpp`：从公开项目 `modules/record80/src/camera_36record.cpp` 复制后改造成双模型输入预取 + 可选同步推理，**仅为实验版**。
- `scripts/build_opt.sh`：通过 WSL 里的 RISC-V musl SDK 交叉编译，输出到本目录的 `bin/`。
- `scripts/run_board_opt.sh`、`scripts/run_board_opt_sync.sh`：实验版的原有摄像头时钟保护/温度保护包装，板端使用 `/code/camera/modules/record80_opt/`。
- `scripts/run_stable_fp16.sh`：已在板端通过 `--check-config` 验证，可安全选择 320/224/192 三种现有模型，并继续调用原版稳定摄像头程序，不需修改原版脚本。

## 默认安全使用

```sh
sh /code/camera/modules/record80_opt/run_stable_fp16.sh 320
# 只做配置验收：
sh /code/camera/modules/record80_opt/run_stable_fp16.sh 320 --check-config
```

默认运行 60s，禁止自动录像。输入尺寸更小时可手动选择 `224`、`192`，但是未验收真实检出框和小目标精度。

**重要**：当前源程序只有 NPU Forward，没有完整的颜色/缩放输入正确性验证、YOLO26 解码/NMS 或叠框显示。本文提到的推理吞吐不是最终目标检测 FPS。

实验版中双模型预取导致摄像头采集降到约 31.5FPS，另一种同步推理导致摄像头降到约 40FPS；两种都不适合作为默认程序。请保留原先稳定版。
