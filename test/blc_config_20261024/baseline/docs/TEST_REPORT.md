# 板端测试报告：GC4653 录像模块

**测试日期：2026-10-24（实际开发日期）**　**板端RTC：错误地为1970年**　**设备：LicheeRV Nano SG2002 / GC4653 / 1280×720**。

本报告转录、引用保存在 `test/record80_20261024` 中的实际运行日志和视频，不把本地编译当成板端实测。

## 1. 环境与安全前提

- Windows端使用笔记本 `deskDock`，项目根目录 `D:\study\LicheeRV`，SSH免密访问板端 `root@10.133.125.1` / `root@10.133.124.1`。
- 板端 `riscv64`，运行 `/code/camera` 的厂商库；录像存储挂载在 `/dev/mmcblk0p2`，测试前显示约55GiB可用。
- CAM1在默认 `0x00200001` 检查通过后由监督脚本切为 `0x00210001`（分频33，推算约36MHz），测试结束恢复原值。
- 初始温度需小于70°C，运行到74.5°C或发现新MIPI错误自动停机，最多300秒。
- 实测连续写入64MiB的测试用时7.60秒，平均约8.4MiB/s。没有由此推断其他SD卡或高容量卡性能一致。

## 2. 迭代对照结果

| 方案 | 实测录像帧数 | 真实录制时长 | 录像平均FPS | 队列丢帧 | 写入错误 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| 首版：目标80FPS Q85 + 外部FFmpeg封装 | 2,289 | 38.522秒 | 59.420 | 750 | 0 | **失败**，写盘不足 |
| 次版：目标80FPS Q85 + 原生AVI写入 | 1,652 | 27.385秒 | 60.326 | 424 | 0 | **失败**，依然丢帧 |
| **最终版：取流80FPS + Q85录像目标40FPS，原生AVI** | **951** | **24.682秒** | **38.530** | **0** | **0** | **短测通过** |
| 另一次网页启停流程 | 49 | 5.027秒 | 9.747（本次5秒窗口发生在硬件切换/预热阶段） | 0 | 0 | **API启停与封装通过；此条不能作为稳定FPS结论** |

**注意：** 最终方案“录像队列0丢帧”只统计入队之后是否被覆盖/丢弃。硬件编码线程可能早于入队点替换预览待处理帧；在最后短测日志中，摄像头取流仍约80FPS，JPEG编码线程统计约79FPS但在切换/RAW诊断时短暂低于80，故录像平均38.53FPS而非精确40FPS。当前不把该方案描述成严格恒定实录40FPS或逐帧无损。

### 最终版板端录像证据

位于板端：

```text
/code/camera/recordings/gc4653_19700101_005208_1290_0001_720p40.avi
/code/camera/recordings/gc4653_19700101_005208_1290_0001_720p40.avi.json
```

本地下载后位置：

```text
D:\study\LicheeRV\test\record80_20261024\captures\
    gc4653_19700101_005208_1290_0001_720p40.avi
    gc4653_19700101_005208_1290_0001_720p40.avi.json
```

原始AVI文件字节数 `133385096`，在Windows和板端都核对过 SHA256：

```text
e9f0b2c1f815b261ef90caac553ad0b38c9b77c1b2ce4447f285edd1545751f3
```

旁路元数据（照录实测值）：

```json
{
  "codec": "MJPEG",
  "width": 1280,
  "height": 720,
  "nominal_fps": 40,
  "capture_target_fps": 80,
  "frames": 951,
  "elapsed_sec": 24.682,
  "fps_by_elapsed": 38.530,
  "jpeg_bytes": 133361579,
  "queue_drops": 0,
  "write_errors": 0
}
```

FFprobe实际读取 `codec_name=mjpeg`、`width=1280`、`height=720`、`r_frame_rate=40/1`、`duration=23.775000`、`nb_frames=951`，与生成AVI索引帧数一致。FFmpeg的30帧解码返回退出码0。输出过 `unable to decode APP fields` 的厂商JPEG APP元数据警告，但该批抽测帧成功解码；**并未做951帧逐帧像素审查**。

本地保存的解析抽帧：`test/record80_20261024/verified_frame.jpg`，分辨率1280×720。

### VI/MIPI与时钟

最终版日志中，稳定阶段 `CLOCK36_WINDOW` 5秒取流分别有401/400等帧数，对应约80FPS；`duplicate_pts=0`、`timeouts=0`、`encode_errors=0`。MIPI监控在最终版无新增错误；退出时分频寄存器恢复 `0x00200001`，独占锁已释放。

