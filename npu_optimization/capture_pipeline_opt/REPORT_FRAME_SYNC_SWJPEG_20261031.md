# 2026-10-31 SG2002 YOLO26n 板端同帧绘框 JPEG 实机验收

## 最终结果与默认入口

本次已把板端`/code/camera/modules/record80_opt/start.sh`指向新独立二进制`camera_capture_first_baked`，成功通过20秒独立实机验收。原Canvas二进制`camera_capture_first_yolo26`、采集版`camera_capture_first_320`均保留；以前的run_capture_first.sh备份于`run_capture_first_before_baked_swjpeg.sh`。默认`max_run_sec: 300`和74.5℃过热保护没有改变。

在同一可信Wi-Fi浏览器打开`http://192.168.1.103:8081/`，默认显示板端已烘焙框的`/detect.mjpg`(320×320 letterbox)，页面可切换`/live.mjpg`查看原始1280×720、80FPS视频。网页**不使用Canvas绘检测框**：C++ NPU解码、NMS后写入同一张VPSS 320×320 NV21帧，再拷贝图像，由独立CPU工作线程完成NV21→RGB与JPEG编码，发送已带框MJPEG。只保留一个最新任务，落后帧直接丢弃，避免延迟累计。原始VENC0的取流/录像不受此软件JPEG线程阻塞。

## 板端实测（20秒限时脚本 + 约25秒完整采集）

- 采集frames=1987，原始JPEGencoded=1960，稳态约80FPS，模型前向forwards=705，forward_errors=0，infer_avg_ms=34.513（含画框和入队）。
- 板端带框JPEG有效生成497帧，BAKED_PREVIEW frames=497 errors=0（约20FPS），BAKED_QUEUE_DROPS=208；软件JPEG编码平均耗时33.1003ms。不能把705次模型前向当作497张网页图。
- 检测接口实时采样：`{"model":"YOLO26n","fps":28.55,"age_ms":16.44,"post_ms":0.11,"baked_frames":389,"baked_errors":0,"boxes":[]}`。单帧`/detect.jpg`请求HTTP 200，JPEG有效；当前场景没有符合阈值的训练目标，**真实正样本框位置尚未目视验证**。
- 报告结束：MAX_TIME_REACHED limit=20s、CLEANUP_DONE、FINAL_MMIO=0x00200001、LOCK_RELEASED，温度测试结束72.414℃、之后降至65.072℃，原74.5℃保护继续有效。
- 框严格来自同一张VPSS帧，并非单独的网页JSON框异步追踪；但浏览器视频端到端时延尚未通过高速相机测量，不应宣称零延迟。帧率约20FPS，移动物体仍可能看出视频帧间隔，不等同完全无延迟。

## 失败方案的明确结论

1. VENC1对VPSS帧直接`CVI_VENC_SendFrame`返回`0xc0078012 = CVI_ERR_VENC_INVALID_VB`，导致检测只有约1FPS；原始80FPS不受影响。
2. 改为专用CVI VB池复制后仍触发同一异常，未解决VENC1兼容。
3. 改用单线程CPU软件JPEG后错误消失，成功318张、0错误，但推理与编码串联导致约13FPS（infer_avg_ms=76.374）。
4. 软件JPEG改为单帧有界异步队列后，推理恢复约28FPS，带框JPEG提升至约20FPS，无编码错误。
5. 对于1280×720高清带框原图，不能直接按320帧代替。今后需增加同PTS高清VPSS帧及支持的硬件叠框路径，测试是否仍能保持80FPS原流。

## 启动与回滚

板端直接启动（仍是300秒最长时间，超温会提前关闭）：
```sh
sh /code/camera/modules/record80_opt/start.sh
```
浏览器：`http://192.168.1.103:8081/`，设备Wi-Fi IP变动时按wlan0最新地址访问。

在非运行状态下恢复旧Canvas入口：
```sh
cp /code/camera/modules/record80_opt/run_capture_first_before_baked_swjpeg.sh \
   /code/camera/modules/record80_opt/run_capture_first.sh
```
旧版二进制仍在同目录；配置和温度保护不会因此改动。原稳定源码提交f98aafe和Git tag`baseline-yolo26-canvas-20261031`可还原。

## 文件位置与交接

电脑只修改`D:\study\LicheeRV`下的文件。源码：
- `camera_capture_first_320.cpp`：NPU/录制/带框软件JPEG线程/双网页预览，异步丢帧队列。
- `frame_baked_preview.h`：同帧320×320 NV21 C++绿色框绘制。
- `vendor/stb_image_write.h`：开源stb JPEG writer，头文件内标明public domain/MIT许可。
- `tests/failed_venc_vb_copy.h`：单独归档的未通过VB兼容实验，不参与构建。
- `tests/run_baked_trial.sh`+`tests/record80_baked_trial.yaml`：20秒有界验收方案，绝不取代默认300秒配置。
- `build_capture_first.sh`：RISC-V交叉编译输出`camera_capture_first_baked`；需外置SDK路径。
- `REPORT_FRAME_SYNC_BAKED_WIP_20261031.md`：先前两次VENC1失败历史。

尚待优化：使用实际训练目标验证正检测框、类名和置信度在网页图片内的绘制（当前只在图像里画绿色框，类名/置信度由页面文字JSON状态显示）；对比20FPS带框画面和原80FPS画面端到端显示时延，进一步提升高清带框和散热。禁止将目前状态写成30FPS高清带框已达成。