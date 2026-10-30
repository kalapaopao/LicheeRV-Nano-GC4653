# YOLO26n 置信度阈值 70%（2026-10-31）

用户希望从25%提升至70%，排查远处发光灯等局部特征误检。只修改YOLO后处理的`score >= 0.70`，NMS IoU 0.45、模型、曝光/时钟/安全策略均不变。
**置信度70%只是过滤预测分数，不是模型准确率70%。** 阈值变高可减少低置信度误检，也可能增大漏检，尤其目标小且偏暗。

板端：`/code/camera/modules/record80_opt/camera_capture_first_baked70`。
已将`/code/camera/modules/record80_opt/start.sh`默认入口下的`run_capture_first.sh`切换为此二进制，仍读取`config/record80_opt.yaml`的`max_run_sec: 300`（过热可能提前退出）。
备份：`/code/camera/modules/record80_opt/run_capture_first_before_conf70.sh`；旧25%程序`camera_capture_first_baked`没有覆盖。

短时实测：20秒实验脚本`run_baked70_trial.sh`，日志`conf70_baked_trial.log`。从capture.log确认`YOLO_CONFIDENCE_THRESHOLD=0.70 NMS_IOU=0.45`。
- HTTP /detect.jpg 200，/detections 200，检测FPS采样28.72，浏览器无需Canvas绘框
- 最终`BAKED_PREVIEW frames=492 errors=0 boxes=0`，`forwards=706 forward_errors=0`，`stopped frames=1995 encoded=1963`，原始采集约80FPS
- 验收场景没出现分数达到0.70的目标（boxes=[]），尚不能证明灯光是否误检，需要用户摆放真实目标验证
- `MAX_TIME_REACHED limit=20s`，`FINAL_MMIO=0x00200001`，LOCK_RELEASED，温度68.568℃

正常使用：
```sh
sh /code/camera/modules/record80_opt/start.sh
```
浏览器`http://192.168.1.103:8081/`（Wi-Fi地址变化时用实际wlan0 IP）。
退回25%（停止运行后）：
```sh
cp /code/camera/modules/record80_opt/run_capture_first_before_conf70.sh \
 /code/camera/modules/record80_opt/run_capture_first.sh
```
两版本独立，禁止覆盖原来的25%二进制。无模型、视频或编译二进制纳入Git。