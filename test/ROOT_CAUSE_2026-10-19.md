# LicheeRV Nano / GC4653 RAW 彩条根因隔离实验

实验日期：2026-10-19。此文件及本次所有 Windows 新增源码、二进制、数据均在 `D:\study\LicheeRV\test` 内。

## 结论（区分事实与推测）

**已由控制变量实验证实**：这块板卡的 720P 模式中，采集由 27MHz MCLK 驱动时，无此前顶部 RAW 异常；把 MCLK 选到 37.125MHz 后，帧率约82.5FPS，ISP 前的 RAW12 第2、3行 x约646~711 固定区域出现约3400~3600、最高4092的异常像素。只改 `MAIX_SENSOR_FPS` 请求数字、但固定 MCLK，异常随 MCLK 档而非请求数字变化。

**能排除**：JPEG、浏览器/HTTP/USB、ISP TNR/DPC、YUV NV21 转换、VI TILE 压缩误解码以及仅由 `fps=80` 请求变量或 AE 自动曝光造成的假条纹。

**还不能判定**：GC4653 内部 PLL/读出时序软件配置与37.125MHz不匹配，还是模组时钟/供电/MIPI信号质量的高速裕量不足。两者均可产生固定位置的可重复缺陷。未用示波器测量波形，未做相同型号模组替换，也没找到经过 GC4653 型号确认的内部测试图案寄存器，不做猜测式写寄存器。

## 开发减法

把历史复杂的 `VI → VENC JPEG → HTTP → 网络 → 网页` 简化为：

`GC4653 → MIPI/VI → CVI_VI_GetPipeFrame (RAW12 ×3) + CVI_VI_GetChnFrame 计数/PTS`

- JPEG、网络、GUI、视频显示线程全部取消。
- 传感器720P初始化寄存器表、窗口尺寸、MIPI lane、板端 SDK 保持不变。
- VI通道统一设为 `COMPRESS_MODE_NONE`，拒绝压缩RAW的错误解析（初次试验的 TILE dump 长691200字节，不能当成RAW12；修正后线性RAW为1382400字节）。
- 唯一外部变量 `LICHEE_RAW_MCLK=27|37`，覆盖以前仅由请求 FPS 选择MCLK的逻辑。27和37.125均为项目现有支持枚举，没有尝试未知频率。
- 每组完整3帧RAW、7秒计数窗口。非长期稳定性验收。

## 四组交叉对照（完成）

| FPS请求 | MCLK | VI FPS | RAW前2/3行异常 | 重复PTS/超时 |
|---|---|---:|---|---|
| 60 | 27 MHz | 60.0002 | 3/3帧无异常高值 | 0/0 |
| 80 | 37.125 MHz | 82.4981 | 3/3帧出现 >3000 异常 | 0/0 |
| 60 | 37.125 MHz | 82.5104 | 3/3帧出现 >3000 异常 | 0/0 |
| 80 | 27 MHz | 60.0003 | 3/3帧无异常高值 | 0/0 |

RAW解析：每3字节恢复2像素的12bit packed RAW；统计前8行最大值和大于3000的异常点数量，阈值只针对当前对照场景，不能当通用画质质量分数。原始数据位于 `results/raw-isolation-20261019-retry1/`，每一档包括 `raw-0/1/2.bin`、`result.json`、`run.log` 和原 VI 计数。

### 高速异常的空间特性

6张高速RAW共同特点：第2行异常像素的 x 最小值始终647，第3行为646，异常横向集中在约646~711；而6张27MHz RAW中前8行 >3000 的统计均为0。完整逐帧像素坐标在 `results/raw-isolation-20261019-retry1/anomaly_pixel_positions.json`。此规律更像固定时序/固定通路问题，而非随机网络错误；但不能因此排除电气问题。

## 固定曝光减法（部分完成）

精简版自带的 manual 模式把曝光固定为 5000us、模拟增益4096、数字增益1024。

- 请求80 + 37.125MHz：实际82.5006 FPS，3张RAW中第2/3行仍有异常，最大4092。说明仅关闭AE不足以消除问题。
- 请求80 + 27MHz：VI日志仍为60FPS，但后续RAW文件出现写入不完整；由于 `/tmp` 已满，相关RAW不得用于画质结论。原非手动的27MHz对照是有效的。
- 第一次固定曝光任务被板端临时锁拦截，未开始试验。保留失败记录，未删锁未强杀。

## 设备现场与数据清理

此轮检查前摄像头预览进程已处于停止状态，互斥锁不存在；实验后保持原本停止状态，没有擅自启动预览。无摄像头生产二进制、驱动、ISP库、系统配置文件被修改或覆盖。

实验临时产生的板端目录仅在 `/tmp/lichee-raw-isolation*`，相关证据下载至本地 `test/results` 后，仅删除本轮自己创建的三个实验 tmp 目录，腾出空间。`df -h /tmp` 从使用率100%恢复到54%，约29.4MiB可用。审核日志在 `results/raw-isolation-tmp-cleanup.txt`。

## 下一步区分软件与硬件的实验优先级

1. **验证正式 GC4653 高速初始化表**：以型号匹配的寄存器数据和接收时钟要求核对 sensor PLL、MCLK、MIPI lane rate、HTS/VTS、曝光/帧头窗口时序。如果确证SDK现用表和37.125MHz不匹配，在 `test` 中做单寄存器变量实验，不乱写未知值。
2. **有文档依据的传感器内置测试图案**：如果 GC4653 确认支持可由自身产生 RAW 的 test pattern，27/37MHz各采集对照。若测试图案仍异常，倾向传感器输出/MIPI链路；若测试图案正常、光学图像异常，倾向像素读出/模拟前端。其它型号 GC08A3/GC05A2 的0x008c不能直接用于GC4653。
3. **同型号模组+排线交叉替换**：固定当前板卡、程序与电源，只换模组/排线。在另一块模组上同37.125MHz无异常，说明原模组或连接问题可能性显著升高；两模组均异常则优先查板端电气/驱动配置。
4. **物理测量**：示波器检查 MCLK实际频率/抖动、各路供电纹波，MIPI D-PHY走线/终端/lane时序；高速只看CRC=0不能排除固定位置误采样/内部读出错误。

## 文件索引与复现

- 源码：`raw_isolation/main.cpp`（简化的VI/RAW/PTS）；`raw_isolation/sensor/gc4653_cmos.c`（仅MCLK覆盖）；`raw_isolation/build.sh`、`raw_isolation/rebuild-main.sh`，输出 `raw_isolation/camera_raw_isolation`。
- 安全调度：`run_raw_isolation_retry1.py`，只用 `/tmp/lichee-raw-isolation-retry1`，运行 4组；`run_raw_isolation_manual_retry1.py` 另测固定曝光。
- 数据分析：`results/raw-isolation-20261019-retry1/summary.json` 与各档的 `analysis.json`、`anomaly_pixel_positions.json`；`results/raw-isolation-20261019-manual-retry1/`。
- 初次压缩格式不符实验：`results/raw-isolation-20261019/`，属于失败但保留证据；不能与正常RAW直接比较。

官方参考：https://wiki.sipeed.com/maixpy/doc/zh/vision/camera.html。该文档提示某些GC4653模组80FPS会有异常纹路，但没有提供确定本板根因的电气诊断，因此这里只作为现象佐证。

**现阶段结论表述：已定位到37.125MHz高速状态引起的上游原始采集异常，尚未证明具体是哪一个芯片寄存器/电气部件失效。**