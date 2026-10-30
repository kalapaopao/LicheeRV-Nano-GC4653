# YOLO26n 实时后处理与 Wi-Fi 叠框：2026-10-31

## 交付结论

**实机已验证** SG2002 YOLO26n raw FP32 [1,5,2100] C++ 后处理、JSON 检测接口和网页 Canvas 叠框功能。原 36MHz 80FPS 采集、录像、300秒运行配置、74.5℃保护均保留。

- 单类别 `target`，输入320×320 NV21、输出通道优先 [1,5,2100]（XYWH+置信度）。
- 分数阈值 0.25；IoU 0.45 同类别 NMS；最多40框；原始1280×720信号经过320×320 letterbox，恢复坐标 x×4、(y−70)×4。
- 原始MJPEG在8081网页，8082新增 `GET /detections` JSON；网页用透明Canvas叠框并显示label、score和FPS；两条路径异步，**并非严格同一帧对齐**。
- 网页录像控制无身份认证，只能用于可信局域网。

## 真实验收

- 2026-10-31 板端短测20秒，独立实验二进制 `/code/camera/modules/record80_opt/camera_capture_first_yolo26`。
- 本地Windows C++测试 `YOLO26_POSTPROCESS_TEST_OK boxes=2 first=(560 280 720 440)`，验证置信度过滤、NMS、坐标映射。
- 浏览器原始网页 GET `http://192.168.1.103:8081/` 返回 HTTP200，5471字节；`http://192.168.1.103:8082/detections` 返回 HTTP200（样例：`{"model":"YOLO26n","class":"target","fps":31.16,"age_ms":29.99,"post_ms":0.29,"boxes":[]}`）。
- 网页JS由 `node --check` 验证通过。
- 板端 `/code/camera/modules/record80_opt/record_report/session_1793382438_986/capture.log`：采集稳态约80FPS；`YOLO26_POSTPROCESS frames=743 avg_us=244.4`；`infer=743 infer_errors=0 infer_avg_ms=31.925`。
- 当前场景没有达到置信度阈值的目标，因此 boxes=[]，**并没有正样本检测框位置的实机验收**，后续要拿实际目标放在摄像头前验证。
- 结束正常 `MAX_TIME_REACHED limit=20s`，时钟回到 `0x00200001`，无新增MIPI计数，摄像头锁释放；温度71.365℃。过热仍会提前停止。
- 使用 `sh /code/camera/modules/record80_opt/start.sh` 默认配置依旧是300秒，新增检测程序接入原入口。不会自动开机运行。

## 文件与回滚

本地：
- `npu_optimization/capture_pipeline_opt/yolo26_postprocess.h`：后处理/NMS
- `npu_optimization/capture_pipeline_opt/camera_capture_first_320.cpp`：NPU输出读取、HTTP JSON、Canvas叠框
- `npu_optimization/capture_pipeline_opt/tests/test_yolo26_postprocess.cpp`：纯C++测试
- `npu_optimization/capture_pipeline_opt/build_capture_first.sh`：交叉编译
- `npu_optimization/include/cviruntime.h` / `cvitpu_debug.h`：来自开源sophgo/tpu-mlir第三方CV18xx Runtime SDK，遵守源代码原有版权说明。

板端备份：
- 旧实验二进制 `camera_capture_first_320` 保存不动
- 旧入口 `/code/camera/modules/record80_opt/run_capture_first_before_postprocess.sh`
- 独立20秒测试脚本 `run_detect_overlay_trial.sh` 及 `config/record80_overlay_trial.yaml`

恢复原来的不叠框程序：
```sh
cp /code/camera/modules/record80_opt/run_capture_first_before_postprocess.sh \
   /code/camera/modules/record80_opt/run_capture_first.sh
```

独立稳定模块 `/code/camera/modules/record80` 未被更改。电脑端所有写入均在 `D:\study\LicheeRV` 内。不提交大模型、图像视频或二进制SDK。长时间运行需风扇/散热片，禁止调高温度限值代替散热。