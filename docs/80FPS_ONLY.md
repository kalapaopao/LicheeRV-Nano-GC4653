# 当前 80FPS 工程入口

当前仓库以 GC4653 80FPS 采集和 `fly_rm` 实时推理为主线。

> **2026-10-30 更新：** 本页原有 `fly_rm_320_int8.cvimodel` + `run_board_yolo320.sh` 是**历史已验证运行入口**，不等于最新速度最佳方案。实测最新YOLO26n 320×320 FP16、VI优先VPSS的 C++ 实验请到 [NPU / VPSS 独立研究模块](../npu_optimization/README.md)。该独立实验约80 FPS是真实采集，NPU约31.6次前向/秒，真实检测框和端到端识别FPS尚未验收；请勿覆盖既有稳定录像程序。

## 板端启动

```sh
export LD_LIBRARY_PATH=/code/camera/lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd:/usr/bin/lib
export FLY_RM_MODEL=/code/camera/models/fly_rm/fly_rm_320_int8.cvimodel
sh /code/camera/modules/record80/run_board_yolo320.sh
```

不设置 `FLY_RM_MODEL` 时，只运行 80FPS 采集。设置后，程序在采集路径中调用 `CVI_NN`，日志显示采集帧、完成推理帧、跳过帧和平均推理耗时。

## 代码入口

- `modules/record80/src/camera_36record.cpp`：摄像头、编码、模型调用和运行统计。
- `modules/record80/include/cviruntime.h`：板端运行时所需的最小官方接口声明。
- `modules/record80/scripts/build.sh`：交叉编译。
- `modules/record80/scripts/run_board.sh`：板端 80FPS 启动和硬件状态检查。
- `model_deploy/fly_rm/BOARD_320_INT8.md`：模型转换、部署和实时测试记录。

旧的 60FPS 测试结果已清理。公共 SDK、80FPS 测试、录像模块和模型部署文件保留。
