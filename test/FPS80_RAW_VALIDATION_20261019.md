# 2026-10-19 GC4653 冲击 80 FPS：真正 RAW 质量验证与模式配置纠偏

本轮新增/修改的 PC 文件**全部在** `D:\study\LicheeRV\test` 下。未覆盖已有的 `stable_69p5_1080p`、`over70_lab`、`over70_next`，未安装新板端驱动/内核，也未更改官方摄像头脚本。

## 结论（请不要把当前样本说成稳定80FPS）

**本轮最高经过完整 1080P Bayer RAW12 抽样验证的实测采集速度为 72.1839 FPS（PTS 72.1835 FPS）**，GC4653输入时钟27MHz，1920×1080，HTS=1165，VTS=1200。12秒统计窗采集867帧，重复PTS 0，取帧超时0；3张 ISP 前 RAW12 大小均为3110400字节，顶部历史行2/3突发亮斑计数均为0；采集期间的 MIPI ECC、CRC、Header、WordCount、FIFO计数均为0。SoC最高温度约65.07°C。**关闭接收以后出现16次ECC计数**，仍需单独研究关机时序。结果文件：`fps80_bayer1080/results/raw1080-20261019-204324/`。

进一步尝试27MHz / HTS=1165 / VTS=1140：12秒采集866帧，72.1007 FPS（PTS72.1004），重复PTS0、超时0，3张3110400字节 RAW12顶部突发亮斑0。但初始化至预热阶段MIPI Word Count累计1次（预热之后未再增加）；停机后ECC累计增加至22，完整运行流程存在异常事件。此档并没有比VTS1200更快，因此**不继续降低到1120**。文件：`fps80_bayer1080/results/raw1080-20261019-204558/`。

更早的 VTS1180、HTS1165、VI+硬件JPEG的短时试验曾得到72.1544FPS、3张 NV21初检合格，但采集结束后ECC累计16，因此自动停止继续试更短VTS：`fps80_vts_trial/results/over70-20261019-202954/`。不要据此宣布VTS1180是合格稳定模式。

## 关键发现：过去“1080P画面”与ISP前RAW实际配置不完全一致

第一次直接移植720p最小程序到1080p时，传感器初始化为自定义1920×1080，然而 `sample_common_sensor.c::SAMPLE_COMM_SNS_GetSize` 仍将 `GCORE_GC4653_MIPI_720P_60FPS_10BIT` 映射到 `PIC_720P`。RAW metadata显示1920×1080，但 `u32Length[0]=1382400`（仅够1280×720 RAW12），于是出现3个0字节无效RAW文件。第一轮因MIPI启动字数错误提前结束，第二轮虽然取帧但仍出现尺寸不匹配和无效RAW。证据目录：`fps80_bayer1080/results/raw1080-20261019-203511/`、`raw1080-20261019-203627/`。

只在新独立副本 `fps80_bayer1080/common/sample_common_sensor.c` 将对应模式映射到 `PIC_1080P`，并让本项目构建脚本使用自己复制的common源码。同时在最小 `main.cpp` 内复制原视频程序中的`CVI_ISP_SetPubAttr(...f32FrameRate=60)` 和 AE固定帧率/最大12000us曝光控制（旧VI-only遗漏这一步时仅36.1043FPS）。重新编译后，**同一最小程序达到72.1839FPS，且 RAW长度变为真实1920×1080 RAW12应有的3110400字节**。说明SDK镜像中的尺寸映射是这一诊断的实际软件错误，不能据此宣称旧1080P样本就是Sensor端真1080 Bayer。新实测纠偏后验证了原始分辨率对应的RAW缓冲区，但仍需其他时刻的额外抽样与可视化验收。

## RAW画质检查的边界

`fps80_bayer1080/analyze_full_raw.py` 对这6张有效原始RAW12逐行解包，比较相同 Bayer 相位的相邻间隔行均值（排除CFA交替造成的假条纹）。最大异常行均值差相对内区中位数约4.3～6.0倍，出现在不同帧的不同行，并无此前异常形态固定在顶部行2/3和特定x列的可重复突变，样本顶部 isolated_top_spikes=0。具体数值、行号和SHA256在 `fps80_bayer1080/results/bayer_full_line_audit.json`。

**注意：这是一种启发式抽样扫描，不等同于“每一帧全像素无损”的保证**。真实验收至少需要10分钟以上连续采集、每5～10秒间隔Bayer RAW抽样、人工检查不同光照、热稳与sensor时钟电气检测。即使MIPI过程中零错误，停机时ECC还需排查。