网页/API验证独立使用 `test/record80_20261024/test_web_controls.ps1`，真实收到了：
- GET `http://10.133.124.1:8081/` → HTTP 200；
- POST `http://10.133.124.1:8082/start` → `accepted=true`；
- GET `/status` → `recording=true`、`written`随时间增长；
- POST `/stop` → `accepted=true`；
- GET `/status` → `recording=false`、`segments=1`、`last`存在；
- 对应的49帧AVI（短测处于启动时序，所以不拿它评测帧率）可被FFprobe读取。

证据日志：`test/record80_20261024/web_control_test.log`、板端 `/tmp/clock36_record_20261024/record_report/capture.log`。一次网页测试MIPI累计值开始前已有1，之后没有继续增加，应写成 **“本次未新增”**，而不是累计绝对零。

## 3. 真实板端与模块化后的验证范围

实测源自 `test/record80_20261024/camera_36record`，对应验证版SHA：
```text
3d751f2b2c16b0b0815453593689d5b96bd1d4375c667f37836846edf3600cba
```

`modules/record80` 保留相同C++录像/摄像头逻辑，仅重新组织文件、构建入口、部署位置/独立日志路径。模块化后是否重新构建、上板运行，需要在交接文档中单独报告，并且不应混同于本节原测试。

### 模块化后再次实机复测（2026-10-24）

新模块经过本笔记本 `modules/record80/scripts/build.sh` **完整重新编译成功**，SHA-256 与上述原验证版完全一致：

```text
3d751f2b2c16b0b0815453593689d5b96bd1d4375c667f37836846edf3600cba
```

使用 `modules/record80/scripts/deploy.ps1` 上传至板端持久路径 `/code/camera/modules/record80`，板端SHA一致，并从**新路径**实际执行：

```sh
MAX_RUN_SEC=24 RECORD_TEST_AUTOSTART=1 sh /code/camera/modules/record80/run_board.sh
```

得到录像成品：

```text
/code/camera/recordings/gc4653_19700101_012848_2310_0001_720p40.avi
/code/camera/recordings/gc4653_19700101_012848_2310_0001_720p40.avi.json
```

板端实读JSON：

```json
{"codec":"MJPEG","width":1280,"height":720,"nominal_fps":40,"capture_target_fps":80,
 "frames":961,"elapsed_sec":24.767,"fps_by_elapsed":38.802,
 "jpeg_bytes":139306283,"queue_drops":0,"write_errors":0}
```

FFprobe：1280×720 / MJPEG / 40/1 / 961帧 / 24.025秒AVI名义播放时长。程序采集末期5秒窗口 `host_fps=79.9999`，PTS `79.9997`。起始累计MIPI `1 0 0 0 0`，至正常退出**没有增加**；温度最后观测67.519°C；`FINAL_MMIO=0x00200001`，`CLEANUP_DONE`，摄像头锁已释放。

**验收判定：** 持久路径部署 / 自动录像 / 文件索引和JSON / 无队列丢帧 / 约80FPS采集 / 异常监控与回退 **通过该24秒短测**。但不得把这次测试扩展成5分钟连续录像、全帧画质审计或与YOLO同时推理已通过。

## 4. 未通过或尚未执行的验收

- 全部 **80FPS Q85原画幅录像**：两次试验分别丢750与424帧，失败。
- 单段超过60秒自动切段：尚未通过完整验证。
- 5分钟以上稳定录制、持续上小时/多轮热启动：尚未完成。
- 板端RTC/NTP校准：尚未完成，文件名不能用于标示时间。
- AVI逐帧时间戳：尚未实现，录像38.53FPS均值但AVI标称40FPS的播放时长差问题存在。
- 浏览器真实渲染FPS：未逐帧测量，不能与VI/PTS FPS混淆。
- CPU/NPU YOLO目标检测实时推理：没有包含在本次录像验收中。
- 摄像头MCLK实体引脚波形示波器验证：尚未完成。

## 5. 验收判定原则

下一版须同时提供：构建SHA、板端SHA一致、VI/PTS取流窗口、写入AVI大小/JSON `frames/elapsed/drops/errors`、FFprobe实际帧数、至少抽帧图像质量、MIPI差量、温度上限、结束后时钟/锁回退。只返回 `HTTP 200`、`accepted=true` 或仅编译通过，不构成录像完成。
