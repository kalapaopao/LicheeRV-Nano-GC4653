# GC4653 高帧率、无条纹实验方向（尚未部署）

**实验日期：2026-10-19。只读研究与离线推导。** 本文不是“80 FPS 无条纹成功”的验收报告。

## 实机基线
- Board: LicheeRV Nano / Buildroot / Linux 5.10.4, SSH root@10.133.124.1。
- 活跃：`/code/camera/bin/camera_preview_factory ... 60`，通过 USB NCM 的 8081 HTTP 输出 1920×1080、JPEG Q95。
- 实时板端 VI/PTS/编码：约 65.688 / 65.688 / 65.65 FPS，已运行超过约 16 万帧，重复 PTS=0，采集超时=0，VENC errors=0（统计截至本次检查）。
- 本机当次约 12s：493 JPEG、41.324 FPS；这是网络接收速率，不是源采集速率；Q95 载荷约84.36 Mbps。
- `/proc/mipi-rx`：ECC/CRC/Header/WordCount/FIFO 错误皆 0；`/proc/cvitek/vi_dbg`：CSI overflow、宽高计数=0。
- `/sys/class/thermal/thermal_zone0/temp`：约 76958～77308 毫摄氏度。升频前需核对该 thermal zone 对应器件以及允许温度，设置保守中止条件。
- 完整只读日志：`results/board-readonly-report.txt`；原始程序已有 `first-raw.nv21` 和 `first-hw.jpg` 复制在 `results/factory-existing-baseline-20261019/`。
- 旧档 1280×720@80：已有 82.5 FPS 成果，但 RAW Bayer 层顶部有异常；当前的 1080p/Factory YUV 顶部样本无同类明显异常。两种不同分辨率/传感器表，不能直接用一张图片证明所有模式无条纹。
- 亮度统计详见 `results/stripe-nv21-comparison.json`；旧80 YUV第2行相邻行差异28.73，局部常态1.101（26.10倍），旧60=1.96/0.923（2.13倍），当前Factory=1.48/1.220（1.21倍）。**这是启发式质量证据，不是全部缺陷检测。**

## 可能突破路径：保持低 MCLK，通过传感器读出时序取得 >80 FPS
历史坏帧主要与 720P 模式把传感器 MCLK 从27MHz切到37.125MHz同时出现；并非 USB 或 JPEG 独自产生。
目前更干净的 1080P Factory 寄存器表（`speed-fry/workspace/camera/experiments/over100/src/sensor_factory1080/gc4653_sensor_ctl.c`）使用：
- VTS: 寄存器 0x0340/0x0341 = 0x04B0 = 1200
- HTS: 寄存器 0x0342/0x0343 = 0x04E2 = 1250
- 实测约 65.69 FPS。以「像素/行时钟完全不变，且 FPS 反比于 HTS×VTS」为简化模型，目标80 FPS 对应 HTS约1026，若 VTS不变。但不能据此直接写 0x0402：传感器行读出/空白区、接口同步、AE约束和接收端配置未验证。此为**待证假设，不是安全或受支持的参数**。
- 若仅改 VTS，目标值约985，低于当前1080行有效高度，明显不合适。
- 选择更小的实际 sensor window（而不是只裁剪输出 YUV）也可能允许更短读出周期，但历史若干 ROI 实验因驱动不匹配而零帧，不能直接重试同一失败配置。

建议在 test 中复制参考源码成独立变体，保持 factory 初始化表和27MHz，分离 HTS/PLL/窗口变量；先用 datasheet/相关驱动确认读出时钟、lane bit rate、合法最短 HTS 和 VTS/曝光约束，编译至 test 内。**无依据不随机写寄存器、不直接超频到某个预估值。**

## 实际运行验证前的约束
用户要求唯一电脑写入位置 `D:\study\LicheeRV\test`。此次尚未上传新可执行文件或远程写入实验文件，旧程序原样运行。若在板端做新的调参实验，需要明确、隔离的板端临时执行位置和对当前 8081 流短暂停机的许可；不得覆盖旧 `/code/camera/bin` 和 `scripts`，不得刷机、删锁或改系统配置。

通过标准：**原始画面无条纹 + 传感器实采 FPS>80 + 网络完整画面接收尽量跟上 + 温升/丢帧可控**，均要由新一轮实机数据证明。Q85 可减少网络负载，却不能修复 MIPI/RAW 层条纹。
