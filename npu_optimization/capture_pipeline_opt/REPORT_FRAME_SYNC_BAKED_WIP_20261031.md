# 2026-10-31 板端带框同帧预览改造：实验报告（尚未通过）

## 稳定回滚点
- 当前正常版本：Git commit f98aafe，tag baseline-yolo26-canvas-20261031，已推送GitHub。
- 实验分支 feature/frame-synced-server-overlay；板端默认 /code/camera/modules/record80_opt/start.sh 保持原Canvas检测程序，300秒参数不变。
- 板端新二进制 camera_capture_first_baked、新脚本 run_baked_trial.sh、新config/record80_baked_trial.yaml 独立存在，限时20秒；旧 camera_capture_first_yolo26 二进制完全未覆盖。
- 原始 /code/camera/modules/record80 稳定录像模块未改动。

## 本次实现
- 原1280x720 VI -> VENC0 JPEG -> /live.mjpg（保持原取流与录像）。
- VPSS 320x320 NV21 -> YOLO26n -> NMS -> 在同一VPSS帧的Y/VU平面画绿色框 -> 独立VENC1 JPEG -> /detect.mjpg 与 /detect.jpg。
- 网页增加原图/带框模式切换，不再按120ms轮询Canvas画框，/detections仍可查询性能。
- 第一阶段只尝试320x320 letterbox带框图，尚不是1280x720带框原图；框内置信度文字未烘焙进JPEG。
- 若要严格原1280x720同帧，应优先完成两个VPSS输出共享PTS后匹配，不能简单用最近的框。

## 两次板端实测（未通过）
第一次：20秒，capture.log session_1793384780_1814。
- /detect.jpg HTTP200，确实生成有效JPEG约8.6KB；/snapshot.jpg HTTP200原画；/detections HTTP200。
- 原始取流约80FPS，但带框通道只有约1FPS，BAKED_PREVIEW frames=8 errors=17，VPSS_NPU_FINAL forwards=25，平均infer约964.6ms。
- SDK错误0xc0078012，对应CVI_ERR_VENC_INVALID_VB。

第二次：20秒，增加stage、PTS、物理地址跟踪。
- BAKED_VENC_ERROR stage=send rc=0xc0078012，失败在CVI_VENC_SendFrame(1,&frame,150)，不是网页/NMS/GetStream。
- BAKED_PREVIEW frames=19 errors=14，forwards=33，infer_avg_ms=736.3，原采集仍约80FPS。
- 正常限时退出，FINAL_MMIO=0x00200001、摄像头锁释放，最终温度69.267℃。

## 后续验证方向
1. 查CVI VB池/帧所有权和VENC1输入格式：验证使用CVI_VB_GetBlock分配合法VB，复制VPSS像素后交VENC1，同时统计分配、拷贝和送帧耗时。
2. 若硬编缓存不可兼容，则尝试独立320x320 NV21→RGB→libjpeg软件编码，测CPU、温度和检测吞吐，不得明显损害原80FPS采集。
3. 要实现原画1280x720同步，使用另一VPSS输出共享PTS、队列上限、丢帧和时钟保护，再进行同步叠框，不可直接追随最新结果。

## 安全与使用
**实验已开始但尚未可用，严禁把此分支二进制覆盖现有稳定程序。** 目前依旧使用：
    sh /code/camera/modules/record80_opt/start.sh

所有电脑端写文件仅D:\study\LicheeRV；不提交模型、视频、图像、构建产物。实验结果已记录，下一步在有可测的合法VENC VB后再正式替换。