## 为什么这次仍然不是80FPS

- 不能靠显示端缩放、插帧或统计重复帧假称突破。当前72.18FPS距离真实80FPS还差约10.8%的帧频。
- 压低VTS1200→1140并没有提升本次raw-only采集率，说明`VTS`不是现阶段唯一生效的限速条件，或被其它内部时序/ISP同步控制覆盖。进一步降到1120极可能无收益，且官方手册限制帧长至少为window height+32+VB_min。
- 上轮缩短HTS至1165后短测/72秒约71FPS，旧1150曾零帧且存在MIPI word-count错误先例；GC4653官方手册特别不建议改HTS，因此不能无限缩短来追80。
- 37.125MHz超出公开fSCK最大36MHz，在旧720p试验中ISP前Bayer有彩条；不再把该高频档作为合格方案。
- 新开发的36MHz Sipeed `soph_mipi_rx` 驱动补丁 `test/kernel36/sipeed_soph_mipi_rx_36mhz.patch` 仍是待匹配板端`5.10.4-tag-` kernel ABI、符号表并交叉编译验证的**离线源码**，没有可安全加载的.ko，未上板启用36MHz。

## 实验项目索引（每项都独立）

| 目录 | 用途 |
|---|---|
| `stable_69p5_1080p/` | 用户要求保留的69.5FPS候选，完全未改 |
| `over70_lab/`, `over70_next/` | 约70.7/71.xFPS历史视频链路方案，未改 |
| `fps80_vts_trial/` | VTS1180 JPEG/ISP+MIPI错误时序定位 |
| `fps80_bayer1080/` | 独立VI-only与Bayer RAW采集；隔离1080P buffer mapping修正，源码和新RISCV ELF、runner和6张有效RAW样本 |
| `kernel36/` | Sipeed驱动36MHz离线补丁、原模块只读备份（未加载） |

## 下一阶段最有价值的步骤

1. 优先索取或复原**与实际加载内核 ABI 完全匹配的Sipeed SDK/BSP**，在test独立构建`soph_mipi_rx.ko`，验证vermagic/Module.symvers和回退路径后，才在保证串口/硬件恢复能力时尝试合法36MHz。
2. 同时向GC4653厂家索取/核对原生720P@80和1080P高速窗口对应的sensor PLL、行/帧时序以及MIPI lane速率表，不只更改MCLK单个数字。Sipeed官方MaixPy列出GC4653 720P@80，但明确提醒部分模组在80档存在花纹，**不能简单移植并视为保证**。
3. 先明确目前停机ECC16～22的来源，是sensor stop、CSI PHY关断还是软件停止顺序引起，恢复后进行多轮A/B/A数据确认；此项不影响稳态FPS计数的真实性，但影响整条链路的无错宣称。
4. 若36MHz稳定时序表也不能在当前模组得到可靠≥80FPS，应优先换厂家明确支持目标高速模式且可移植到SG2002的sensor，别继续压高于额定输入时钟。

官方资料：
- GC4653 Datasheet Beta 1.0：https://dl.sipeed.com/fileList/MaixIII/AXera/07_Chip_manual/GC4653_CSP_datasheet%C2%A0for%C2%A0release_Rev.1.0_20190712.pdf
- Sipeed MaixPy camera：http://wiki.sipeed.com/maixpy/doc/zh/vision/camera.html

## 板端恢复

测试程序为短时用户态进程。每次退出后camera lock安全释放；时钟树读回27MHz，未替换板端已有camera程序或模块。板端暂存目录只用`/tmp/raw1080-...`且仅存本项目的临时样本。**归档成功后可删除本轮自己创建的临时目录，PC的test/results保留**。

**最终核验（已完成）**：旧 `stable_69p5_1080p/manifest.sha256.json` 的36项均一致，未改动封存原程序。6张新 Bayer RAW12 均为3110400字节，18份有内容的关键证据（包括原始RAW、日志、JSON）SHA256保存在 `fps80_bayer1080/results/evidence_manifest_20261019.json`。原始6张RAW仍在Windows的test目录；清理了**仅本轮自行新建**的板端 `/tmp/raw1080-20261019-203511`、`203627`、`204324`、`204558` 目录，板端/tmp可用约63.5MiB。最后通过SSH确认相机锁空闲、`clk_cam1=27000000Hz`、SoC约57.7°C、无测试进程。保留启动/停机时错误的原始计数，**不清零证据文件**。
