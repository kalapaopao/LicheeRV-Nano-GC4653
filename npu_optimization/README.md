# YOLO26n FP16 × SG2002 VPSS × GC4653 80FPS：C++ 优化实验

> **独立实验，不替换稳定采集版。** 已完成300秒长测的 [原80FPS相机入口](../test/clock36_live_20261023/README.md) 继续保留。图像采集、硬件缩放、NPU和异步JPEG均使用 C++11，Python只用于PC导出和离线模型比较。

## 实测性能（2026-10-30）

| 流水线 | VI取帧 | JPEG编码 | VPSS处理 | NPU前向 | 验证状态 |
|---|---:|---:|---:|---:|---|
| YOLO26n，JPEG后置VPSS | 约80FPS | 约60FPS | 约60FPS | 31.582ms / 31.66次每秒 | 完整短测 |
| YOLO26n，C++采集后VPSS（全帧） | 约80FPS | 约80FPS | 约80FPS | 32.031ms / 31.22次每秒 | 完整短测 |
| YOLO26n，采集后VPSS（20ms间隔） | 约80FPS | 约80FPS | 约40FPS | 31.649ms / 31.60次每秒 | **仅运行中统计，SSH中断，无最终退出验收** |
| YOLOv8n，同样320 FP16 | 约80FPS | 约60FPS | 约60FPS | 38.553ms / 25.94次每秒 | 完整短测 |

**结论：** YOLO26n在SG2002上比YOLOv8n前向吞吐高约22%；把VPSS从JPEG线程前移后，JPEG编码由约60达到约80FPS，VPSS可在20ms限频下减少一半冗余工作；**NPU仍约31.6次前向/秒，并不是80FPS目标检测**。

可复核数据：[board_benchmarks_20261030.json](benchmarks/board_benchmarks_20261030.json)、[采集优化交接](capture_pipeline_opt/REPORT_CPP_CAPTURE_PIPELINE_20261030.md)、[YOLO26模型报告](fly_rm320/REPORT_20261030_NEW_MODEL.md)、[YOLOv8对照报告](fly_rm320_v8/REPORT_V8_VS_YOLO26_20261030.md)。

## 最新 C++11 源码

```text
GC4653 → VI 1280×720 NV21 (~80FPS)
          ├─→ VPSS 320×320 NV21 → 最新帧单槽 → CVI_NN_Forward (~31.6次/秒)
          └─→ 异步硬件 VENC JPEG (~80FPS) → HTTP/录像
```

- [camera_capture_first_320.cpp](capture_pipeline_opt/camera_capture_first_320.cpp)：VI优先VPSS、20ms节流、异步VENC、最新帧缓存。
- [camera_vpss_320.cpp](vpss_pipeline/camera_vpss_320.cpp)：旧JPEG后VPSS的C++对照。
- [C++交叉编译](capture_pipeline_opt/build_capture_first.sh)、[研究级受监督运行](capture_pipeline_opt/run_capture_first.sh)、[录像线程头文件](include/record80.h)。

在本机 WSL 中，克隆仓库与原实验SDK工作区必须都在 Windows D:\study\LicheeRV：
```bash
cd /mnt/d/study/LicheeRV/LicheeRV-Nano-GC4653
bash npu_optimization/capture_pipeline_opt/build_capture_first.sh
```

脚本从**本仓库读取源码**，从旁边的 `gc4653_36mhz_80fps_20261019` 工作区读取厂商SDK和工具链，输出被Git忽略的 `npu_optimization/bin/camera_capture_first_320`。另一个机器可设置 `LICHEERV_LAB_ROOT` 为SDK工作区绝对路径。模型文件、板端程序、厂商SDK、录像和传感器原始数据**不在公开仓库**。

板端实验路径 `/code/camera/modules/record80_opt` 中保留已部署程序，当前模型为新训练 YOLO26n `fly_rm320_new_vpss_nv21_f16.cvimodel`；显式20ms短测命令：
```sh
MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 CAPTURE_VPSS_MIN_GAP_MS=20 FLY_RM_MODEL=/code/camera/modules/record80_opt/fly_rm320_new_vpss_nv21_f16.cvimodel sh /code/camera/modules/record80_opt/run_capture_first.sh
```

**安全事项：** 临时切换CAM1分频只用于有人监护的实验。一次SSH强制中断导致时钟未自动恢复和空锁目录，之后人工确认无摄像头进程、恢复 `0x00200001` 并清锁。独立看门狗异常退出仍未验收；切勿无人值守运行、强杀进程或覆盖稳定版本。

**精度边界：** YOLO26与YOLOv8各31张验证图，但只有3张共同未见图，另外28张互相进入对方的训练集。仅3张共同未见图上召回都为100%，mAP50-95约70.18%和68.02%；样本量不足以确立泛化精度优劣。完整YOLO解码/NMS/叠框、正样本的板端精度和真正端到端FPS仍未验收。
